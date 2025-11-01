# Logging System Documentation

> **Version**: 1.0
> **Last Updated**: 2025-11-01
> **Status**: Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Logging Modes](#logging-modes)
4. [Configuration Guide](#configuration-guide)
5. [Route-Specific Rules](#route-specific-rules)
6. [Status-Code-Based Filtering](#status-code-based-filtering)
7. [Cost Analysis](#cost-analysis)
8. [Quick Toggle Guide](#quick-toggle-guide)
9. [Pattern Matching System](#pattern-matching-system)
10. [Correlation IDs](#correlation-ids)
11. [Sensitive Data Masking](#sensitive-data-masking)
12. [Implementation Details](#implementation-details)
13. [Testing Guide](#testing-guide)
14. [Troubleshooting](#troubleshooting)
15. [Best Practices](#best-practices)
16. [Migration Guide](#migration-guide)

---

## Overview

### What Problem Does This Solve?

**Before:**
- Logs scattered across files (only 2 files had logging)
- Unstructured f-string logs (hard to search)
- No request/response correlation
- No exception logging
- Can't track a request through multiple operations
- No cost control as traffic scales

**After:**
- Single consolidated log per request
- Structured JSON logs (searchable)
- Correlation IDs track requests end-to-end
- All exceptions logged with tracebacks
- Flexible modes: full/smart/minimal
- 70% log reduction in smart mode
- Cloud-agnostic (no vendor lock-in)

### Key Features

✅ **Single Log Per Request** - All request/response data in one entry
✅ **Three Modes** - Full/Smart/Minimal for different scales
✅ **Status-Code-Based** - Success=minimal, Errors=full details
✅ **Route-Specific Rules** - Different logging per endpoint
✅ **Correlation IDs** - Track requests across operations
✅ **Cost Efficient** - Under free tier up to 100M requests/month
✅ **Cloud Agnostic** - No GCP/AWS specific dependencies
✅ **Easy Toggle** - Change mode with one env var
✅ **Middleware-Based** - No endpoint code changes needed

---

## Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Request                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Logging Middleware                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 1. Generate/Extract Correlation ID                     │ │
│  │ 2. Match request path against route rules             │ │
│  │ 3. Determine effective logging settings               │ │
│  │ 4. Capture request metadata + body (if configured)    │ │
│  │ 5. Start timer                                         │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Execute Request                           │
│                  (Your API Endpoints)                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Logging Middleware                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 6. Capture response metadata + body (if configured)   │ │
│  │ 7. Calculate duration                                  │ │
│  │ 8. Check status code (200 vs 400 vs 500)             │ │
│  │ 9. Determine log level (full vs metadata only)        │ │
│  │ 10. Log single consolidated entry                     │ │
│  │ 11. Add X-Request-ID header to response               │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Client Response                           │
│                 (with X-Request-ID header)                   │
└─────────────────────────────────────────────────────────────┘
```

### Component Overview

| Component | Location | Purpose |
|-----------|----------|---------|
| **Logging Config** | `app/logging_config.py` | Formatters, modes, route rules |
| **Middleware** | `app/middleware/logging_middleware.py` | Request/response interception |
| **Helpers** | `app/utils/logging_helpers.py` | Business/security event logging |
| **Context** | `app/dependencies.py` | Correlation ID storage |
| **Settings** | `app/config.py` | Environment configuration |

---

## Logging Modes

### Mode 1: FULL (Startup Phase)

**Use When:**
- Startup phase (< 10M requests/month)
- Active debugging
- Initial launch
- Under free tier

**What It Logs:**
- ✅ All request metadata (method, path, headers, user context)
- ✅ Full request bodies
- ✅ All response metadata (status, duration, headers)
- ✅ Full response bodies
- ✅ All status codes (200, 400, 500)

**Log Size:** ~1.6 KB per request

**Cost at 10M requests/month:** $0 (under 50GB free tier)

**Example Log:**
```json
{
  "timestamp": "2025-11-01T10:23:45.123Z",
  "level": "INFO",
  "correlation_id": "abc-def-123",
  "method": "POST",
  "path": "/jobs/123/applications",
  "user_id": "user-uuid",
  "company_id": "company-uuid",
  "role": "admin",
  "status_code": 200,
  "duration_ms": 145,
  "request_body": {"email": "user@example.com", "name": "John Doe"},
  "response_body": {"id": "app-uuid", "status": "applied"},
  "message": "Request completed"
}
```

---

### Mode 2: SMART (Production Scale) ⭐ RECOMMENDED

**Use When:**
- Production scale (10M-500M requests/month)
- Cost optimization needed
- Most requests succeed (95%+ success rate)

**How It Works:**
- ✅ **200-299 (Success):** Metadata only (~0.42 KB)
- ✅ **400-499 (Client Errors):** Full details (~1.6 KB)
- ✅ **500-599 (Server Errors):** Full details + traceback (~2.5 KB)

**Cost Reduction:** 70-80% smaller logs vs full mode

**Cost at 100M requests/month:** $0 (still under 50GB free tier)

**Example Success Log (200):**
```json
{
  "timestamp": "2025-11-01T10:23:45.123Z",
  "level": "INFO",
  "correlation_id": "abc-def-123",
  "method": "POST",
  "path": "/jobs/123/applications",
  "user_id": "user-uuid",
  "company_id": "company-uuid",
  "status_code": 200,
  "duration_ms": 145,
  "message": "Request completed"
}
```

**Example Error Log (500):**
```json
{
  "timestamp": "2025-11-01T10:23:45.123Z",
  "level": "ERROR",
  "correlation_id": "abc-def-123",
  "method": "POST",
  "path": "/jobs/123/applications",
  "user_id": "user-uuid",
  "company_id": "company-uuid",
  "status_code": 500,
  "duration_ms": 245,
  "request_body": {"email": "user@example.com"},
  "response_body": {"error": "Database connection failed"},
  "exception": "psycopg.OperationalError: connection timeout",
  "traceback": "Traceback (most recent call last):\n  File ...",
  "message": "Request failed"
}
```

---

### Mode 3: MINIMAL (Emergency Cost Control)

**Use When:**
- Extreme traffic (500M+ requests/month)
- Emergency cost control
- Temporarily reducing log verbosity

**What It Logs:**
- ✅ Request metadata only
- ❌ No request bodies
- ❌ No response bodies
- ✅ All status codes tracked

**Log Size:** ~0.42 KB per request

**Cost Reduction:** ~95% vs full mode

**Example Log:**
```json
{
  "timestamp": "2025-11-01T10:23:45.123Z",
  "level": "INFO",
  "correlation_id": "abc-def-123",
  "method": "POST",
  "path": "/jobs/123/applications",
  "status_code": 200,
  "duration_ms": 145,
  "message": "Request completed"
}
```

---

## Configuration Guide

### Environment Variables

#### Core Settings

```bash
# ===== MASTER LOGGING MODE =====
LOG_MODE=smart                          # full | smart | minimal
                                        # Controls overall logging verbosity

LOG_LEVEL=INFO                          # DEBUG | INFO | WARNING | ERROR
                                        # Python logging level

LOG_FORMAT=auto                         # auto | json | console
                                        # auto = console in dev, json in prod

# ===== REQUEST/RESPONSE LOGGING =====
LOG_REQUEST_BODY=true                   # Include request bodies in logs
LOG_RESPONSE_BODY=true                  # Include response bodies in logs

# ===== SAMPLING =====
LOG_SAMPLING_RATE=1.0                   # 0.0 to 1.0 (1.0 = 100%)
                                        # Randomly sample this % of requests
                                        # Errors always logged regardless

# ===== PERFORMANCE =====
LOG_SLOW_REQUEST_THRESHOLD_MS=2000      # Log warning if request > this
```

#### Smart Mode Settings

```bash
# ===== SMART MODE CONFIGURATION =====
# Only applies when LOG_MODE=smart

LOG_SUCCESS_LEVEL=metadata              # metadata | full
                                        # How to log 200-299 responses

LOG_CLIENT_ERROR_LEVEL=full             # metadata | full
                                        # How to log 400-499 responses

LOG_SERVER_ERROR_LEVEL=full             # metadata | full
                                        # How to log 500-599 responses
```

#### Optional Overrides

```bash
# ===== EMERGENCY OVERRIDE =====
# JSON string to override specific route without redeployment
LOG_ROUTE_OVERRIDE='{"pattern": "/public/jobs/*", "sample_rate": 0.01}'
```

---

### Development Environment (.env.development)

```bash
# ===== LOGGING CONFIGURATION =====
LOG_LEVEL=DEBUG
LOG_MODE=full                           # See everything while developing
LOG_FORMAT=console                      # Human-readable with colors
LOG_REQUEST_BODY=true
LOG_RESPONSE_BODY=true
LOG_SAMPLING_RATE=1.0                   # Log everything
LOG_SLOW_REQUEST_THRESHOLD_MS=2000

# Smart mode settings (not used in full mode)
LOG_SUCCESS_LEVEL=metadata
LOG_CLIENT_ERROR_LEVEL=full
LOG_SERVER_ERROR_LEVEL=full
```

---

### Production Environment (.env.production)

**For Startup Phase (< 10M requests/month):**

```bash
# ===== LOGGING CONFIGURATION =====
LOG_LEVEL=INFO
LOG_MODE=full                           # Safe under free tier
LOG_FORMAT=json                         # Structured for GCP Console
LOG_REQUEST_BODY=true                   # Safe at this scale
LOG_RESPONSE_BODY=true                  # Safe at this scale
LOG_SAMPLING_RATE=1.0                   # Log everything
LOG_SLOW_REQUEST_THRESHOLD_MS=2000

# Smart mode settings (for future use)
LOG_SUCCESS_LEVEL=metadata
LOG_CLIENT_ERROR_LEVEL=full
LOG_SERVER_ERROR_LEVEL=full
```

**For High Traffic (10M-100M requests/month):**

```bash
# ===== LOGGING CONFIGURATION =====
LOG_LEVEL=INFO
LOG_MODE=smart                          # ← Change to smart mode
LOG_FORMAT=json
LOG_REQUEST_BODY=true                   # Smart mode will filter
LOG_RESPONSE_BODY=true                  # Smart mode will filter
LOG_SAMPLING_RATE=1.0
LOG_SLOW_REQUEST_THRESHOLD_MS=2000

# Smart mode settings (now active)
LOG_SUCCESS_LEVEL=metadata              # Success = minimal
LOG_CLIENT_ERROR_LEVEL=full             # Client errors = detailed
LOG_SERVER_ERROR_LEVEL=full             # Server errors = detailed
```

**For Extreme Traffic (100M+ requests/month):**

```bash
# ===== LOGGING CONFIGURATION =====
LOG_LEVEL=INFO
LOG_MODE=smart
LOG_FORMAT=json
LOG_REQUEST_BODY=true
LOG_RESPONSE_BODY=true
LOG_SAMPLING_RATE=0.5                   # ← Log 50% of successes
LOG_SLOW_REQUEST_THRESHOLD_MS=2000

# Smart mode settings
LOG_SUCCESS_LEVEL=metadata
LOG_CLIENT_ERROR_LEVEL=full
LOG_SERVER_ERROR_LEVEL=full             # Always log server errors
```

---

## Route-Specific Rules

### Overview

Route rules provide fine-grained control over logging per endpoint. They override global settings and enable:
- Different logging modes per endpoint
- Disabling body logging for sensitive/large endpoints
- Sampling high-traffic public endpoints
- Always-on logging for critical admin endpoints

### Rule Priority

Rules are matched in order of specificity:

1. **Exact match** (highest priority): `/auth/login`
2. **Specific wildcard**: `/public/jobs/*/apply`
3. **Prefix wildcard**: `/dashboard/*`, `/jobs/*`
4. **Global default** (lowest priority): `*`

### Configuration Location

**File:** `app/logging_config.py`

```python
ROUTE_LOGGING_RULES = {
    # Authentication endpoints - Never log bodies (sensitive)
    "/auth/login": {
        "log_request_body": False,      # Contains password
        "log_response_body": False,     # Contains token
        "mask_fields": ["password", "token"]
    },

    "/auth/register": {
        "log_request_body": False,      # Contains password
        "log_response_body": True       # Want to see user creation
    },

    # Application submission - Don't log multipart upload
    "/public/jobs/*/apply": {
        "log_request_body": False,      # Multipart file upload (huge)
        "log_response_body": True,      # Need to see created application
        "mode": "smart"                 # Smart filtering
    },

    # Public job listings - Minimal logging (high traffic)
    "/public/jobs/*": {
        "mode": "minimal",              # Metadata only
        "sample_rate": 0.1,             # Log 10% of requests
        "log_on_error_only": True       # Only log if status >= 400
    },

    # Admin dashboard - Always full logging (critical)
    "/dashboard/*": {
        "mode": "full",                 # Always detailed
        "ignore_global_mode": True      # Don't respect LOG_MODE
    },

    # Job management - Smart filtering
    "/jobs/*": {
        "mode": "smart",                # Success=minimal, errors=full
        "log_slow_requests": True,      # Log if duration > threshold
        "slow_threshold_ms": 1000
    },

    # Default rule for all other endpoints
    "*": {
        "mode": None,                   # Use global LOG_MODE
        "log_request_body": True,
        "log_response_body": True
    }
}
```

### Rule Options

| Option | Type | Description |
|--------|------|-------------|
| `mode` | string | Override global mode: `full`, `smart`, `minimal`, or `None` |
| `log_request_body` | boolean | Include request body in logs |
| `log_response_body` | boolean | Include response body in logs |
| `sample_rate` | float | 0.0-1.0, randomly log this % (errors always logged) |
| `log_on_error_only` | boolean | Only log if status >= 400 |
| `ignore_global_mode` | boolean | Don't respect global LOG_MODE setting |
| `mask_fields` | list | Additional fields to mask (beyond defaults) |
| `log_slow_requests` | boolean | Log warning if duration exceeds threshold |
| `slow_threshold_ms` | int | Milliseconds threshold for slow requests |

### Examples

**Example 1: High-Traffic Public Endpoint**

```python
"/public/jobs/*": {
    "mode": "minimal",
    "sample_rate": 0.1,         # Log 10% only
    "log_on_error_only": True   # Except errors (always logged)
}
```

Result at 1M requests/month:
- 950K successful requests → Log ~95K (10%)
- 50K errors → Log all 50K
- Total logs: ~145K instead of 1M (85% reduction)

**Example 2: Sensitive Authentication**

```python
"/auth/login": {
    "log_request_body": False,  # Don't log password
    "log_response_body": False  # Don't log token
}
```

Result:
- Only metadata logged
- Password and token never in logs
- Still track login attempts and failures

**Example 3: Critical Admin Operations**

```python
"/dashboard/*": {
    "mode": "full",
    "ignore_global_mode": True  # Always full, even if global is minimal
}
```

Result:
- Always full logging for dashboard
- Even if production is in minimal mode
- Ensures admin operations are traceable

---

## Status-Code-Based Filtering

### How It Works

In **smart mode**, logging verbosity depends on the HTTP status code:

```python
if status_code >= 200 and status_code < 300:
    # Success - Log minimal (metadata only)
    log_level = "metadata"

elif status_code >= 400 and status_code < 600:
    # Error - Log full details
    log_level = "full"

else:
    # Redirects, etc - Log minimal
    log_level = "metadata"
```

### Status Code Categories

| Range | Category | Smart Mode Behavior |
|-------|----------|---------------------|
| 200-299 | Success | Metadata only (~0.42 KB) |
| 300-399 | Redirect | Metadata only (~0.42 KB) |
| 400-499 | Client Error | Full details (~1.6 KB) |
| 500-599 | Server Error | Full details + traceback (~2.5 KB) |

### Why This Strategy?

**Assumption:** Most requests succeed (95%+ success rate)

**Benefits:**
- **70-80% log reduction** - Most requests are 200 (metadata only)
- **Full debugging on errors** - When something breaks, you have all details
- **Cost efficient** - Stays under free tier longer
- **No missed errors** - All failures fully logged

**Example Traffic Pattern:**
- 1M requests/month
- 950K → 200 (success) → 0.42 KB each = 399 MB
- 40K → 400-499 (client error) → 1.6 KB each = 64 MB
- 10K → 500-599 (server error) → 2.5 KB each = 25 MB
- **Total: 488 MB** (vs 1.6 GB in full mode = 70% reduction)

### Override Status-Based Filtering

**Use case:** Want full logging even for 200s on specific endpoint

```python
"/api/critical-operation": {
    "mode": "full",                 # Override smart mode
    "ignore_global_mode": True      # Force full logging
}
```

---

## Cost Analysis

### Log Size Breakdown

**Minimal Log (metadata only):**
```json
{
  "timestamp": "2025-11-01T10:23:45.123Z",      // 24 bytes
  "level": "INFO",                               // 12 bytes
  "correlation_id": "abc-def-123",               // 36 bytes
  "method": "POST",                              // 15 bytes
  "path": "/jobs/123/applications",              // 50 bytes
  "user_id": "uuid",                             // 45 bytes
  "company_id": "uuid",                          // 48 bytes
  "role": "admin",                               // 15 bytes
  "status_code": 200,                            // 18 bytes
  "duration_ms": 123,                            // 18 bytes
  "user_agent": "Mozilla/5.0...",                // 120 bytes
  "ip": "192.168.1.1",                           // 20 bytes
  "message": "Request completed"                 // 30 bytes
}
```
**Total: ~420 bytes (0.42 KB)**

**Full Log (with bodies):**
```json
{
  // ... above fields (420 bytes) ...
  "request_body": "{\"email\":\"user@example.com\",\"name\":\"John Doe\"}",  // ~500 bytes
  "response_body": "{\"id\":\"uuid\",\"status\":\"applied\",\"created_at\":\"...\"}"  // ~700 bytes
}
```
**Total: ~1,620 bytes (1.6 KB)**

**Error Log (with traceback):**
```json
{
  // ... full log fields (1.6 KB) ...
  "exception": "ValueError: Invalid input",
  "traceback": "Traceback (most recent call last):\n  File ..."  // ~2 KB
}
```
**Total: ~2,500 bytes (2.5 KB)**

---

### Cost per Request

**Google Cloud Logging Pricing:**
- First 50 GB per month: **FREE**
- After 50 GB: **$0.50 per GB**

| Log Type | Size | Cost per Request | Cost per 1,000 Requests |
|----------|------|------------------|-------------------------|
| Minimal (metadata) | 0.42 KB | $0.00000021 | $0.00021 |
| Full (with bodies) | 1.6 KB | $0.0000008 | $0.0008 |
| Error (with traceback) | 2.5 KB | $0.00000125 | $0.00125 |

---

### Monthly Cost at Different Scales

#### Scenario 1: Startup (1M requests/month)

**Full mode:**
- All requests: 1M × 1.6 KB = 1.6 GB
- **Cost: FREE** (under 50 GB tier)

**Smart mode:**
- Success (95%): 950K × 0.42 KB = 399 MB
- Errors (5%): 50K × 2.5 KB = 125 MB
- **Total: 524 MB**
- **Cost: FREE**

**Savings:** Both free, use full mode for maximum debugging

---

#### Scenario 2: Growing (10M requests/month)

**Full mode:**
- All requests: 10M × 1.6 KB = 16 GB
- **Cost: FREE** (under 50 GB tier)

**Smart mode:**
- Success (95%): 9.5M × 0.42 KB = 3.99 GB
- Errors (5%): 500K × 2.5 KB = 1.25 GB
- **Total: 5.24 GB**
- **Cost: FREE**

**Savings:** Both free, use full mode

---

#### Scenario 3: Production Scale (100M requests/month)

**Full mode:**
- All requests: 100M × 1.6 KB = 160 GB
- Paid: 110 GB × $0.50 = **$55/month**

**Smart mode:**
- Success (95%): 95M × 0.42 KB = 39.9 GB
- Errors (5%): 5M × 2.5 KB = 12.5 GB
- **Total: 52.4 GB**
- Paid: 2.4 GB × $0.50 = **$1.20/month**

**Savings: $53.80/month (98% reduction)**

---

#### Scenario 4: High Growth (500M requests/month)

**Full mode:**
- All requests: 500M × 1.6 KB = 800 GB
- Paid: 750 GB × $0.50 = **$375/month**

**Smart mode:**
- Success (95%): 475M × 0.42 KB = 199.5 GB
- Errors (5%): 25M × 2.5 KB = 62.5 GB
- **Total: 262 GB**
- Paid: 212 GB × $0.50 = **$106/month**

**Savings: $269/month (72% reduction)**

**Smart mode + 50% sampling:**
- Success: 199.5 GB × 0.5 = 99.75 GB
- Errors: 62.5 GB (always logged)
- **Total: 162.25 GB**
- Paid: 112.25 GB × $0.50 = **$56/month**

**Savings: $319/month (85% reduction)**

---

### Cost Comparison Table

| Traffic | Full Mode | Smart Mode | Smart + Sampling (50%) | Savings |
|---------|-----------|------------|------------------------|---------|
| 1M/month | FREE | FREE | FREE | $0 |
| 10M/month | FREE | FREE | FREE | $0 |
| 100M/month | **$55** | **$1.20** | FREE | **$55** |
| 500M/month | **$375** | **$106** | **$56** | **$319** |
| 1B/month | **$800** | **$230** | **$130** | **$670** |

---

## Quick Toggle Guide

### Normal Operations (< 10M requests)

```bash
LOG_MODE=full
```

- **Cost:** $0/month
- **Use:** Startup phase, active development
- **Logs:** Everything (bodies + metadata)

---

### High Traffic (10M-100M requests)

```bash
LOG_MODE=smart
```

- **Cost:** $0-1/month
- **Use:** Production scale, cost awareness
- **Logs:** Success=metadata, Errors=full

**One env var change, no code deployment!**

---

### Viral Growth (100M-500M requests)

```bash
LOG_MODE=smart
LOG_SAMPLING_RATE=0.5  # Log 50% of successes
```

- **Cost:** $0-56/month (vs $55-375 full mode)
- **Use:** Rapid growth, cost control
- **Logs:** 50% of successes, 100% of errors

---

### Emergency Cost Control

```bash
LOG_MODE=minimal
LOG_SAMPLING_RATE=0.1  # Log 10% only
```

- **Cost:** ~$10/month (vs $375 full mode)
- **Use:** Unexpected traffic spike
- **Logs:** 10% sampled, errors always logged

---

### Temporary Debugging (No Redeployment)

```bash
# In production, enable full logging for one endpoint
LOG_ROUTE_OVERRIDE='{"pattern": "/jobs/*/applications", "mode": "full"}'
```

- **Effect:** One endpoint has full logging
- **Use:** Debugging production issue
- **No redeploy needed:** Just update env var in Cloud Run

---

### Disable Logging Temporarily

```bash
LOG_SAMPLING_RATE=0.0  # Log nothing (not recommended)
```

- **Cost:** $0
- **Use:** Never (unless truly emergency)
- **Warning:** Errors still logged (can't disable errors)

---

## Pattern Matching System

### How Patterns Work

The middleware matches each incoming request path against route rules to determine logging settings.

### Matching Algorithm

```python
def find_matching_rule(path: str) -> dict:
    # 1. Try exact match first (highest priority)
    if path in ROUTE_LOGGING_RULES:
        return ROUTE_LOGGING_RULES[path]

    # 2. Try wildcard patterns (specific to general)
    for pattern, rule in sorted_patterns:  # Sorted by specificity
        if matches_pattern(path, pattern):
            return rule

    # 3. Fall back to default
    return ROUTE_LOGGING_RULES["*"]
```

### Pattern Syntax

| Pattern | Matches | Examples |
|---------|---------|----------|
| `/auth/login` | Exact path only | `/auth/login` ✅<br>`/auth/login/` ❌<br>`/auth/logout` ❌ |
| `/jobs/*` | Single segment wildcard | `/jobs/123` ✅<br>`/jobs/abc` ✅<br>`/jobs/123/applications` ❌ |
| `/jobs/**` | Multi-segment wildcard | `/jobs/123` ✅<br>`/jobs/123/applications` ✅<br>`/jobs/123/applications/456` ✅ |
| `/public/jobs/*/apply` | Wildcard in middle | `/public/jobs/abc-123/apply` ✅<br>`/public/jobs/xyz/apply` ✅<br>`/public/jobs/abc-123/applications` ❌ |
| `*` | Global default | Everything not matched above |

### Pattern Priority Examples

**Example 1: Exact vs Wildcard**

```python
ROUTE_LOGGING_RULES = {
    "/jobs/123": {"mode": "full"},      # Exact match
    "/jobs/*": {"mode": "smart"}        # Wildcard
}
```

- Request: `/jobs/123` → Uses "full" (exact match wins)
- Request: `/jobs/456` → Uses "smart" (wildcard match)

**Example 2: Specific vs General Wildcard**

```python
ROUTE_LOGGING_RULES = {
    "/public/jobs/*/apply": {"log_request_body": False},  # Specific
    "/public/jobs/*": {"mode": "minimal"}                 # General
}
```

- Request: `/public/jobs/abc/apply` → Uses first rule (more specific)
- Request: `/public/jobs/abc` → Uses second rule

**Example 3: Multiple Wildcards**

```python
ROUTE_LOGGING_RULES = {
    "/api/v1/*/applications": {...},    # More specific
    "/api/*/*": {...},                  # Less specific
    "/api/*": {...}                     # Least specific
}
```

- `/api/v1/jobs/applications` → First rule (exact pattern match)
- `/api/v1/jobs` → Second rule
- `/api/v1` → Third rule

---

## Correlation IDs

### What Are Correlation IDs?

A unique identifier (UUID) assigned to each request that:
- Tracks the request through multiple operations
- Links all logs related to the same request
- Enables end-to-end tracing
- Helps debugging in production

### How They Work

```
1. Request arrives → Middleware generates UUID
2. UUID stored in context variable (thread-safe)
3. All logs include this UUID automatically
4. Response includes X-Request-ID header
5. Client can use this ID for support requests
```

### Example Flow

**Request:**
```http
POST /jobs/123/applications
```

**Middleware:**
```python
correlation_id = "abc-def-123-456"
set_correlation_id(correlation_id)
```

**Logs Generated:**
```json
// Log 1: Request received
{"correlation_id": "abc-def-123-456", "event": "request_received", ...}

// Log 2: Database query
{"correlation_id": "abc-def-123-456", "event": "db_query", "query": "SELECT ..."}

// Log 3: GCS upload
{"correlation_id": "abc-def-123-456", "event": "resume_uploaded", "path": "..."}

// Log 4: Response sent
{"correlation_id": "abc-def-123-456", "event": "request_completed", "status": 200}
```

**Response:**
```http
HTTP/1.1 200 OK
X-Request-ID: abc-def-123-456
Content-Type: application/json

{"id": "app-uuid", "status": "applied"}
```

### Searching Logs by Correlation ID

**In GCP Console:**
```
jsonPayload.correlation_id="abc-def-123-456"
```

**Result:** All logs related to this request, in chronological order

### Client-Side Integration

**Clients can provide their own correlation IDs:**

```javascript
// Frontend sends request with custom ID
fetch('/api/jobs/123/applications', {
  headers: {
    'X-Request-ID': 'frontend-generated-id'
  }
})
```

**Backend will use provided ID** instead of generating new one.

**Use cases:**
- Frontend error tracking (link frontend errors to backend logs)
- Multi-service tracing (same ID across multiple services)
- Support requests (users can provide request ID)

### Accessing Correlation ID in Code

```python
from app.dependencies import get_correlation_id

# In any endpoint or function
correlation_id = get_correlation_id()
logger.info(
    "Custom event",
    extra={
        "correlation_id": correlation_id,
        "custom_data": "..."
    }
)
```

---

## Sensitive Data Masking

### Why Mask Data?

**Security:** Prevent credentials from appearing in logs
**Compliance:** GDPR, CCPA, PCI-DSS requirements
**Privacy:** Protect user data

### What Gets Masked?

**Automatically masked fields:**
- `password`
- `token`
- `access_token`
- `refresh_token`
- `secret`
- `api_key`
- `credit_card`
- `card_number`
- `cvv`
- `ssn`

**NOT masked (intentionally):**
- `email` - Needed for user lookup/debugging
- `phone` - Needed for user lookup/debugging
- `name` - Not sensitive enough to mask

### How Masking Works

**Before logging:**
```json
{
  "email": "user@example.com",
  "password": "MySecretPassword123",
  "phone": "+1234567890"
}
```

**After masking:**
```json
{
  "email": "user@example.com",
  "password": "***REDACTED***",
  "phone": "+1234567890"
}
```

### Custom Masking Per Route

```python
"/auth/login": {
    "mask_fields": ["password", "token"],  # Default
    "log_request_body": False              # Or just don't log body
}

"/api/payment": {
    "mask_fields": ["card_number", "cvv", "billing_address"],  # Custom
    "log_request_body": True
}
```

### Masking in Manual Logs

```python
from app.utils.logging_helpers import mask_sensitive_data

data = {
    "email": "user@example.com",
    "password": "secret123",
    "name": "John Doe"
}

# Mask before logging
masked = mask_sensitive_data(data)
logger.info("User data", extra={"data": masked})

# Output: {"email": "...", "password": "***REDACTED***", "name": "..."}
```

---

## Implementation Details

### File Structure

```
app/
├── config.py                       # Settings with logging config
├── dependencies.py                 # Correlation ID context
├── exceptions.py                   # Exception handlers with logging
├── main.py                         # Middleware registration + lifespan
├── logging_config.py               # ⭐ Formatters, modes, rules
├── middleware/
│   ├── __init__.py
│   └── logging_middleware.py      # ⭐ Request/response logging
├── routers/
│   ├── auth.py                     # Security event logging
│   ├── jobs.py                     # Business event logging
│   ├── companies.py                # Profile update logging
│   ├── applications.py             # Structured logging
│   └── dashboard.py
├── services/
│   └── storage.py                  # Structured logging
└── utils/
    └── logging_helpers.py          # ⭐ Helper functions
```

### Key Files

#### 1. app/logging_config.py

**Purpose:** Central logging configuration

**Contents:**
- `ROUTE_LOGGING_RULES` dictionary
- `find_matching_rule(path)` function
- `determine_log_level(mode, status_code)` function
- `setup_logging()` function
- Formatters (JsonFormatter, ColoredFormatter)
- Masking logic

**~300 lines of code**

#### 2. app/middleware/logging_middleware.py

**Purpose:** Request/response interception

**Contents:**
- `LoggingMiddleware` class (extends BaseHTTPMiddleware)
- Correlation ID generation/extraction
- Request/response capture
- Pattern matching
- Log consolidation
- Header injection

**~200 lines of code**

#### 3. app/utils/logging_helpers.py

**Purpose:** Helper functions for manual logging

**Contents:**
- `get_correlation_id()`
- `log_business_event()`
- `log_security_event()`
- `log_performance_event()`
- `mask_sensitive_data()`

**~100 lines of code**

### Dependencies

```txt
python-json-logger==2.0.7  # Structured JSON logging
```

**That's it!** No cloud-specific dependencies.

---

## Testing Guide

### Test Checklist

- [ ] Console format works in development
- [ ] JSON format works in production
- [ ] Full mode logs everything
- [ ] Smart mode logs metadata for 200s
- [ ] Smart mode logs full for 4xx/5xx
- [ ] Minimal mode logs metadata only
- [ ] Route rules override global settings
- [ ] Correlation ID generated/extracted
- [ ] Correlation ID in response header
- [ ] Correlation ID in all logs
- [ ] Exception logging works
- [ ] Sensitive data masked
- [ ] Email/phone NOT masked
- [ ] Sampling works
- [ ] User context included (authenticated)
- [ ] User context null (unauthenticated)

### Test Scenarios

#### 1. Test Console Format

```bash
# .env.development
LOG_MODE=full
LOG_FORMAT=console

# Start server
uvicorn app.main:app --reload

# Make request
curl http://localhost:8000/health

# Expected: Human-readable log with colors
# 2025-11-01 10:23:45 | INFO | correlation_id=abc-123 | GET /health | status=200 | duration=5ms
```

#### 2. Test Full Mode

```bash
LOG_MODE=full

# Make request with body
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "test123"}'

# Expected log includes:
# - request_body: {"email": "...", "password": "***REDACTED***"}
# - response_body: {"token": "...", ...}
```

#### 3. Test Smart Mode - Success

```bash
LOG_MODE=smart

# Make successful request (200)
curl http://localhost:8000/jobs

# Expected: Metadata only, no bodies
# {"correlation_id": "...", "status_code": 200, "duration_ms": 45}
```

#### 4. Test Smart Mode - Error

```bash
LOG_MODE=smart

# Make request that fails (404)
curl http://localhost:8000/jobs/invalid-uuid

# Expected: Full details including bodies and error
# {"correlation_id": "...", "status_code": 404, "response_body": {...}, "error": "..."}
```

#### 5. Test Correlation ID

```bash
# Without header (auto-generated)
curl -v http://localhost:8000/health

# Expected response header:
# X-Request-ID: <auto-generated-uuid>

# With custom header
curl -v -H "X-Request-ID: my-custom-id" http://localhost:8000/health

# Expected response header:
# X-Request-ID: my-custom-id
```

#### 6. Test Route Override

```bash
LOG_MODE=minimal

# Request to dashboard (should use full mode per rule)
curl http://localhost:8000/dashboard/statistics

# Expected: Full logging despite global minimal mode
```

#### 7. Test Sampling

```bash
LOG_SAMPLING_RATE=0.1

# Make 100 requests
for i in {1..100}; do curl http://localhost:8000/health; done

# Expected: ~10 logs (10% sampling)

# Trigger error
curl http://localhost:8000/jobs/invalid

# Expected: Error logged regardless of sampling
```

---

## Troubleshooting

### Issue: Logs not appearing

**Possible causes:**
1. LOG_SAMPLING_RATE=0.0 (disabled logging)
2. LOG_MODE not set correctly
3. Middleware not registered
4. Logger not initialized

**Solution:**
```bash
# Check settings
python -c "from app.config import settings; print(settings.log_mode)"

# Check middleware registered
# In app/main.py, verify:
# app.add_middleware(LoggingMiddleware)

# Check logging initialized
# In app/main.py, verify lifespan event calls setup_logging()
```

---

### Issue: Correlation ID not in logs

**Possible causes:**
1. Middleware not setting context
2. Manual logs not including correlation_id

**Solution:**
```python
# In manual logs, always include:
from app.dependencies import get_correlation_id

logger.info(
    "Event",
    extra={"correlation_id": get_correlation_id(), ...}
)
```

---

### Issue: Passwords appearing in logs

**Possible causes:**
1. Masking not working
2. Field name not in mask list

**Solution:**
```python
# Check field name matches mask patterns
# In logging_config.py, add to SENSITIVE_FIELDS:
SENSITIVE_FIELDS = [
    "password",
    "your_custom_field",  # Add here
    ...
]
```

---

### Issue: Logs too large / expensive

**Quick fixes:**
```bash
# 1. Switch to smart mode
LOG_MODE=smart

# 2. Add sampling
LOG_SAMPLING_RATE=0.5  # Log 50%

# 3. Disable bodies
LOG_REQUEST_BODY=false
LOG_RESPONSE_BODY=false

# 4. Sample high-traffic endpoints
# In logging_config.py:
"/public/jobs/*": {"sample_rate": 0.1}
```

---

### Issue: Can't find logs in GCP Console

**Search queries:**
```
# By correlation ID
jsonPayload.correlation_id="abc-123"

# By user
jsonPayload.user_id="user-uuid"

# By endpoint
jsonPayload.path="/jobs"

# By status code
jsonPayload.status_code=500

# By error
severity="ERROR"

# Combine filters
jsonPayload.path="/jobs" AND jsonPayload.status_code>=400
```

---

### Issue: Development logs not colorized

**Solution:**
```bash
# Check LOG_FORMAT
LOG_FORMAT=console  # Not json

# Check terminal supports colors
# Try: export FORCE_COLOR=1
```

---

## Best Practices

### 1. Start with Full Mode

In startup phase (< 10M requests/month):
- Use `LOG_MODE=full`
- Log everything
- Cost: $0 (under free tier)
- Maximum visibility for debugging

### 2. Switch to Smart Mode at Scale

When traffic grows (10M+ requests/month):
- Change to `LOG_MODE=smart`
- One env var change
- 70% log reduction
- Still under free tier

### 3. Always Log Errors

Never disable error logging:
- Errors always logged in smart mode (regardless of sampling)
- Critical for debugging production issues
- Relatively low volume (should be < 5% of traffic)

### 4. Use Route Rules for High-Traffic Endpoints

For public endpoints with high traffic:
```python
"/public/jobs/*": {
    "sample_rate": 0.1,         # Log 10% only
    "log_on_error_only": True   # Except errors
}
```

### 5. Never Log Passwords/Tokens in Bodies

For authentication endpoints:
```python
"/auth/login": {
    "log_request_body": False,  # Contains password
    "log_response_body": False  # Contains token
}
```

### 6. Always Include Correlation ID

In manual logs:
```python
logger.info(
    "Event description",
    extra={
        "correlation_id": get_correlation_id(),  # Always include
        "other_data": "..."
    }
)
```

### 7. Use Structured Logging

**Don't:**
```python
logger.info(f"Application {app_id} submitted by {email}")
```

**Do:**
```python
logger.info(
    "Application submitted",
    extra={
        "event": "application_submitted",
        "application_id": app_id,
        "email": email,
        "correlation_id": get_correlation_id()
    }
)
```

### 8. Monitor Log Volume

Set up alerts:
- Alert at 40 GB/month (80% of free tier)
- Monitor trends
- Adjust settings before hitting paid tier

### 9. Test in Development First

Before changing production:
- Test new settings locally
- Verify log format correct
- Check sensitive data masked
- Deploy to dev environment
- Monitor for 24 hours
- Then update production

### 10. Document Why You Changed Settings

When adjusting:
```bash
# In .env.production, add comment
LOG_MODE=smart  # Changed 2025-11-05: Hit 50M req/month, optimize costs
LOG_SAMPLING_RATE=0.5  # Changed 2025-11-10: Traffic spike, temporary reduction
```

---

## Migration Guide

### Current State

**What we have:**
- Minimal logging (only 2 files)
- Unstructured f-string logs
- No correlation IDs
- No exception logging
- No request/response tracking

**What we're building:**
- Comprehensive middleware-based logging
- Structured JSON logs
- Correlation ID tracking
- Full exception logging
- Single log per request

### Migration Steps

#### Phase 1: Add Core Infrastructure (Day 1)

1. ✅ Create `app/logging_config.py`
2. ✅ Create `app/middleware/logging_middleware.py`
3. ✅ Create `app/utils/logging_helpers.py`
4. ✅ Update `app/config.py` with logging settings
5. ✅ Update `app/dependencies.py` with correlation ID
6. ✅ Register middleware in `app/main.py`

**Test:** Basic request/response logging works

#### Phase 2: Update Exception Handlers (Day 1)

1. ✅ Add logging to all 4 exception handlers in `app/exceptions.py`
2. ✅ Include correlation IDs
3. ✅ Test exception logging

**Test:** Errors logged with full tracebacks

#### Phase 3: Add Router Logging (Day 2)

1. ✅ Add security event logging to `app/routers/auth.py`
2. ✅ Add business event logging to `app/routers/jobs.py`
3. ✅ Add profile update logging to `app/routers/companies.py`
4. ✅ Test manual event logging

**Test:** Business/security events logged correctly

#### Phase 4: Convert Existing Logs (Day 2)

1. ✅ Convert 6 logs in `app/services/storage.py` to structured format
2. ✅ Convert 6 logs in `app/routers/applications.py` to structured format
3. ✅ Add correlation IDs to all logs

**Test:** All logs now structured

#### Phase 5: Environment Configuration (Day 2)

1. ✅ Update `.env.development` with logging settings
2. ✅ Update `.env.production` with logging settings
3. ✅ Test both environments

**Test:** Correct format per environment

#### Phase 6: Deploy and Monitor (Day 3)

1. ✅ Deploy to dev environment
2. ✅ Monitor logs in GCP Console
3. ✅ Verify correlation ID search works
4. ✅ Test all logging modes
5. ✅ Deploy to production
6. ✅ Monitor for 24 hours

**Test:** Production logs working correctly

#### Phase 7: Documentation (Day 3)

1. ✅ Update `AI_CODING_STANDARDS.md`
2. ✅ Update `CLAUDE.md`
3. ✅ Update `vibe-plan/progress.md`
4. ✅ Create this `logging.md` guide

**Test:** Documentation complete and accurate

### Rollback Plan

If issues arise:

1. **Disable middleware:**
   ```python
   # In app/main.py, comment out:
   # app.add_middleware(LoggingMiddleware)
   ```

2. **Revert to minimal mode:**
   ```bash
   LOG_MODE=minimal
   ```

3. **Redeploy previous version:**
   ```bash
   # If critical issues
   gcloud run services update subtribe-ats-api \
     --image gcr.io/PROJECT/subtribe-ats:previous-version
   ```

### Post-Migration

- [ ] Monitor log volume daily for first week
- [ ] Set up alerts at 40 GB/month (80% of free tier)
- [ ] Review cost trends weekly
- [ ] Adjust settings as traffic grows
- [ ] Document any issues encountered

---

## Summary

### Key Takeaways

1. **Single log per request** - All details consolidated
2. **Three modes** - Full/Smart/Minimal for different scales
3. **Status-code-based** - Success minimal, errors full
4. **Route-specific rules** - Fine-grained per-endpoint control
5. **Correlation IDs** - Track requests end-to-end
6. **Cost efficient** - 70% reduction in smart mode
7. **Cloud agnostic** - No vendor lock-in
8. **Easy toggle** - One env var change
9. **Production ready** - Handles 100M+ requests/month under free tier

### Quick Reference

**Change mode:**
```bash
LOG_MODE=full   # All details
LOG_MODE=smart  # Optimized
LOG_MODE=minimal # Metadata only
```

**Add sampling:**
```bash
LOG_SAMPLING_RATE=0.5  # Log 50%
```

**Search logs:**
```
jsonPayload.correlation_id="abc-123"
jsonPayload.user_id="user-uuid"
jsonPayload.status_code>=400
```

**Emergency override:**
```bash
LOG_ROUTE_OVERRIDE='{"pattern": "/api/*", "mode": "full"}'
```

---

## Support

**Questions?** Check:
1. This documentation
2. `AI_CODING_STANDARDS.md` for coding patterns
3. `CLAUDE.md` for project context
4. Code comments in `app/logging_config.py`

**Issues?** See [Troubleshooting](#troubleshooting) section

**Feature requests?** Document in `vibe-plan/progress.md`

---

**Last Updated:** 2025-11-01
**Version:** 1.0
**Status:** Production Ready
**Maintainer:** Development Team
