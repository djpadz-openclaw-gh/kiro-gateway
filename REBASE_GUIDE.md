# Multi-Account Kiro Gateway - Rebase Guide

## Overview

This guide explains how to handle rebases when pulling updates from the upstream Kiro gateway repository. The multi-account implementation is organized to minimize conflicts and make re-application straightforward.

---

## Architecture for Rebase Survival

### New Files (No Conflicts)
These files are new additions and will never conflict during rebases:
- `kiro/multi_account_config.py`
- `kiro/account_manager.py`
- `kiro/health_checker.py`

**Action on rebase**: No action needed. These files merge cleanly.

### Modified Files (Clearly Marked)
These files have modifications that are clearly marked with comments:
- `main.py`
- `routes_openai.py`
- `routes_anthropic.py`

**Action on rebase**: Re-apply modifications using the markers below.

### Documentation Files (No Conflicts)
These are new documentation files:
- All `.md` files in root directory
- All example configuration files

**Action on rebase**: No action needed. These files merge cleanly.

---

## Modification Markers

All modifications are marked with clear comment blocks:

```python
# ============================================================================
# MULTI-ACCOUNT MODIFICATION START
# ============================================================================
# Description of what this modification does
# See: REBASE_GUIDE.md for details

# ... modification code ...

# ============================================================================
# MULTI-ACCOUNT MODIFICATION END
# ============================================================================
```

This makes it easy to:
1. Find all modifications in a file
2. Identify what each modification does
3. Re-apply after rebasing

---

## Rebase Workflow

### Step 1: Prepare for Rebase

```bash
# Make sure you're on your fork's main branch
git checkout main

# Ensure all changes are committed
git status

# Create a backup branch (optional but recommended)
git branch backup-before-rebase
```

### Step 2: Fetch Upstream Updates

```bash
# Add upstream remote if not already added
git remote add upstream https://github.com/jwadow/kiro-gateway.git

# Fetch latest updates
git fetch upstream

# Check what changed
git log --oneline main..upstream/main
```

### Step 3: Rebase

```bash
# Rebase your fork on top of upstream
git rebase upstream/main

# If conflicts occur, resolve them (see Conflict Resolution below)
```

### Step 4: Re-apply Multi-Account Modifications

If there are conflicts in modified files, use the markers to re-apply:

```bash
# For each modified file with conflicts:
# 1. Open the file
# 2. Find the MULTI-ACCOUNT MODIFICATION markers
# 3. Re-apply the modifications
# 4. Resolve any conflicts
# 5. Stage the file: git add <file>
```

### Step 5: Complete Rebase

```bash
# After resolving all conflicts
git rebase --continue

# Or abort if something goes wrong
git rebase --abort
```

### Step 6: Verify

```bash
# Test that everything still works
python main.py

# Check health endpoint
curl http://localhost:8000/health/accounts

# Run test suite
# See TESTING_GUIDE.md
```

### Step 7: Push

```bash
# Force push to your fork (since history changed)
git push origin main --force-with-lease
```

---

## Conflict Resolution

### Common Conflict Scenarios

#### Scenario 1: Conflict in main.py

**Problem**: Upstream changed main.py, and you have multi-account modifications

**Solution**:
1. Open main.py
2. Find the conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`)
3. Locate the MULTI-ACCOUNT MODIFICATION markers
4. Keep both the upstream changes AND your modifications
5. Resolve the conflict manually
6. Stage the file: `git add main.py`

**Example**:
```python
# Before (conflict)
<<<<<<< HEAD
# Upstream changes
def lifespan(app: FastAPI):
    # ... upstream code ...
=======
# Your changes
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ============================================================================
    # MULTI-ACCOUNT MODIFICATION START
    # ============================================================================
    # Initialize multi-account support
    multi_account_config = load_multi_account_config()
    # ... your code ...
    # ============================================================================
    # MULTI-ACCOUNT MODIFICATION END
    # ============================================================================
>>>>>>> upstream/main

# After (resolved)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Upstream code integrated with your modifications
    # ============================================================================
    # MULTI-ACCOUNT MODIFICATION START
    # ============================================================================
    # Initialize multi-account support
    multi_account_config = load_multi_account_config()
    # ... your code ...
    # ============================================================================
    # MULTI-ACCOUNT MODIFICATION END
    # ============================================================================
