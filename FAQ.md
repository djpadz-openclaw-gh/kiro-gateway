# Multi-Account Kiro Gateway - FAQ

## General Questions

### Q: What is multi-account billing-aware failover?

**A:** It's a feature that allows you to run multiple Kiro accounts in a single gateway instance. When one account runs out of credits, the gateway automatically switches to another account. This enables cost optimization by staggering billing cycles and using overage accounts as fallback.

### Q: Why would I need this?

**A:** If you have multiple Kiro accounts with different billing cycles, you can:
- Stagger billing dates to spread costs
- Use one account for regular usage
- Use another account with overages enabled as fallback
- Automatically switch when the primary account runs out of credits
- Avoid paying overage charges until necessary

### Q: Is this backward compatible?

**A:** Yes! Single-account mode still works exactly as before. Multi-account is opt-in. If you don't configure multiple accounts, the gateway works in single-account mode.

### Q: How does it detect when an account runs out of credits?

**A:** It looks for the `MONTHLY_REQUEST_COUNT` error in API responses from Kiro. When detected, it marks that account as out of credits and switches to another account.

### Q: What happens if all accounts run out of credits?

**A:** The gateway falls back to the account marked as `overage: true`. This account should have overages enabled so requests continue to work (but incur overage charges).

---

## Configuration Questions

### Q: How do I configure multiple accounts?

**A:** Create a `kiro-accounts.json` file with your account configurations:

```json
{
  "accounts": [
    {
      "id": "account1",
      "refreshToken": "...",
      "profileArn": "...",
      "overage": false
    },
    {
      "id": "account2",
      "refreshToken": "...",
      "profileArn": "...",
      "overage": true
    }
  ],
  "healthCheckIntervalHours": 1
}
```

### Q: Can I use environment variables instead of a config file?

**A:** Yes! Set `KIRO_ACCOUNTS_JSON` environment variable with a JSON array of accounts.

### Q: What's the difference between `overage: true` and `overage: false`?

**A:** 
- `overage: false` - Primary account, used first. Should have credits.
- `overage: true` - Fallback account, used when others run out. Should have overages enabled.

### Q: Can I have multiple overage accounts?

**A:** You can mark multiple accounts as overage, but only one will be used as the fallback. The first one marked as overage will be used.

### Q: What if I don't mark any account as overage?

**A:** The gateway will log a warning and use the first account as fallback. It's recommended to mark at least one account as overage.

### Q: How do I get the refresh token?

**A:** 
1. Log in to Kiro IDE
2. Check `~/.aws/sso/cache/kiro-auth-token.json`
3. Copy the `refreshToken` field

### Q: How do I get the profile ARN?

**A:** 
1. Log in to Kiro IDE
2. Go to account settings
3. Copy the profile ARN
4. Or check `~/.aws/sso/cache/kiro-auth-token.json` for `profileArn`

---

## Deployment Questions

### Q: How do I deploy this?

**A:** You can deploy using:
- **Docker**: `docker run -e KIRO_ACCOUNTS_JSON='[...]' ...`
- **Systemd**: Create a systemd unit file
- **Standalone**: `python main.py`

See MULTI_ACCOUNT_README.md for detailed deployment instructions.

### Q: Can I run multiple instances on the same host?

**A:** Yes! Use the systemd template unit file to run multiple instances on different ports:
```bash
sudo systemctl start kiro-gateway@8000.service
sudo systemctl start kiro-gateway@8001.service
```

### Q: How do I monitor the gateway?

**A:** 
1. Check health endpoint: `curl http://localhost:8000/health/accounts`
2. Check logs: `journalctl -u kiro-gateway@8000.service -f`
3. Monitor CPU/memory: `top` or `htop`

### Q: What's the performance impact?

**A:** 
- Startup: +100-200ms for health checks
- Per-request: Negligible overhead
- Hourly: +50-100ms for health check task
- Failover: ~1-2 seconds to detect and switch

---

## Troubleshooting Questions

### Q: Gateway won't start

**A:** Check logs for errors:
```bash
python main.py 2>&1 | head -50
```

Common issues:
- Invalid JSON in kiro-accounts.json
- Invalid refresh tokens
- Missing required fields

### Q: No account selected

**A:** Check logs for:
```bash
tail -50 /tmp/kiro-gateway.log | grep -i "selected\|health"
```

Verify:
- At least one account has valid credentials
- Health check ran successfully
- Refresh tokens are correct

### Q: Requests fail with 401

**A:** 
- Verify PROXY_API_KEY matches client's Authorization header
- Check that refresh tokens are valid
- Verify account has access to Kiro API

### Q: Health endpoint returns error

**A:** 
- Verify AccountManager is initialized
- Check that kiro-accounts.json exists and is valid
- Check logs for configuration errors

### Q: Billing error not triggering failover

**A:** 
- Check logs for "Billing error on account X"
- Verify overage account is configured
- Ensure `overage: true` is set on fallback account

### Q: Health check not running

**A:** 
- Check logs for "Running scheduled health check..."
- Verify `healthCheckIntervalHours` is set correctly
- Check that HealthChecker task is running

### Q: Single-account mode not working

**A:** 
- Remove `KIRO_ACCOUNTS_JSON` environment variable
- Remove `kiro-accounts.json` file
- Set `REFRESH_TOKEN` and `PROFILE_ARN` environment variables
- Restart gateway

---

## Security Questions

### Q: Is it safe to store refresh tokens in config files?

