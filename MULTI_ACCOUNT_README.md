# Multi-Account Billing-Aware Kiro Gateway

## Overview

This fork of the Kiro Gateway adds support for multiple Kiro accounts with automatic billing-aware failover. When one account runs out of credits, the gateway automatically switches to another account. This enables cost optimization by staggering billing cycles and using overage accounts as fallback.

## Features

- **Multiple Account Support**: Configure multiple Kiro accounts in a single gateway instance
- **Automatic Failover**: Switches to a different account when the current one runs out of credits
- **Billing-Aware Routing**: Designate one account as "overage" account for fallback
- **Hourly Health Checks**: Periodically checks if accounts have credits
- **Immediate Failover**: Detects billing errors and switches accounts immediately
- **In-Memory State**: No persistent state needed, survives restarts
- **Backward Compatible**: Single-account mode still works as before

## Quick Start

### 1. Configuration

Create a `kiro-accounts.json` file:

```json
{
  "accounts": [
    {
      "id": "dj",
      "name": "Dj Account",
      "refreshToken": "eyJ...",
      "profileArn": "arn:aws:codewhisperer:us-east-1:...",
      "region": "us-east-1",
      "overage": false
    },
    {
      "id": "sherra",
      "name": "Sherra Account (Overage)",
      "refreshToken": "eyJ...",
      "profileArn": "arn:aws:codewhisperer:us-east-1:...",
      "region": "us-east-1",
      "overage": true
    }
  ],
  "healthCheckIntervalHours": 1
}
```

### 2. Start the Gateway

```bash
python main.py
```

The gateway will:
1. Load the multi-account configuration
2. Run health checks on all accounts
3. Select the first account with credits
4. Start the hourly health check scheduler

### 3. Check Account Status

```bash
curl -H "Authorization: Bearer my-super-secret-password-123" \
  http://localhost:8000/health/accounts
```

Response:
```json
{
  "current_account": "dj",
  "accounts": {
    "dj": {
      "has_credits": true,
      "last_checked": "2026-04-13T11:15:00",
      "last_error": null,
      "error_count": 0
    },
    "sherra": {
      "has_credits": true,
      "last_checked": "2026-04-13T11:15:00",
      "last_error": null,
      "error_count": 0
    }
  }
}
```

## Configuration

### Configuration File (kiro-accounts.json)

```json
{
  "accounts": [
    {
      "id": "account-id",
      "name": "Display Name",
      "refreshToken": "refresh-token-from-kiro",
      "profileArn": "arn:aws:codewhisperer:region:account:profile/name",
      "region": "us-east-1",
      "overage": false
    }
  ],
  "healthCheckIntervalHours": 1,
  "vpnProxyUrl": "http://127.0.0.1:7890"
}
```

**Fields:**
- `id` (required): Unique identifier for the account
- `name` (optional): Display name for the account
- `refreshToken` (required): Kiro refresh token
- `profileArn` (optional): AWS CodeWhisperer profile ARN
- `region` (optional): AWS region, default: `us-east-1`
- `overage` (optional): Mark as overage account, default: `false`
- `healthCheckIntervalHours` (optional): Health check interval in hours, default: `1`
- `vpnProxyUrl` (optional): VPN/proxy URL for all accounts

### Environment Variables

Alternatively, use environment variables:

```bash
export KIRO_ACCOUNTS_JSON='[
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
export KIRO_HEALTH_CHECK_INTERVAL_HOURS=1
python main.py
```

### Configuration Priority

1. `KIRO_ACCOUNTS_JSON` environment variable
2. `KIRO_ACCOUNTS_FILE` environment variable
3. `./kiro-accounts.json` file
4. Single-account mode (existing `REFRESH_TOKEN`, `PROFILE_ARN`)

## How It Works

### Startup

1. Load multi-account configuration
2. Initialize auth manager for each account
3. Run health check on all accounts
4. Select first account with credits
5. Start hourly health check scheduler

### Request Handling

1. Receive request from client
2. Get current account's auth manager
3. Make API call to Kiro
4. If successful, return response
5. If billing error (`MONTHLY_REQUEST_COUNT`):
   - Mark current account as out of credits
   - Run health check on all accounts
   - Switch to first account with credits
   - Retry request with new account
   - If all out of credits, use overage account

### Hourly Health Check

1. Check all accounts for billing errors
2. Update account state
3. If current account now has credits, switch back
4. If current account still out of credits, stay on fallback

## Account Selection Logic

The gateway uses this priority order to select which account to use:

1. **First account with credits** (in configuration order)
2. **Overage account** if all are out of credits
3. **First account** if no overage account configured

## Billing Error Detection

The gateway detects billing errors by looking for the `MONTHLY_REQUEST_COUNT` error reason in API responses. When detected:

1. Current account is marked as out of credits
2. Error count is incremented
3. All accounts are re-checked
4. Gateway switches to best available account
5. Request is retried with new account

## Docker Deployment

