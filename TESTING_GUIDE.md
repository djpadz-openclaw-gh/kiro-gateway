# Multi-Account Kiro Gateway - Testing Guide

## Overview

This guide provides comprehensive testing procedures to verify that multi-account billing-aware failover is working correctly.

## Pre-Testing Setup

### 1. Prepare Test Environment

```bash
# Create test directory
mkdir -p ~/kiro-gateway-test
cd ~/kiro-gateway-test

# Copy gateway code
cp -r /path/to/kiro-gateway .

# Create test configuration
cat > kiro-accounts.json << 'EOF'
{
  "accounts": [
    {
      "id": "account1",
      "name": "Test Account 1",
      "refreshToken": "YOUR_TOKEN_1",
      "profileArn": "YOUR_ARN_1",
      "region": "us-east-1",
      "overage": false
    },
    {
      "id": "account2",
      "name": "Test Account 2",
      "refreshToken": "YOUR_TOKEN_2",
      "profileArn": "YOUR_ARN_2",
      "region": "us-east-1",
      "overage": true
    }
  ],
  "healthCheckIntervalHours": 1
}
EOF
```

### 2. Start Gateway

```bash
# Terminal 1: Start gateway
python main.py

# Wait for startup message:
# "Multi-account mode initialized. Current account: account1"
```

### 3. Prepare Test Client

```bash
# Terminal 2: Set up test variables
export GATEWAY_URL="http://localhost:8000"
export API_KEY="my-super-secret-password-123"
export HEADERS="-H 'Authorization: Bearer $API_KEY' -H 'Content-Type: application/json'"
```

## Test Cases

### Test 1: Configuration Loading

**Objective**: Verify that multi-account configuration loads correctly

**Steps**:
1. Start gateway with kiro-accounts.json
2. Check logs for: "Loaded multi-account configuration with 2 accounts"
3. Check logs for: "AccountManager initialized with 2 accounts"

**Expected Result**: ✓ Configuration loads without errors

**Verification**:
```bash
# Check logs
tail -20 /tmp/kiro-gateway.log | grep -i "multi-account\|account"
```

---

### Test 2: Initial Health Check

**Objective**: Verify that health check runs on startup

**Steps**:
1. Start gateway
2. Wait for startup to complete
3. Check logs for health check results

**Expected Result**: ✓ Health check runs and accounts are checked

**Verification**:
```bash
# Check logs
tail -50 /tmp/kiro-gateway.log | grep -i "health\|initial"
```

---

### Test 3: Account Selection

**Objective**: Verify that correct account is selected on startup

**Steps**:
1. Start gateway
2. Wait for initialization
3. Check health endpoint

**Expected Result**: ✓ First account with credits is selected

**Verification**:
```bash
curl -s $HEADERS $GATEWAY_URL/health/accounts | jq '.current_account'
# Should output: "account1"
```

---

### Test 4: Health Status Endpoint

**Objective**: Verify that health status endpoint returns correct data

**Steps**:
1. Gateway running
2. Call health endpoint
3. Verify response structure

**Expected Result**: ✓ Endpoint returns account status

**Verification**:
```bash
curl -s $HEADERS $GATEWAY_URL/health/accounts | jq '.'
# Should output:
# {
#   "current_account": "account1",
#   "accounts": {
#     "account1": {
#       "has_credits": true,
#       "last_checked": "2026-04-13T11:15:00",
#       "last_error": null,
#       "error_count": 0
#     },
#     "account2": {
#       "has_credits": true,
#       "last_checked": "2026-04-13T11:15:00",
#       "last_error": null,
#       "error_count": 0
#     }
#   }
# }
```

---

### Test 5: Request Routing

**Objective**: Verify that requests route to current account

**Steps**:
1. Gateway running with account1 selected
2. Make API request
3. Verify request succeeds

**Expected Result**: ✓ Request succeeds and routes to account1

**Verification**:
```bash
curl -s $HEADERS -X POST $GATEWAY_URL/v1/chat/completions \
  -d '{
    "model": "claude-sonnet-4-5",
    "messages": [{"role": "user", "content": "Hello"}]
  }' | jq '.choices[0].message.content' | head -c 50
# Should return a response from Claude
```

---

### Test 6: Billing Error Detection

**Objective**: Verify that billing errors are detected

**Steps**:
1. Modify account_manager.py to simulate billing error
2. Make API request
3. Check logs for billing error detection

**Expected Result**: ✓ Billing error is detected and logged

**Verification**:
```bash
# Modify account_manager.py temporarily to force billing error
# Then make a request and check logs
tail -20 /tmp/kiro-gateway.log | grep -i "billing\|monthly_request"
```

---

### Test 7: Account Failover

**Objective**: Verify that gateway switches to another account on billing error

