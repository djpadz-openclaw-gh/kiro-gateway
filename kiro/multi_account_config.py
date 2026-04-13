# -*- coding: utf-8 -*-

"""
Multi-account configuration management for Kiro Gateway.

Handles loading and validating multiple account configurations.
Supports both environment variables and configuration files.
"""

import json
import os
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path

from loguru import logger


@dataclass
class AccountConfig:
    """Configuration for a single Kiro account."""
    id: str
    refresh_token: str
    profile_arn: Optional[str] = None
    region: str = "us-east-1"
    overage: bool = False
    name: Optional[str] = None
    
    def __post_init__(self):
        """Validate account configuration."""
        if not self.id:
            raise ValueError("Account id is required")
        if not self.refresh_token:
            raise ValueError(f"Account {self.id}: refresh_token is required")
        if not self.name:
            self.name = self.id


@dataclass
class MultiAccountConfig:
    """Configuration for multi-account setup."""
    accounts: List[AccountConfig]
    health_check_interval_hours: int = 1
    vpn_proxy_url: Optional[str] = None
    
    def __post_init__(self):
        """Validate multi-account configuration."""
        if not self.accounts:
            raise ValueError("At least one account is required")
        
        # Check for duplicate account IDs
        account_ids = [acc.id for acc in self.accounts]
        if len(account_ids) != len(set(account_ids)):
            raise ValueError("Duplicate account IDs found")
        
        # Check that exactly one account is marked as overage
        overage_accounts = [acc for acc in self.accounts if acc.overage]
        if len(overage_accounts) > 1:
            raise ValueError(f"Multiple accounts have overage enabled. Only one account can have overage=true")
        if not overage_accounts:
            logger.warning("No account marked as overage account. Failover may not work correctly.")
    
    def get_account(self, account_id: str) -> Optional[AccountConfig]:
        """Get account configuration by ID."""
        for acc in self.accounts:
            if acc.id == account_id:
                return acc
        return None
    
    def get_overage_account(self) -> Optional[AccountConfig]:
        """Get the overage account."""
        for acc in self.accounts:
            if acc.overage:
                return acc
        return None


def load_multi_account_config_from_env_vars() -> Optional[MultiAccountConfig]:
    """
    Load multi-account configuration from ACCOUNT_N_* environment variables.
    
    Supports arbitrary number of accounts using pattern:
    - ACCOUNT_1_REFRESH_TOKEN
    - ACCOUNT_1_NAME
    - ACCOUNT_1_PROFILE_ARN
    - ACCOUNT_1_REGION
    - ACCOUNT_1_OVERAGE
    - ACCOUNT_2_REFRESH_TOKEN
    - etc.
    
    Returns:
        MultiAccountConfig if accounts found, None otherwise
    """
    accounts_dict: Dict[int, Dict[str, Any]] = {}
    
    # Scan environment variables for ACCOUNT_N_* pattern
    for key, value in os.environ.items():
        if key.startswith("ACCOUNT_"):
            parts = key.split("_", 2)  # Split into ["ACCOUNT", "N", "FIELD"]
            if len(parts) >= 3:
                try:
                    account_num = int(parts[1])
                    field_name = "_".join(parts[2:]).lower()
                    
                    if account_num not in accounts_dict:
                        accounts_dict[account_num] = {}
                    
                    # Parse boolean values
                    if field_name == "overage":
                        accounts_dict[account_num][field_name] = value.lower() in ("true", "1", "yes")
                    else:
                        accounts_dict[account_num][field_name] = value
                except (ValueError, IndexError):
                    continue
    
    if not accounts_dict:
        return None
    
    # Build AccountConfig objects
    accounts = []
    overage_count = 0
    
    for account_num in sorted(accounts_dict.keys()):
        acc_data = accounts_dict[account_num]
        
        # Validate required fields
        if "refresh_token" not in acc_data:
            logger.warning(f"Account {account_num}: refresh_token not found, skipping")
            continue
        
        account = AccountConfig(
            id=acc_data.get("id", f"account-{account_num}"),
            refresh_token=acc_data["refresh_token"],
            profile_arn=acc_data.get("profile_arn"),
            region=acc_data.get("region", "us-east-1"),
            overage=acc_data.get("overage", False),
            name=acc_data.get("name", f"Account {account_num}")
        )
        accounts.append(account)
        
        if account.overage:
            overage_count += 1
    
    if not accounts:
        return None
    
    # Validate overage constraint: only one account can have overage=true
    if overage_count > 1:
        raise ValueError(f"Multiple accounts have overage enabled ({overage_count}). Only one account can have overage=true")
    
    health_check_interval = int(os.getenv("HEALTH_CHECK_INTERVAL_HOURS", "1"))
    vpn_proxy_url = os.getenv("VPN_PROXY_URL")
    
    config = MultiAccountConfig(
        accounts=accounts,
        health_check_interval_hours=health_check_interval,
        vpn_proxy_url=vpn_proxy_url
    )
    
    logger.info(f"Loaded multi-account configuration from environment variables with {len(accounts)} accounts")
    return config


