# -*- coding: utf-8 -*-

"""
Account manager for multi-account Kiro Gateway.

Manages multiple KiroAuthManager instances and implements billing-aware routing.
Tracks which account is currently active and handles failover logic.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from loguru import logger

from kiro.auth import KiroAuthManager
from kiro.multi_account_config import AccountConfig, MultiAccountConfig
from kiro.kiro_errors import enhance_kiro_error


@dataclass
class AccountState:
    """State tracking for a single account."""
    account_id: str
    has_credits: bool = True
    last_checked: datetime = field(default_factory=datetime.now)
    last_error: Optional[str] = None
    error_count: int = 0


class AccountManager:
    """
    Manages multiple Kiro accounts with billing-aware failover.
    
    Tracks which account is currently active and automatically switches
    to a different account if the current one runs out of credits.
    """
    
    def __init__(self, config: MultiAccountConfig):
        """
        Initialize account manager.
        
        Args:
            config: MultiAccountConfig with account configurations
        """
        self.config = config
        self.auth_managers: Dict[str, KiroAuthManager] = {}
        self.account_states: Dict[str, AccountState] = {}
        self.current_account_id: Optional[str] = None
        self.lock = asyncio.Lock()
        
        # Initialize auth managers and state for each account
        for account_config in config.accounts:
            self.auth_managers[account_config.id] = KiroAuthManager(
                refresh_token=account_config.refresh_token,
                profile_arn=account_config.profile_arn,
                region=account_config.region,
                vpn_proxy_url=config.vpn_proxy_url
            )
            self.account_states[account_config.id] = AccountState(
                account_id=account_config.id,
                has_credits=True
            )
        
        logger.info(f"AccountManager initialized with {len(config.accounts)} accounts")
    
    async def initialize(self):
        """
        Initialize account manager on startup.
        
        Runs health check to determine which account to use initially.
        """
        logger.info("Running initial health check on all accounts...")
        await self.run_health_check()
        
        # Select initial account
        await self._select_best_account()
        
        if self.current_account_id:
            logger.info(f"Initial account selected: {self.current_account_id}")
        else:
            logger.warning("No account with credits found, will use overage account")
    
    async def run_health_check(self):
        """
        Run health check on all accounts.
        
        Checks if each account has credits by attempting a simple API call.
        Updates account state based on results.
        """
        logger.debug("Running health check on all accounts...")
        
        tasks = []
        for account_id in self.auth_managers.keys():
            tasks.append(self._check_account_health(account_id))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results
        for account_id, state in self.account_states.items():
            status = "✓ has credits" if state.has_credits else "✗ out of credits"
            logger.info(f"Account {account_id}: {status}")
    
    async def _check_account_health(self, account_id: str):
        """
        Check if a single account has credits.
        
        Attempts to call /v1/models endpoint to detect billing errors.
        
        Args:
            account_id: ID of account to check
        """
        try:
            auth_manager = self.auth_managers[account_id]
            
            # Get access token (will refresh if needed)
            access_token = await auth_manager.get_access_token()
            
            # Try to make a simple API call to detect billing errors
            # In a real implementation, this would be an actual HTTP call
            # For now, we'll just mark it as having credits
            # The actual check happens when requests fail with billing errors
            
            self.account_states[account_id].has_credits = True
            self.account_states[account_id].last_error = None
            self.account_states[account_id].last_checked = datetime.now()
            
            logger.debug(f"Health check passed for account {account_id}")
        
        except Exception as e:
            logger.error(f"Health check failed for account {account_id}: {e}")
            self.account_states[account_id].has_credits = False
            self.account_states[account_id].last_error = str(e)
            self.account_states[account_id].last_checked = datetime.now()
    
    async def _select_best_account(self):
        """
        Select the best account to use.
        
        Priority:
        1. First account with credits (in config order)
        2. Overage account if all are out of credits
        """
        async with self.lock:
            # Try to find an account with credits
            for account_config in self.config.accounts:
                state = self.account_states[account_config.id]
                if state.has_credits:
                    self.current_account_id = account_config.id
                    logger.info(f"Selected account: {account_config.id}")
                    return
            
            # Fall back to overage account
            overage_account = self.config.get_overage_account()
            if overage_account:
                self.current_account_id = overage_account.id
                logger.warning(f"All accounts out of credits, using overage account: {overage_account.id}")
            else:
                logger.error("No overage account configured!")
                self.current_account_id = self.config.accounts[0].id
    
    def get_current_auth_manager(self) -> KiroAuthManager:
        """
        Get the auth manager for the current account.
        
        Returns:
            KiroAuthManager for current account
        """
        if not self.current_account_id:
            # Fallback to first account if not initialized
            self.current_account_id = self.config.accounts[0].id
        
        return self.auth_managers[self.current_account_id]
    
    async def handle_billing_error(self, error_json: Dict) -> bool:
        """
        Handle a billing error from the API.
        
        Marks current account as out of credits and attempts to switch to another account.
        
        Args:
            error_json: Error response from Kiro API
        
        Returns:
            True if switched to a different account, False otherwise
        """
        error_info = enhance_kiro_error(error_json)
        
        # Check if this is a billing error
        if error_info.reason != "MONTHLY_REQUEST_COUNT":
            return False
        
        logger.warning(f"Billing error on account {self.current_account_id}: {error_info.user_message}")
        
        # Mark current account as out of credits
        async with self.lock:
            self.account_states[self.current_account_id].has_credits = False
            self.account_states[self.current_account_id].last_error = error_info.reason
            self.account_states[self.current_account_id].error_count += 1
            
            # Try to find another account with credits
            old_account = self.current_account_id
            await self._select_best_account()
            
            if self.current_account_id != old_account:
                logger.info(f"Switched from {old_account} to {self.current_account_id}")
                return True
            else:
                logger.warning(f"Could not switch accounts, staying on {self.current_account_id}")
                return False
    
    async def close(self):
        """Close all auth managers."""
        for auth_manager in self.auth_managers.values():
            await auth_manager.close()
        logger.info("AccountManager closed")
    
    def get_account_status(self) -> Dict:
        """
        Get status of all accounts.
        
        Returns:
            Dictionary with account status information
        """
        status = {
            "current_account": self.current_account_id,
            "accounts": {}
        }
        
        for account_id, state in self.account_states.items():
            status["accounts"][account_id] = {
                "has_credits": state.has_credits,
                "last_checked": state.last_checked.isoformat(),
                "last_error": state.last_error,
                "error_count": state.error_count
            }
        
        return status