```

#### Scenario 2: Conflict in routes_openai.py

**Problem**: Upstream changed routes_openai.py, and you have multi-account modifications

**Solution**:
1. Open routes_openai.py
2. Find the conflict markers
3. Locate the MULTI-ACCOUNT MODIFICATION markers
4. Keep both the upstream changes AND your modifications
5. Ensure the modifications are in the right place in the function
6. Stage the file: `git add routes_openai.py`

#### Scenario 3: No Conflicts (Best Case)

**Problem**: Upstream changes don't overlap with your modifications

**Solution**: No action needed. Rebase completes automatically.

---

## File-by-File Modification Locations

### main.py

**Modification 1: Imports**
```python
# Location: Top of file, after existing imports
# ============================================================================
# MULTI-ACCOUNT MODIFICATION START
# ============================================================================
from kiro.multi_account_config import load_multi_account_config
from kiro.account_manager import AccountManager
from kiro.health_checker import HealthChecker
# ============================================================================
# MULTI-ACCOUNT MODIFICATION END
# ============================================================================
```

**Modification 2: Lifespan Context Manager**
```python
# Location: In the lifespan() function
# ============================================================================
# MULTI-ACCOUNT MODIFICATION START
# ============================================================================
# Try to load multi-account configuration
multi_account_config = load_multi_account_config()

if multi_account_config:
    # Multi-account mode
    account_manager = AccountManager(multi_account_config)
    await account_manager.initialize()
    
    health_checker = HealthChecker(
        account_manager,
        interval_hours=multi_account_config.health_check_interval_hours
    )
    await health_checker.start()
    
    app.state.account_manager = account_manager
    app.state.health_checker = health_checker
    app.state.auth_manager = None
else:
    # Single-account mode (existing code)
    auth_manager = KiroAuthManager(...)
    app.state.auth_manager = auth_manager
    app.state.account_manager = None
    app.state.health_checker = None
# ============================================================================
# MULTI-ACCOUNT MODIFICATION END
# ============================================================================
```

**Modification 3: Shutdown**
```python
# Location: In the lifespan() function, shutdown section
# ============================================================================
# MULTI-ACCOUNT MODIFICATION START
# ============================================================================
if app.state.account_manager:
    await app.state.health_checker.stop()
    await app.state.account_manager.close()
elif app.state.auth_manager:
    await app.state.auth_manager.close()
# ============================================================================
# MULTI-ACCOUNT MODIFICATION END
# ============================================================================
```

**Modification 4: Health Status Endpoint**
```python
# Location: After existing endpoints
# ============================================================================
# MULTI-ACCOUNT MODIFICATION START
# ============================================================================
@app.get("/health/accounts")
async def health_accounts(request: Request):
    """Get status of all accounts (multi-account mode only)."""
    if request.app.state.account_manager:
        return request.app.state.account_manager.get_account_status()
    else:
        return {"mode": "single-account", "status": "ok"}
# ============================================================================
# MULTI-ACCOUNT MODIFICATION END
# ============================================================================
```

### routes_openai.py

**Modification 1: Auth Manager Selection**
```python
# Location: In chat_completions() function, after getting auth_manager
# ============================================================================
# MULTI-ACCOUNT MODIFICATION START
# ============================================================================
# Get auth manager (works with both single and multi-account modes)
if request.app.state.account_manager:
    auth_manager = request.app.state.account_manager.get_current_auth_manager()
    account_manager = request.app.state.account_manager
else:
    auth_manager = request.app.state.auth_manager
    account_manager = None
# ============================================================================
# MULTI-ACCOUNT MODIFICATION END
# ============================================================================
```

**Modification 2: Error Handling with Failover**
```python
# Location: In chat_completions() function, in the try/except block
# ============================================================================
# MULTI-ACCOUNT MODIFICATION START
# ============================================================================
# Make the API request with retry logic
max_retries = 2 if account_manager else 1
last_error = None

for attempt in range(max_retries):
    try:
        # Get current auth manager (may have changed due to failover)
        if account_manager:
            auth_manager = account_manager.get_current_auth_manager()
        
        # ... existing API call code ...
    
    except HTTPException as e:
        last_error = e
        
        # Check if this is a billing error
        if account_manager and attempt < max_retries - 1:
            try:
                error_detail = e.detail
                if isinstance(error_detail, str):
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

if last_error:
    raise last_error
# ============================================================================
# MULTI-ACCOUNT MODIFICATION END
# ============================================================================
```

### routes_anthropic.py

**Same modifications as routes_openai.py**

---

## Verification After Rebase

### Step 1: Check File Integrity

```bash
# Verify all modifications are present
grep -n "MULTI-ACCOUNT MODIFICATION" main.py
grep -n "MULTI-ACCOUNT MODIFICATION" kiro/routes_openai.py
grep -n "MULTI-ACCOUNT MODIFICATION" kiro/routes_anthropic.py

