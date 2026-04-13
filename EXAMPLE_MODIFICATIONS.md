# -*- coding: utf-8 -*-

"""
Example: Modified routes_openai.py with multi-account support.

This shows how to modify the chat_completions endpoint to use AccountManager
and handle billing errors with automatic failover.

Key changes:
1. Get auth manager from AccountManager if available
2. Catch billing errors and trigger account switching
3. Retry request with new account if switched
"""

# Example of modified chat_completions endpoint:

async def chat_completions(request: Request, request_data: ChatCompletionRequest):
    """
    Chat completions endpoint - compatible with OpenAI API.
    
    With multi-account support and billing-aware failover.
    """
    logger.info(f"Request to /v1/chat/completions (model={request_data.model}, stream={request_data.stream})")
    
    # Get auth manager (works with both single and multi-account modes)
    if request.app.state.account_manager:
        auth_manager = request.app.state.account_manager.get_current_auth_manager()
        account_manager = request.app.state.account_manager
    else:
        auth_manager = request.app.state.auth_manager
        account_manager = None
    
    model_cache: ModelInfoCache = request.app.state.model_cache
    
    # ... existing truncation recovery code ...
    
    # Generate conversation ID for Kiro API
    conversation_id = generate_conversation_id()
    
    # Build payload for Kiro
    profile_arn_for_payload = ""
    if auth_manager.auth_type == AuthType.KIRO_DESKTOP and auth_manager.profile_arn:
        profile_arn_for_payload = auth_manager.profile_arn
    
    try:
        kiro_payload = build_kiro_payload(
            request_data,
            conversation_id,
            profile_arn_for_payload
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Make the API request with retry logic
    max_retries = 2 if account_manager else 1
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Get current auth manager (may have changed due to failover)
            if account_manager:
                auth_manager = account_manager.get_current_auth_manager()
            
            # Make the API call
            async with KiroHttpClient(auth_manager) as http_client:
                if request_data.stream:
                    # Streaming response
                    response = await http_client.request_with_retry(
                        "POST",
                        f"{auth_manager.api_host}/generateAssistantResponse",
                        json=kiro_payload,
                        headers={"Accept": "text/event-stream"},
                        timeout=STREAMING_READ_TIMEOUT
                    )
                    
                    async def stream_wrapper():
                        try:
                            async for chunk in response.aiter_bytes():
                                yield chunk
                        except Exception as e:
                            logger.error(f"Streaming error: {e}")
                            raise
                    
                    return StreamingResponse(
                        stream_wrapper(),
                        media_type="text/event-stream",
                        headers={"Cache-Control": "no-cache"}
                    )
                else:
                    # Non-streaming response
                    response = await http_client.request_with_retry(
                        "POST",
                        f"{auth_manager.api_host}/generateAssistantResponse",
                        json=kiro_payload,
                        timeout=STREAMING_READ_TIMEOUT
                    )
                    
                    response_data = response.json()
                    return JSONResponse(response_data)
        
        except HTTPException as e:
            last_error = e
            
            # Check if this is a billing error
            if account_manager and attempt < max_retries - 1:
                try:
                    error_detail = e.detail
                    if isinstance(error_detail, str):
                        # Try to parse as JSON
                        try:
                            error_json = json.loads(error_detail)
                        except:
                            error_json = {"message": error_detail}
                    else:
                        error_json = error_detail if isinstance(error_detail, dict) else {"message": str(error_detail)}
                    
                    # Check if this is a billing error and try to switch accounts
                    switched = await account_manager.handle_billing_error(error_json)
                    
                    if switched:
                        logger.info(f"Retrying request with new account (attempt {attempt + 2}/{max_retries})")
                        continue
                except Exception as switch_error:
                    logger.error(f"Error handling billing error: {switch_error}")
            
            # If we get here, we couldn't switch or it's not a billing error
            raise last_error
        
        except Exception as e:
            logger.error(f"Unexpected error in chat_completions: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Should not reach here
    if last_error:
        raise last_error
    raise HTTPException(status_code=500, detail="Unknown error")


# Example of modified main.py lifespan:

from contextlib import asynccontextmanager
from kiro.multi_account_config import load_multi_account_config
from kiro.account_manager import AccountManager
from kiro.health_checker import HealthChecker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    
    Handles startup and shutdown of auth managers and health checker.
    Supports both single-account and multi-account modes.
    """
    # Startup
    logger.info("Starting Kiro Gateway...")
    
    # Try to load multi-account configuration
    multi_account_config = load_multi_account_config()
    
    if multi_account_config:
        # Multi-account mode
        logger.info(f"Initializing multi-account mode with {len(multi_account_config.accounts)} accounts")
        
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
        
        logger.info(f"Multi-account mode initialized. Current account: {account_manager.current_account_id}")
    
    else:
        # Single-account mode (existing behavior)
        logger.info("Initializing single-account mode...")
        
        auth_manager = KiroAuthManager(
            refresh_token=REFRESH_TOKEN,
            profile_arn=PROFILE_ARN,
            region=REGION,
            vpn_proxy_url=VPN_PROXY_URL
        )
        
        app.state.auth_manager = auth_manager
        app.state.account_manager = None
        app.state.health_checker = None
    
    # Initialize model cache
    model_cache = ModelInfoCache(
        auth_manager=app.state.auth_manager or app.state.account_manager.get_current_auth_manager(),
        hidden_models=HIDDEN_MODELS,
        model_aliases=MODEL_ALIASES,
        hidden_from_list=HIDDEN_FROM_LIST,
        fallback_models=FALLBACK_MODELS
    )
    app.state.model_cache = model_cache
    
    logger.info("Kiro Gateway started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Kiro Gateway...")
    
    if app.state.account_manager:
        await app.state.health_checker.stop()
        await app.state.account_manager.close()
    elif app.state.auth_manager:
        await app.state.auth_manager.close()
    
    logger.info("Kiro Gateway shut down")


# Add health status endpoint to main.py:

@app.get("/health/accounts")
async def health_accounts(request: Request):
    """
    Get status of all accounts (multi-account mode only).
    
    Returns account status including which account is currently active,
    whether each account has credits, and error information.
    """
    if request.app.state.account_manager:
        return request.app.state.account_manager.get_account_status()
    else:
        return {
            "mode": "single-account",
            "status": "ok"
        }