**A:** 
- Restrict file permissions: `chmod 600 kiro-accounts.json`
- Use environment variables for sensitive deployments
- Rotate refresh tokens regularly
- Don't commit config files to version control

### Q: Can I use environment variables instead of config files?

**A:** Yes! Set `KIRO_ACCOUNTS_JSON` environment variable. This is more secure for production deployments.

### Q: What data does the health endpoint expose?

**A:** The health endpoint returns:
- Current active account
- Whether each account has credits
- Last health check time
- Error information

It does NOT expose:
- Refresh tokens
- Profile ARNs
- Sensitive credentials

### Q: How do I secure the gateway?

**A:** 
1. Use strong PROXY_API_KEY
2. Restrict file permissions on config files
3. Use environment variables for credentials
4. Run behind a firewall
5. Use HTTPS in production
6. Monitor for unusual activity

---

## Performance Questions

### Q: How often should I run health checks?

**A:** 
- Default: 1 hour
- For faster failover: 30 minutes
- For less overhead: 2-4 hours
- Adjust based on your needs

### Q: What's the latency impact?

**A:** Negligible - just an account lookup per request. < 1ms overhead.

### Q: Can I handle high request volume?

**A:** Yes! The gateway is designed to handle high volume. Performance is limited by:
- Kiro API rate limits
- Network bandwidth
- Server resources

### Q: How many accounts can I have?

**A:** Theoretically unlimited, but practically:
- 2-3 accounts: Recommended
- 5+ accounts: May need to adjust health check interval
- 10+ accounts: Consider multiple gateway instances

---

## Integration Questions

### Q: How do I integrate this into my existing gateway?

**A:** 
1. Copy 3 Python files to kiro/ directory
2. Modify main.py (see EXAMPLE_MODIFICATIONS.md)
3. Modify routes_openai.py (see EXAMPLE_MODIFICATIONS.md)
4. Modify routes_anthropic.py (see EXAMPLE_MODIFICATIONS.md)
5. Create kiro-accounts.json configuration
6. Test with `python main.py`

See QUICK_START.md for step-by-step instructions.

### Q: Do I need to modify my client code?

**A:** No! The gateway is transparent to clients. Clients don't need to know about multi-account failover.

### Q: Can I use this with existing single-account deployments?

**A:** Yes! Multi-account is opt-in. Existing deployments continue to work without changes.

### Q: How do I migrate from single-account to multi-account?

**A:** 
1. Follow integration steps above
2. Create kiro-accounts.json with your existing account
3. Add second account to config
4. Restart gateway
5. Verify both accounts work

---

## Monitoring Questions

### Q: How do I monitor account status?

**A:** Use the health endpoint:
```bash
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8000/health/accounts
```

### Q: How do I know when an account runs out of credits?

**A:** 
1. Check logs for "Billing error on account X"
2. Check health endpoint for `has_credits: false`
3. Set up monitoring/alerts on health endpoint

### Q: Can I get metrics/prometheus integration?

**A:** Not yet, but it's planned for future versions. For now, use logs and health endpoint.

### Q: How do I set up alerts?

**A:** 
1. Monitor health endpoint periodically
2. Alert if `has_credits: false` for all accounts
3. Alert if `error_count` increases
4. Alert if gateway doesn't respond

---

## Billing Questions

### Q: How does this save money?

**A:** 
- Stagger billing cycles to spread costs
- Use primary account until it runs out
- Use overage account only when necessary
- Avoid paying overage charges until needed

### Q: Can I track usage per account?

**A:** Not yet, but you can:
- Check logs for account switches
- Monitor health endpoint for error counts
- Implement custom monitoring

### Q: How do I know which account is being used?

**A:** 
1. Check health endpoint: `curl http://localhost:8000/health/accounts`
2. Check logs: `grep "current_account\|switched" /var/log/kiro-gateway.log`
3. Check logs: `grep "Switched from\|Selected account" /var/log/kiro-gateway.log`

---

## Advanced Questions

### Q: Can I customize the failover logic?

**A:** Yes! Modify `account_manager.py` to implement custom logic:
- Different account selection strategy
- Custom billing error detection
- Custom health check logic

### Q: Can I use this with multiple gateway instances?

**A:** Yes! Each instance can have its own multi-account configuration. They operate independently.

### Q: Can I load balance across multiple gateways?

**A:** Yes! Use a load balancer (nginx, HAProxy, etc.) to distribute requests across multiple gateway instances.

### Q: Can I use this with a proxy/VPN?

**A:** Yes! Set `vpnProxyUrl` in configuration to route all requests through a proxy.

---

## Getting Help

### Q: Where can I find more information?

**A:** 
- **MULTI_ACCOUNT_README.md** - Comprehensive user guide
- **QUICK_START.md** - 5-minute setup guide
- **INTEGRATION_GUIDE.md** - Integration instructions
- **TESTING_GUIDE.md** - Testing procedures
- **EXAMPLE_MODIFICATIONS.md** - Code examples

### Q: How do I report a bug?

**A:** 
1. Check logs for error messages
2. Check health endpoint for status
3. Verify configuration is correct
4. Open an issue on GitHub with:
   - Error message
   - Configuration (without credentials)
   - Steps to reproduce

### Q: How do I request a feature?

**A:** Open an issue on GitHub with:
- Feature description
- Use case
- Why it's needed

---

## Conclusion

For more information, see:
- **MULTI_ACCOUNT_README.md** - Complete user guide
- **QUICK_START.md** - Quick setup guide
- **TESTING_GUIDE.md** - Testing procedures
- **INTEGRATION_GUIDE.md** - Integration instructions