**Steps**:
1. Simulate billing error on account1
2. Make API request
3. Verify account switches to account2
4. Verify request is retried with account2

**Expected Result**: ✓ Gateway switches to account2 and retries request

**Verification**:
```bash
# Check logs for failover
tail -30 /tmp/kiro-gateway.log | grep -i "switched\|failover"
# Should show: "Switched from account1 to account2"

# Check health endpoint
curl -s $HEADERS $GATEWAY_URL/health/accounts | jq '.current_account'
# Should output: "account2"
```

---

### Test 8: Fallback to Overage Account

**Objective**: Verify that gateway falls back to overage account when all others are out of credits

**Steps**:
1. Simulate billing errors on all non-overage accounts
2. Make API request
3. Verify gateway uses overage account

**Expected Result**: ✓ Gateway uses overage account

**Verification**:
```bash
# Check logs
tail -30 /tmp/kiro-gateway.log | grep -i "overage"
# Should show: "All accounts out of credits, using overage account: account2"

# Check health endpoint
curl -s $HEADERS $GATEWAY_URL/health/accounts | jq '.current_account'
# Should output: "account2"
```

---

### Test 9: Hourly Health Check

**Objective**: Verify that hourly health check runs

**Steps**:
1. Gateway running
2. Wait for health check interval (or modify to 1 minute for testing)
3. Check logs for health check execution

**Expected Result**: ✓ Health check runs at scheduled interval

**Verification**:
```bash
# For testing, modify KIRO_HEALTH_CHECK_INTERVAL_HOURS to 0.016 (1 minute)
# Then wait 1 minute and check logs
tail -50 /tmp/kiro-gateway.log | grep -i "scheduled health check"
```

---

### Test 10: Account Recovery

**Objective**: Verify that gateway switches back to primary account when it regains credits

**Steps**:
1. Account1 is out of credits, account2 is active
2. Simulate account1 regaining credits
3. Run health check
4. Verify gateway switches back to account1

**Expected Result**: ✓ Gateway switches back to account1

**Verification**:
```bash
# Check logs for account recovery
tail -30 /tmp/kiro-gateway.log | grep -i "selected\|switched"
# Should show: "Selected account: account1"

# Check health endpoint
curl -s $HEADERS $GATEWAY_URL/health/accounts | jq '.current_account'
# Should output: "account1"
```

---

### Test 11: Single-Account Mode Compatibility

**Objective**: Verify that single-account mode still works

**Steps**:
1. Remove kiro-accounts.json
2. Set REFRESH_TOKEN and PROFILE_ARN environment variables
3. Start gateway
4. Make API request

**Expected Result**: ✓ Gateway works in single-account mode

**Verification**:
```bash
# Check logs
tail -20 /tmp/kiro-gateway.log | grep -i "single-account"
# Should show: "Initializing single-account mode..."

# Make request
curl -s $HEADERS -X POST $GATEWAY_URL/v1/chat/completions \
  -d '{"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "Hello"}]}' \
  | jq '.choices[0].message.content' | head -c 50
```

---

### Test 12: Streaming Requests

**Objective**: Verify that streaming requests work with multi-account

**Steps**:
1. Gateway running with multi-account
2. Make streaming request
3. Verify stream completes successfully

**Expected Result**: ✓ Streaming request works

**Verification**:
```bash
curl -s $HEADERS -X POST $GATEWAY_URL/v1/chat/completions \
  -d '{
    "model": "claude-sonnet-4-5",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }' | head -20
# Should show SSE stream events
```

---

### Test 13: Error Handling

**Objective**: Verify that errors are handled gracefully

**Steps**:
1. Make request with invalid model
2. Make request with invalid API key
3. Make request with malformed JSON

**Expected Result**: ✓ Errors are handled and returned to client

**Verification**:
```bash
# Invalid model
curl -s $HEADERS -X POST $GATEWAY_URL/v1/chat/completions \
  -d '{"model": "invalid-model", "messages": [{"role": "user", "content": "Hello"}]}' \
  | jq '.error'

# Invalid API key
curl -s -H "Authorization: Bearer invalid-key" -X POST $GATEWAY_URL/v1/chat/completions \
  -d '{"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "Hello"}]}' \
  | jq '.error'
```

---

### Test 14: Concurrent Requests

**Objective**: Verify that concurrent requests are handled correctly

**Steps**:
1. Make multiple concurrent requests
2. Verify all requests succeed
3. Verify all route to same account

**Expected Result**: ✓ Concurrent requests handled correctly

**Verification**:
```bash
# Make 5 concurrent requests
for i in {1..5}; do
  curl -s $HEADERS -X POST $GATEWAY_URL/v1/chat/completions \
    -d '{"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "Hello"}]}' \
    > /tmp/response_$i.json &
done
wait

# Check all responses
for i in {1..5}; do
  jq '.choices[0].message.content' /tmp/response_$i.json | head -c 20
  echo ""
done
```

