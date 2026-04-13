# -*- coding: utf-8 -*-

"""
Integration guide for multi-account support in Kiro Gateway.

This document shows how to integrate AccountManager and HealthChecker
into the existing Kiro Gateway code.
"""

# ============================================================================
# MAIN.PY MODIFICATIONS
# ============================================================================

"""
Changes needed in main.py:

1. Import new modules:
   from kiro.multi_account_config import load_multi_account_config
   from kiro.account_manager import AccountManager
   from kiro.health_checker import HealthChecker

2. In the lifespan context manager, add:

   @asynccontextmanager
   async def lifespan(app: FastAPI):
       # Startup
       
       # Try to load multi-account config
       multi_account_config = load_multi_account_config()
       
       if multi_account_config:
           # Multi-account mode
           logger.info("Initializing multi-account mode...")
           account_manager = AccountManager(multi_account_config)
           await account_manager.initialize()
           
           health_checker = HealthChecker(
               account_manager,
               interval_hours=multi_account_config.health_check_interval_hours
           )
           await health_checker.start()
           
           app.state.account_manager = account_manager
           app.state.health_checker = health_checker
           app.state.auth_manager = None  # Not used in multi-account mode
       else:
           # Single-account mode (existing behavior)
           logger.info("Initializing single-account mode...")
           auth_manager = KiroAuthManager(...)
           app.state.auth_manager = auth_manager
           app.state.account_manager = None
           app.state.health_checker = None
       
       yield
       
       # Shutdown
       if app.state.account_manager:
           await app.state.health_checker.stop()
           await app.state.account_manager.close()
       elif app.state.auth_manager:
           await app.state.auth_manager.close()

3. Add health status endpoint:

   @app.get("/health/accounts")
   async def health_accounts():
       if app.state.account_manager:
           return app.state.account_manager.get_account_status()
       else:
           return {"mode": "single-account"}
"""

# ============================================================================
# ROUTES MODIFICATIONS
# ============================================================================

"""
Changes needed in routes_openai.py and routes_anthropic.py:

1. Modify the chat_completions/messages endpoint to use AccountManager:

   async def chat_completions(request: Request, request_data: ChatCompletionRequest):
       # Get auth manager (single or multi-account)
       if request.app.state.account_manager:
           auth_manager = request.app.state.account_manager.get_current_auth_manager()
       else:
           auth_manager = request.app.state.auth_manager
       
       # ... existing code ...
       
       # When making the API call:
       try:
           response = await http_client.request_with_retry(...)
       except HTTPException as e:
           # Check if this is a billing error
           if request.app.state.account_manager:
               error_json = e.detail if isinstance(e.detail, dict) else {"message": str(e.detail)}
               switched = await request.app.state.account_manager.handle_billing_error(error_json)
               
               if switched:
                   # Retry with new account
                   auth_manager = request.app.state.account_manager.get_current_auth_manager()
                   response = await http_client.request_with_retry(...)
               else:
                   raise
           else:
               raise

2. For streaming responses, handle billing errors similarly:

   async def stream_wrapper():
       try:
           async for chunk in response.aiter_bytes():
               yield chunk
       except Exception as e:
           if request.app.state.account_manager:
               # Try to extract error info and handle billing error
               error_json = parse_error_from_stream(e)
               await request.app.state.account_manager.handle_billing_error(error_json)
           raise
"""

# ============================================================================
# CONFIGURATION EXAMPLES
# ============================================================================

"""
Example 1: Environment variable configuration

export KIRO_ACCOUNTS_JSON='[
  {
    "id": "dj",
    "refreshToken": "eyJ...",
    "profileArn": "arn:aws:codewhisperer:us-east-1:...",
    "region": "us-east-1",
    "overage": false,
    "name": "Dj Account"
  },
  {
    "id": "sherra",
    "refreshToken": "eyJ...",
    "profileArn": "arn:aws:codewhisperer:us-east-1:...",
    "region": "us-east-1",
    "overage": true,
    "name": "Sherra Account (Overage)"
  }
]'
export KIRO_HEALTH_CHECK_INTERVAL_HOURS=1
python main.py


Example 2: Configuration file (kiro-accounts.json)

{
  "accounts": [
    {
      "id": "dj",
      "refreshToken": "eyJ...",
      "profileArn": "arn:aws:codewhisperer:us-east-1:...",
      "region": "us-east-1",
      "overage": false,
      "name": "Dj Account"
    },
    {
      "id": "sherra",
      "refreshToken": "eyJ...",
      "profileArn": "arn:aws:codewhisperer:us-east-1:...",
      "region": "us-east-1",
      "overage": true,
      "name": "Sherra Account (Overage)"
    }
  ],
  "healthCheckIntervalHours": 1,
  "vpnProxyUrl": "http://127.0.0.1:7890"
}

python main.py


Example 3: Docker with multi-account

docker run -d \\
  -p 8000:8000 \\
  -e KIRO_ACCOUNTS_JSON='[...]' \\
  -e KIRO_HEALTH_CHECK_INTERVAL_HOURS=1 \\
  --name kiro-gateway-multi \\
  ghcr.io/jwadow/kiro-gateway:latest
"""

# ============================================================================
# SYSTEMD TEMPLATE UNIT
# ============================================================================

"""
File: /etc/systemd/system/kiro-gateway@.service

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

# Multi-account configuration
EnvironmentFile=/etc/kiro-gateway/%i.env

Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=kiro-gateway-%i

[Install]
WantedBy=multi-user.target


Usage:

# Create config files
sudo mkdir -p /etc/kiro-gateway
sudo tee /etc/kiro-gateway/8000.env > /dev/null <<EOF
KIRO_ACCOUNTS_JSON='[...]'
KIRO_HEALTH_CHECK_INTERVAL_HOURS=1
EOF

sudo tee /etc/kiro-gateway/8001.env > /dev/null <<EOF
KIRO_ACCOUNTS_JSON='[...]'
KIRO_HEALTH_CHECK_INTERVAL_HOURS=1
EOF

# Enable and start services
sudo systemctl enable kiro-gateway@8000.service
sudo systemctl enable kiro-gateway@8001.service
sudo systemctl start kiro-gateway@8000.service
sudo systemctl start kiro-gateway@8001.service

# Check status
sudo systemctl status kiro-gateway@8000.service
sudo systemctl status kiro-gateway@8001.service

# View logs
sudo journalctl -u kiro-gateway@8000.service -f
"""

# ============================================================================
# TESTING
# ============================================================================

"""
Manual testing steps:

1. Start gateway with multi-account config:
   python main.py

2. Check account status:
   curl -H "Authorization: Bearer my-super-secret-password-123" \\
     http://localhost:8000/health/accounts

3. Make a request:
   curl -H "Authorization: Bearer my-super-secret-password-123" \\
     -H "Content-Type: application/json" \\
     -d '{"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "Hello"}]}' \\
     http://localhost:8000/v1/chat/completions

4. Simulate billing error by manually marking account as out of credits:
   - Edit account_manager.py to force a billing error
   - Or wait for actual billing error from Kiro API
   - Verify that gateway switches to secondary account

5. Verify health check runs:
   - Check logs for "Running scheduled health check..."
   - Verify account status changes after health check
"""
