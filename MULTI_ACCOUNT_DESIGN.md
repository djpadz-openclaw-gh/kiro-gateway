# Multi-Account Billing-Aware Kiro Gateway

## Overview

This document describes the design for adding multi-account support to the Kiro gateway with automatic billing-aware failover.

## Architecture

### Configuration Schema

```json5
{
  "accounts": [
    {
      "id": "dj",
      "name": "Dj Account",
      "refreshToken": "...",
      "profileArn": "...",
      "region": "us-east-1",
      "overage": false
    },
    {
      "id": "sherra",
      "name": "Sherra Account",
      "refreshToken": "...",
      "profileArn": "...",
      "region": "us-east-1",
      "overage": true  // This account has overages enabled
    }
  ],
  "healthCheckIntervalHours": 1,
  "vpnProxyUrl": "http://127.0.0.1:7890"  // Optional, shared across accounts
}
```

### In-Memory State

```python
{
  "current_account_id": "dj",
  "last_health_check": 1713012660,
  "accounts": {
    "dj": {
      "has_credits": True,
      "last_checked": 1713012660,
      "error": None
    },
    "sherra": {
      "has_credits": False,
      "last_checked": 1713012660,
      "error": "MONTHLY_REQUEST_COUNT"
    }
  }
}
```

## Implementation Plan

### 1. Configuration Management (`kiro/multi_account_config.py`)
- Load multiple accounts from environment or config file
- Validate account configuration
- Provide account lookup by ID

### 2. Account Manager (`kiro/account_manager.py`)
- Manage multiple KiroAuthManager instances (one per account)
- Track current active account
- Implement health check logic
- Implement account selection logic
- Handle billing error detection

### 3. Health Check (`kiro/health_checker.py`)
- Check if an account has credits by calling `/v1/models`
- Detect `MONTHLY_REQUEST_COUNT` errors
- Update account state
- Run on startup and hourly

### 4. Request Routing
- Modify routes to use AccountManager instead of single auth manager
- Catch billing errors and trigger immediate re-check
- Fall back to overage account if needed

### 5. Integration Points
- `main.py` - initialize AccountManager on startup
- `routes_openai.py` - use AccountManager for routing
- `routes_anthropic.py` - use AccountManager for routing
- Add hourly health check task

## Billing Error Detection

When a request returns `MONTHLY_REQUEST_COUNT` error:
1. Mark current account as out of credits
2. Immediately run health check on all accounts
3. Switch to first account with credits
4. If all out of credits, use overage account
5. Retry the request with new account

## Failover Behavior

**Scenario 1: Primary account runs out of credits mid-hour**
- Request gets `MONTHLY_REQUEST_COUNT` error
- Immediately re-check all accounts
- Switch to secondary account
- Retry request

**Scenario 2: Hourly health check finds credits available**
- Scheduled health check runs
- Finds primary account now has credits (new billing cycle)
- Switches back to primary
- Future requests use primary

**Scenario 3: All accounts out of credits**
- All accounts return `MONTHLY_REQUEST_COUNT`
- Use overage account (has overages enabled)
- Requests succeed but incur overage charges

## Files to Create/Modify

### New Files
- `kiro/multi_account_config.py` - Configuration management
- `kiro/account_manager.py` - Account management and routing
- `kiro/health_checker.py` - Health check logic
- `MULTI_ACCOUNT_DESIGN.md` - This document

### Modified Files
- `main.py` - Initialize AccountManager, add health check task
- `routes_openai.py` - Use AccountManager
- `routes_anthropic.py` - Use AccountManager
- `config.py` - Add multi-account configuration options
- `.env.example` - Add multi-account configuration examples

## Configuration Examples

### Environment Variables
```bash
# Single account (backward compatible)
REFRESH_TOKEN="..."
PROFILE_ARN="..."

# Multi-account (new)
KIRO_ACCOUNTS_JSON='[
  {
    "id": "dj",
    "refreshToken": "...",
    "profileArn": "...",
    "overage": false
  },
  {
    "id": "sherra",
    "refreshToken": "...",
    "profileArn": "...",
    "overage": true
  }
]'
KIRO_HEALTH_CHECK_INTERVAL_HOURS=1
```

### Configuration File
```json
{
  "accounts": [
    {
      "id": "dj",
      "refreshToken": "...",
      "profileArn": "...",
      "overage": false
    },
    {
      "id": "sherra",
      "refreshToken": "...",
      "profileArn": "...",
      "overage": true
    }
  ],
  "healthCheckIntervalHours": 1
}
```

## Backward Compatibility

- Single account mode still works (uses existing REFRESH_TOKEN, PROFILE_ARN)
- Multi-account mode is opt-in via KIRO_ACCOUNTS_JSON or config file
- If multi-account config is present, it takes precedence
- Existing deployments continue to work without changes

## Testing Strategy

1. **Unit tests**
   - Account selection logic
   - Health check detection
   - Billing error parsing

2. **Integration tests**
   - Multi-account failover
   - Health check scheduling
   - Request routing

3. **Manual testing**
   - Simulate billing error
   - Verify failover to secondary
   - Verify hourly health check
   - Verify fallback to overage account
