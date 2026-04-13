# Multi-Account Kiro Gateway - Quick Start Guide

## 5-Minute Setup

### Step 1: Prepare Your Credentials

Get your Kiro refresh tokens and profile ARNs:
- Log in to Kiro IDE
- Get refresh token from `~/.aws/sso/cache/kiro-auth-token.json`
- Get profile ARN from your Kiro account settings

### Step 2: Create Configuration File

Create `kiro-accounts.json`:

```json
{
  "accounts": [
    {
      "id": "dj",
      "name": "Dj Account",
      "refreshToken": "YOUR_DJ_REFRESH_TOKEN_HERE",
      "profileArn": "arn:aws:codewhisperer:us-east-1:123456789012:profile/default",
      "region": "us-east-1",
      "overage": false
    },
    {
      "id": "sherra",
      "name": "Sherra Account (Overage)",
      "refreshToken": "YOUR_SHERRA_REFRESH_TOKEN_HERE",
      "profileArn": "arn:aws:codewhisperer:us-east-1:123456789012:profile/default",
      "region": "us-east-1",
      "overage": true
    }
  ],
  "healthCheckIntervalHours": 1
}
```

### Step 3: Copy Implementation Files

```bash
# Copy the three new Python files to kiro/ directory
cp kiro/multi_account_config.py /path/to/kiro-gateway/kiro/
cp kiro/account_manager.py /path/to/kiro-gateway/kiro/
cp kiro/health_checker.py /path/to/kiro-gateway/kiro/
```

### Step 4: Modify main.py

Add these imports at the top:

```python
from kiro.multi_account_config import load_multi_account_config
from kiro.account_manager import AccountManager
from kiro.health_checker import HealthChecker
```

Replace the lifespan context manager with the one from EXAMPLE_MODIFICATIONS.md.

Add the health status endpoint:

```python
@app.get("/health/accounts")
async def health_accounts(request: Request):
    if request.app.state.account_manager:
        return request.app.state.account_manager.get_account_status()
    else:
        return {"mode": "single-account", "status": "ok"}
```

### Step 5: Modify routes_openai.py

In the `chat_completions` function, replace the auth manager initialization:

```python
# OLD:
auth_manager: KiroAuthManager = request.app.state.auth_manager

# NEW:
if request.app.state.account_manager:
    auth_manager = request.app.state.account_manager.get_current_auth_manager()
    account_manager = request.app.state.account_manager
else:
    auth_manager = request.app.state.auth_manager
    account_manager = None
```

Add error handling for billing errors (see EXAMPLE_MODIFICATIONS.md for full code).

### Step 6: Modify routes_anthropic.py

Same changes as routes_openai.py.

### Step 7: Test

```bash
# Start the gateway
python main.py

# In another terminal, check account status
curl -H "Authorization: Bearer my-super-secret-password-123" \
  http://localhost:8000/health/accounts

# Make a test request
curl -H "Authorization: Bearer my-super-secret-password-123" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "Hello"}]}' \
  http://localhost:8000/v1/chat/completions
```

## Verification Checklist

- [ ] Configuration file created with correct tokens
- [ ] Python files copied to kiro/ directory
- [ ] main.py modified with imports and lifespan
- [ ] routes_openai.py modified with AccountManager
- [ ] routes_anthropic.py modified with AccountManager
- [ ] Gateway starts without errors
- [ ] Health endpoint returns account status
- [ ] Test request succeeds
- [ ] Logs show "Initial account selected: dj"

## Troubleshooting

### Gateway won't start
- Check logs: `python main.py 2>&1 | head -50`
- Verify kiro-accounts.json is valid JSON
- Verify refresh tokens are correct

### Health endpoint returns error
- Check that AccountManager is initialized
- Verify KIRO_ACCOUNTS_JSON or kiro-accounts.json exists
- Check logs for configuration errors

### Requests fail with 401
- Verify PROXY_API_KEY matches client's Authorization header
- Check that refresh tokens are valid

### No account selected
- Check logs for "Initial account selected"
- Verify at least one account has valid credentials
- Check that health check ran successfully

## Next Steps

1. **Deploy to production** - Use Docker or systemd
2. **Monitor** - Check health endpoint regularly
3. **Test failover** - Manually mark account as out of credits to test
4. **Optimize** - Adjust health check interval if needed

## Getting Help

- Check **MULTI_ACCOUNT_README.md** for comprehensive guide
- Check **INTEGRATION_GUIDE.md** for detailed integration steps
- Check **EXAMPLE_MODIFICATIONS.md** for code examples
- Check logs: `tail -f /var/log/kiro-gateway.log`
- Check health: `curl http://localhost:8000/health/accounts`

## Common Issues

### Issue: "No account with credits found"
**Solution**: Verify refresh tokens are valid and accounts have credits

### Issue: "Billing error on account X"
**Solution**: This is expected when account runs out of credits. Gateway will switch to another account.

### Issue: "Health check failed for account X"
**Solution**: Check that refresh token is valid and account is accessible

### Issue: "Could not switch accounts"
**Solution**: Verify overage account is configured and has overages enabled

## Performance Tips

- Set `healthCheckIntervalHours` to 1 for hourly checks
- Increase to 2-4 hours if you have many accounts
- Decrease to 30 minutes if you need faster failover detection

## Security Tips

- Restrict permissions on kiro-accounts.json: `chmod 600 kiro-accounts.json`
- Use environment variables for sensitive deployments
- Rotate refresh tokens regularly
- Monitor health endpoint for unusual activity

## What's Next?

Once you have multi-account working:

1. **Deploy to production** using Docker or systemd
2. **Set up monitoring** to track account usage
3. **Configure alerts** for billing errors
4. **Test failover** to ensure it works as expected
5. **Optimize** health check interval based on your needs

That's it! You now have multi-account billing-aware failover working.
