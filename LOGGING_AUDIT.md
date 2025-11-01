# Logging Audit & Verbose Logger Suppression

**Date**: 2025-11-01
**Issue**: Verbose third-party logging was flooding output with SQL queries and duplicate access logs
**Status**: ✅ **RESOLVED**

---

## Problem

After implementing the structured logging system, verbose third-party libraries were creating noise:

1. **SQLAlchemy**: Logging raw SQL queries with parameter binding details
2. **Uvicorn**: Duplicate access logs (both uvicorn's and our middleware's logs)
3. **Potential**: Other third-party libraries (httpx, google-cloud, asyncio)

**Example of problematic output**:
```
2025-11-01 19:46:04.897 IST WHERE jobs.slug = $1::VARCHAR
2025-11-01 19:46:04.897 IST SELECT companies.id AS companies_id...
INFO:     127.0.0.1:58401 - "GET /health HTTP/1.1" 200 OK
2025-11-01 19:49:09 | INFO | correlation_id=eb9ef59f... | GET /docs | ...
INFO:     127.0.0.1:58453 - "GET /docs HTTP/1.1" 200 OK
```

---

## Root Causes

### 1. SQLAlchemy Echo Enabled
**File**: `app/database.py:33`
**Issue**: `echo=settings.debug` was logging ALL SQL queries when debug=True

### 2. Uvicorn Access Logs
**Issue**: Uvicorn's default access logger was duplicating our middleware logs

### 3. Insufficient Logger Suppressions
**Issue**: Not all verbose third-party loggers were suppressed in `logging_config.py`

---

## Solutions Applied

### 1. Disabled SQLAlchemy Echo
**File**: `app/database.py`

```python
# BEFORE:
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # ❌ Logs all SQL queries when debug=True
    ...
)

# AFTER:
engine = create_async_engine(
    settings.database_url,
    echo=False,  # ✅ Don't log SQL queries (use our logging middleware instead)
    ...
)
```

### 2. Added --no-access-log Flag to Uvicorn
**File**: `Dockerfile`

```dockerfile
# BEFORE:
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}

# AFTER:
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --no-access-log
```

**Impact**: Production deployments (Cloud Run) will use this flag automatically

### 3. Comprehensive Logger Suppressions
**File**: `app/logging_config.py`

Added comprehensive suppressions for all verbose third-party libraries:

```python
def setup_logging(log_format: str = "json", log_level: str = "INFO"):
    # ... formatter setup ...

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("google.auth").setLevel(logging.WARNING)
    logging.getLogger("google.cloud").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # CRITICAL: Suppress SQLAlchemy query logging (extremely verbose)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)

    # Suppress uvicorn access logs (we have our own middleware logging)
    # Note: Also run uvicorn with --no-access-log flag for complete suppression
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)  # Keep errors visible

    # Suppress FastAPI/Starlette internal logs
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    logging.getLogger("starlette").setLevel(logging.WARNING)
```

---

## Suppressed Loggers Reference

### Database & ORM
- `sqlalchemy.engine` - SQL query execution
- `sqlalchemy.pool` - Connection pool management
- `sqlalchemy.dialects` - Database dialect specifics
- `sqlalchemy.orm` - ORM operations

### Web Framework
- `uvicorn` - Root uvicorn logger
- `uvicorn.access` - HTTP access logs
- `uvicorn.error` - ERROR level only (INFO suppressed)
- `fastapi` - FastAPI framework internals
- `starlette` - Starlette (FastAPI base) internals

### HTTP Clients
- `httpx` - Async HTTP client
- `httpcore` - HTTP core library

### Cloud Services
- `google` - Google Cloud SDK
- `google.auth` - Google authentication
- `google.cloud` - Google Cloud Storage client
- `urllib3` - Underlying HTTP library

### System
- `asyncio` - Async event loop debugging

---

## Testing Results

### Before Fixes
```
INFO:     127.0.0.1:58401 - "GET /health HTTP/1.1" 200 OK
2025-11-01 19:46:04.897 IST WHERE jobs.slug = $1::VARCHAR
2025-11-01 19:46:04.897 IST SELECT companies.id AS companies_id...
2025-11-01 19:22:15 | INFO | correlation_id=802d50fd... | GET /docs | status=200
INFO:     127.0.0.1:58453 - "GET /docs HTTP/1.1" 200 OK
```

### After Fixes ✅
```
2025-11-01 20:11:01 | INFO | Application starting
2025-11-01 20:12:53 | INFO | correlation_id=16b0ee69... | GET /docs | status=200 | duration=0ms | Request completed: GET /docs
2025-11-01 20:13:17 | WARNING | correlation_id=108858aa... | GET /public/jobs | status=404 | duration=0ms | Request completed: GET /public/jobs
```

**Result**: Clean, single-line logs with no duplicates or SQL spam! 🎉

---

## Development Setup

When running locally, use the `--no-access-log` flag:

```bash
# Development (with auto-reload)
uvicorn app.main:app --reload --no-access-log

# Production (with host/port)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

---

## Files Modified

1. ✅ `app/database.py` - Disabled `echo` parameter
2. ✅ `Dockerfile` - Added `--no-access-log` flag
3. ✅ `app/logging_config.py` - Comprehensive logger suppressions

---

## Related Documentation

- [`vibe-plan/logging.md`](./vibe-plan/logging.md) - Complete logging system documentation
- [`app/logging_config.py`](./app/logging_config.py) - Logging configuration implementation
- [`app/middleware/logging_middleware.py`](./app/middleware/logging_middleware.py) - Request/response logging

---

## Maintenance

### Adding New Library Suppressions

If a new third-party library starts logging verbosely, add it to `app/logging_config.py`:

```python
def setup_logging(log_format: str = "json", log_level: str = "INFO"):
    # ... existing setup ...

    # Add new logger suppression
    logging.getLogger("noisy_library_name").setLevel(logging.WARNING)
```

### Common Verbose Loggers to Watch For

Libraries that commonly have verbose logging:
- Database drivers (psycopg2, asyncpg, pymysql)
- HTTP clients (requests, httpx, aiohttp)
- Cloud SDKs (boto3, google-cloud, azure-sdk)
- ORMs (SQLAlchemy, Tortoise, Peewee)
- Web servers (uvicorn, gunicorn, hypercorn)

---

**Last Updated**: 2025-11-01
**Status**: Production Ready ✅