---

### Test 15: Configuration Reload

**Objective**: Verify that configuration can be reloaded

**Steps**:
1. Gateway running
2. Modify kiro-accounts.json
3. Restart gateway
4. Verify new configuration is loaded

**Expected Result**: ✓ New configuration is loaded on restart

**Verification**:
```bash
# Modify kiro-accounts.json
# Restart gateway
# Check logs for new configuration
tail -20 /tmp/kiro-gateway.log | grep -i "loaded\|account"
```

---

## Performance Tests

### Test P1: Startup Time

**Objective**: Measure gateway startup time

**Steps**:
1. Time gateway startup
2. Record time to first request

**Expected Result**: < 5 seconds

**Verification**:
```bash
time python main.py &
# Wait for "Gateway started successfully"
# Record time
```

---

### Test P2: Request Latency

**Objective**: Measure request latency with multi-account

**Steps**:
1. Make 100 requests
2. Measure average latency
3. Compare with single-account mode

**Expected Result**: < 100ms overhead

**Verification**:
```bash
time for i in {1..100}; do
  curl -s $HEADERS -X POST $GATEWAY_URL/v1/chat/completions \
    -d '{"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "Hi"}]}' \
    > /dev/null
done
```

---

### Test P3: Health Check Overhead

**Objective**: Measure health check overhead

**Steps**:
1. Monitor CPU/memory during health check
2. Verify minimal impact

**Expected Result**: < 5% CPU spike

**Verification**:
```bash
# Monitor during health check
watch -n 1 'ps aux | grep python | grep main'
```

---

## Stress Tests

### Test S1: High Request Volume

**Objective**: Verify gateway handles high request volume

**Steps**:
1. Send 1000 requests rapidly
2. Verify all succeed
3. Check for errors or timeouts

**Expected Result**: ✓ All requests succeed

**Verification**:
```bash
# Send 1000 requests
for i in {1..1000}; do
  curl -s $HEADERS -X POST $GATEWAY_URL/v1/chat/completions \
    -d '{"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "Hi"}]}' \
    > /dev/null &
done
wait
```

---

### Test S2: Long-Running Requests

**Objective**: Verify gateway handles long-running requests

**Steps**:
1. Make request with long prompt
2. Verify request completes
3. Check for timeouts

**Expected Result**: ✓ Request completes successfully

**Verification**:
```bash
curl -s $HEADERS -X POST $GATEWAY_URL/v1/chat/completions \
  -d '{"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "Write a 1000 word essay on..."}]}' \
  | jq '.choices[0].message.content' | wc -c
```

---

## Test Summary

| Test | Status | Notes |
|------|--------|-------|
| Configuration Loading | ✓ | |
| Initial Health Check | ✓ | |
| Account Selection | ✓ | |
| Health Status Endpoint | ✓ | |
| Request Routing | ✓ | |
| Billing Error Detection | ✓ | |
| Account Failover | ✓ | |
| Fallback to Overage | ✓ | |
| Hourly Health Check | ✓ | |
| Account Recovery | ✓ | |
| Single-Account Mode | ✓ | |
| Streaming Requests | ✓ | |
| Error Handling | ✓ | |
| Concurrent Requests | ✓ | |
| Configuration Reload | ✓ | |
| Startup Time | ✓ | < 5s |
| Request Latency | ✓ | < 100ms |
| Health Check Overhead | ✓ | < 5% CPU |
| High Request Volume | ✓ | |
| Long-Running Requests | ✓ | |

## Troubleshooting Failed Tests

### If Test Fails

1. **Check logs**: `tail -100 /tmp/kiro-gateway.log`
2. **Check configuration**: `cat kiro-accounts.json | jq '.'`
3. **Check health endpoint**: `curl http://localhost:8000/health/accounts`
4. **Check credentials**: Verify refresh tokens are valid
5. **Check network**: Verify gateway can reach Kiro API

### Common Issues

- **"No account with credits found"**: Verify refresh tokens are valid
- **"Billing error on account X"**: This is expected, verify failover works
- **"Health check failed"**: Check refresh token validity
- **"Could not switch accounts"**: Verify overage account is configured

## Test Automation

Create a test script to automate all tests:

```bash
#!/bin/bash

# Run all tests
echo "Running multi-account tests..."

# Test 1: Configuration
echo "Test 1: Configuration Loading..."
# ... test code ...

# Test 2: Health Check
echo "Test 2: Initial Health Check..."
# ... test code ...

# ... more tests ...

echo "All tests completed!"
```

## Conclusion

This testing guide provides comprehensive coverage of multi-account functionality. Run through all tests to verify the implementation is working correctly before deploying to production.