# Should show 4 modifications in main.py, 2 in each routes file
```

### Step 2: Test Gateway

```bash
# Start gateway
python main.py

# Check for startup errors
# Should see: "Multi-account mode initialized" or "Initializing single-account mode"

# Check health endpoint
curl -H "Authorization: Bearer my-super-secret-password-123" \
  http://localhost:8000/health/accounts

# Should return account status
```

### Step 3: Run Test Suite

```bash
# See TESTING_GUIDE.md for full test procedures
# At minimum, run:
# - Configuration loading test
# - Health endpoint test
# - Request routing test
```

### Step 4: Verify Backward Compatibility

```bash
# Test single-account mode still works
# Remove kiro-accounts.json
# Set REFRESH_TOKEN and PROFILE_ARN
# Start gateway
# Verify it works in single-account mode
```

---

## Troubleshooting Rebase Issues

### Issue: Merge Conflicts Won't Resolve

**Solution**:
1. Abort the rebase: `git rebase --abort`
2. Create a new branch from upstream: `git checkout -b rebase-fix upstream/main`
3. Manually re-apply modifications using the markers above
4. Test thoroughly
5. Force push: `git push origin main --force-with-lease`

### Issue: Gateway Won't Start After Rebase

**Solution**:
1. Check logs: `python main.py 2>&1 | head -50`
2. Verify all modifications are present: `grep -n "MULTI-ACCOUNT" main.py`
3. Check for syntax errors: `python -m py_compile main.py`
4. Verify imports are correct: `python -c "from kiro.multi_account_config import load_multi_account_config"`

### Issue: Tests Fail After Rebase

**Solution**:
1. Check if upstream changes broke something
2. Review the upstream changes: `git log --oneline main@{1}..main`
3. Check if modifications are still in the right place
4. Run individual tests to isolate the issue

### Issue: Upstream Removed a Function I'm Using

**Solution**:
1. Check the upstream changelog
2. Find the replacement function
3. Update your modifications to use the new function
4. Test thoroughly

---

## Best Practices

### 1. Keep Modifications Minimal
- Only modify what's necessary
- Don't refactor upstream code
- Keep changes isolated and clearly marked

### 2. Test After Every Rebase
- Run the full test suite
- Test both single-account and multi-account modes
- Verify health endpoint works

### 3. Document Changes
- Keep track of what changed in upstream
- Note any modifications needed to your code
- Update this guide if new patterns emerge

### 4. Use Backup Branches
- Create a backup branch before rebasing
- Keep it until you're confident the rebase worked
- Delete after verification

### 5. Communicate Changes
- If working with others, let them know about rebases
- Document any breaking changes
- Update deployment procedures if needed

---

## Rebase Checklist

Before rebasing:
- [ ] All changes committed
- [ ] Backup branch created
- [ ] Tests passing

During rebase:
- [ ] Resolve conflicts using markers
- [ ] Keep both upstream and multi-account changes
- [ ] Verify syntax after resolving conflicts

After rebase:
- [ ] Gateway starts without errors
- [ ] Health endpoint works
- [ ] Single-account mode works
- [ ] Multi-account mode works
- [ ] All tests pass
- [ ] Changes pushed to fork

---

## Quick Reference

### Find All Modifications
```bash
grep -r "MULTI-ACCOUNT MODIFICATION" .
```

### Check Modification Count
```bash
grep -c "MULTI-ACCOUNT MODIFICATION START" main.py routes_openai.py routes_anthropic.py
# Should show: 4, 2, 2
```

### Verify Syntax
```bash
python -m py_compile main.py kiro/routes_openai.py kiro/routes_anthropic.py
```

### Test Gateway
```bash
python main.py &
sleep 2
curl http://localhost:8000/health/accounts
kill %1
```

---

## Summary

The multi-account implementation is organized to survive rebases by:

1. **New files** - No conflicts, merge cleanly
2. **Clearly marked modifications** - Easy to identify and re-apply
3. **Isolated changes** - Minimal impact on existing code
4. **Comprehensive documentation** - This guide explains everything

After rebasing:
1. Resolve conflicts using the markers
2. Verify all modifications are present
3. Test thoroughly
4. Push to your fork

Good luck with your rebases! 🚀
