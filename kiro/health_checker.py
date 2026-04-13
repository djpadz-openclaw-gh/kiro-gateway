# -*- coding: utf-8 -*-

"""
Health checker for multi-account Kiro Gateway.

Periodically checks if accounts have credits and updates account state.
Runs on startup and at regular intervals.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from kiro.account_manager import AccountManager


class HealthChecker:
    """
    Periodically checks health of all accounts.
    
    Runs health checks at regular intervals to detect when accounts
    regain credits (e.g., after billing cycle reset).
    """
    
    def __init__(self, account_manager: AccountManager, interval_hours: int = 1):
        """
        Initialize health checker.
        
        Args:
            account_manager: AccountManager instance to check
            interval_hours: Interval between health checks in hours
        """
        self.account_manager = account_manager
        self.interval_seconds = interval_hours * 3600
        self.running = False
        self.task: Optional[asyncio.Task] = None
        
        logger.info(f"HealthChecker initialized with {interval_hours}h interval")
    
    async def start(self):
        """Start the health checker background task."""
        if self.running:
            logger.warning("HealthChecker is already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._run())
        logger.info("HealthChecker started")
    
    async def stop(self):
        """Stop the health checker background task."""
        if not self.running:
            return
        
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        logger.info("HealthChecker stopped")
    
    async def _run(self):
        """
        Main health checker loop.
        
        Runs health checks at regular intervals.
        """
        while self.running:
            try:
                await asyncio.sleep(self.interval_seconds)
                
                if not self.running:
                    break
                
                logger.debug("Running scheduled health check...")
                await self.account_manager.run_health_check()
                
                # Re-select best account in case credits were restored
                await self.account_manager._select_best_account()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health checker: {e}")
                # Continue running even if there's an error
                await asyncio.sleep(60)  # Wait a minute before retrying
    
    async def check_now(self):
        """
        Run a health check immediately.
        
        Useful for manual triggering or testing.
        """
        logger.info("Running immediate health check...")
        await self.account_manager.run_health_check()
        await self.account_manager._select_best_account()