def load_multi_account_config_from_env() -> Optional[MultiAccountConfig]:
    """
    Load multi-account configuration from environment variables.
    
    Looks for KIRO_ACCOUNTS_JSON environment variable containing JSON array.
    
    Returns:
        MultiAccountConfig if found, None otherwise
    """
    accounts_json = os.getenv("KIRO_ACCOUNTS_JSON")
    if not accounts_json:
        return None
    
    try:
        accounts_data = json.loads(accounts_json)
        if not isinstance(accounts_data, list):
            raise ValueError("KIRO_ACCOUNTS_JSON must be a JSON array")
        
        accounts = []
        for acc_data in accounts_data:
            account = AccountConfig(
                id=acc_data.get("id"),
                refresh_token=acc_data.get("refreshToken") or acc_data.get("refresh_token"),
                profile_arn=acc_data.get("profileArn") or acc_data.get("profile_arn"),
                region=acc_data.get("region", "us-east-1"),
                overage=acc_data.get("overage", False),
                name=acc_data.get("name")
            )
            accounts.append(account)
        
        health_check_interval = int(os.getenv("KIRO_HEALTH_CHECK_INTERVAL_HOURS", "1"))
        vpn_proxy_url = os.getenv("VPN_PROXY_URL")
        
        config = MultiAccountConfig(
            accounts=accounts,
            health_check_interval_hours=health_check_interval,
            vpn_proxy_url=vpn_proxy_url
        )
        
        logger.info(f"Loaded multi-account configuration with {len(accounts)} accounts")
        return config
    
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error(f"Failed to load multi-account configuration from environment: {e}")
        return None


def load_multi_account_config_from_file(file_path: str) -> Optional[MultiAccountConfig]:
    """
    Load multi-account configuration from JSON file.
    
    Args:
        file_path: Path to JSON configuration file
    
    Returns:
        MultiAccountConfig if found, None otherwise
    """
    path = Path(file_path)
    if not path.exists():
        return None
    
    try:
        with open(path, "r") as f:
            config_data = json.load(f)
        
        accounts_data = config_data.get("accounts", [])
        if not accounts_data:
            raise ValueError("No accounts found in configuration file")
        
        accounts = []
        for acc_data in accounts_data:
            account = AccountConfig(
                id=acc_data.get("id"),
                refresh_token=acc_data.get("refreshToken") or acc_data.get("refresh_token"),
                profile_arn=acc_data.get("profileArn") or acc_data.get("profile_arn"),
                region=acc_data.get("region", "us-east-1"),
                overage=acc_data.get("overage", False),
                name=acc_data.get("name")
            )
            accounts.append(account)
        
        health_check_interval = config_data.get("healthCheckIntervalHours", 1)
        vpn_proxy_url = config_data.get("vpnProxyUrl")
        
        config = MultiAccountConfig(
            accounts=accounts,
            health_check_interval_hours=health_check_interval,
            vpn_proxy_url=vpn_proxy_url
        )
        
        logger.info(f"Loaded multi-account configuration from {file_path} with {len(accounts)} accounts")
        return config
    
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error(f"Failed to load multi-account configuration from file: {e}")
        return None


def load_multi_account_config() -> Optional[MultiAccountConfig]:
    """
    Load multi-account configuration from environment or file.
    
    Priority:
    1. ACCOUNT_N_* environment variables (new approach)
    2. KIRO_ACCOUNTS_JSON environment variable
    3. KIRO_ACCOUNTS_FILE environment variable
    4. ./kiro-accounts.json file
    
    Returns:
        MultiAccountConfig if found, None otherwise
    """
    # Try ACCOUNT_N_* environment variables first (new approach)
    config = load_multi_account_config_from_env_vars()
    if config:
        return config
    
    # Try KIRO_ACCOUNTS_JSON environment variable
    config = load_multi_account_config_from_env()
    if config:
        return config
    
    # Try file from environment variable
    config_file = os.getenv("KIRO_ACCOUNTS_FILE")
    if config_file:
        config = load_multi_account_config_from_file(config_file)
        if config:
            return config
    
    # Try default file
    config = load_multi_account_config_from_file("./kiro-accounts.json")
    if config:
        return config
    
    return None