```bash
docker run -d \
  -p 8000:8000 \
  -e KIRO_ACCOUNTS_JSON='[...]' \
  -e KIRO_HEALTH_CHECK_INTERVAL_HOURS=1 \
  -e PROXY_API_KEY="my-super-secret-password-123" \
  --name kiro-gateway-multi \
  ghcr.io/jwadow/kiro-gateway:latest
```

## Systemd Deployment

### Template Unit File

Create `/etc/systemd/system/kiro-gateway@.service`:

```ini
[Unit]
Description=Kiro Gateway - %i
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=kiro
WorkingDirectory=/opt/kiro-gateway
Environment="PATH=/opt/kiro-gateway/.venv/bin"
ExecStart=/opt/kiro-gateway/.venv/bin/python main.py --port %i
EnvironmentFile=/etc/kiro-gateway/%i.env

Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=kiro-gateway-%i

[Install]
WantedBy=multi-user.target
```

### Configuration Files

Create `/etc/kiro-gateway/8000.env`:
```bash
KIRO_ACCOUNTS_JSON='[...]'
KIRO_HEALTH_CHECK_INTERVAL_HOURS=1
PROXY_API_KEY="my-super-secret-password-123"
```

### Enable and Start

```bash
sudo systemctl enable kiro-gateway@8000.service
sudo systemctl start kiro-gateway@8000.service
sudo systemctl status kiro-gateway@8000.service
sudo journalctl -u kiro-gateway@8000.service -f
```

## Monitoring

### Health Status Endpoint

```bash
curl -H "Authorization: Bearer my-super-secret-password-123" \
  http://localhost:8000/health/accounts
```

### Logs

Look for these log messages:

- `AccountManager initialized with N accounts` - Initialization
- `Running initial health check on all accounts...` - Startup health check
- `Initial account selected: account-id` - Account selection
- `Running scheduled health check...` - Hourly health check
- `Billing error on account X: ...` - Billing error detected
- `Switched from X to Y` - Account failover
- `All accounts out of credits, using overage account: X` - Fallback to overage

## Troubleshooting

### No accounts with credits found

**Problem**: Gateway logs "No account with credits found, will use overage account"

**Solution**: 
1. Verify refresh tokens are valid
2. Check that at least one account has credits
3. Run health check manually: `curl http://localhost:8000/health/accounts`

### Billing error not triggering failover

**Problem**: Gateway doesn't switch accounts when one runs out of credits

**Solution**:
1. Check logs for "Billing error on account X"
2. Verify overage account is configured
3. Ensure `overage: true` is set on fallback account

### Health check not running

**Problem**: Hourly health check doesn't seem to run

**Solution**:
1. Check logs for "Running scheduled health check..."
2. Verify `healthCheckIntervalHours` is set correctly
3. Check that HealthChecker task is running

### Single-account mode not working

**Problem**: Gateway doesn't start in single-account mode

**Solution**:
1. Remove `KIRO_ACCOUNTS_JSON` environment variable
2. Remove `kiro-accounts.json` file
3. Set `REFRESH_TOKEN` and `PROFILE_ARN` environment variables
4. Restart gateway

## Implementation Details

### New Files

- `kiro/multi_account_config.py` - Configuration loading and validation
- `kiro/account_manager.py` - Account management and routing logic
- `kiro/health_checker.py` - Periodic health check scheduler

### Modified Files

- `main.py` - Initialize AccountManager and HealthChecker
- `routes_openai.py` - Use AccountManager for routing
- `routes_anthropic.py` - Use AccountManager for routing

### State Management

All state is kept in memory:
- Current active account
- Account health status
- Last health check time
- Error counts

No persistent state files are created. On restart, the gateway re-evaluates which account to use.

## Backward Compatibility

Single-account mode continues to work exactly as before:
- If no multi-account configuration is found, gateway uses existing `REFRESH_TOKEN` and `PROFILE_ARN`
- All existing deployments continue to work without changes
- Multi-account mode is opt-in

## Performance Impact

- **Startup**: +100-200ms for health checks on all accounts
- **Hourly**: +50-100ms for health check task
- **Per-request**: Negligible overhead (just account lookup)
- **Failover**: ~1-2 seconds to detect error and switch accounts

## Security Considerations

- Refresh tokens are stored in configuration files or environment variables
- Ensure configuration files have restricted permissions (600)
- Use environment variables for sensitive deployments
- Health check endpoint returns account status (no sensitive data)

## Future Enhancements

- [ ] Persistent state tracking (optional)
- [ ] Metrics/prometheus integration
- [ ] Account-specific rate limiting
- [ ] Load balancing across accounts
- [ ] Automatic billing cycle detection
- [ ] Account usage tracking and reporting

## Support

For issues or questions:
1. Check the logs: `journalctl -u kiro-gateway@8000.service -f`
2. Check account status: `curl http://localhost:8000/health/accounts`
3. Review configuration: `cat kiro-accounts.json`
4. Open an issue on GitHub

## License

GNU Affero General Public License v3.0 (AGPL-3.0)
