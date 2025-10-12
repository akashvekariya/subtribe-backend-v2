# Testing Strategy - Subtribe ATS Backend

> **Current Status**: Comprehensive test suite implemented  
> **Coverage**: Unit tests, integration tests, E2E tests, performance tests

---

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures, test DB setup
├── plan.md                  # This file - testing strategy
├── progress.md              # Testing progress tracking
├── data/                    # Test data files
│   └── test.pdf            # Sample resume for testing
├── unit/                    # Unit tests with mocks
│   ├── test_models.py      # SQLAlchemy model tests
│   ├── test_schemas.py     # Pydantic schema validation tests
│   └── test_services.py    # Service layer tests (mocked GCS)
├── integration/             # Integration tests with TestClient
│   ├── test_auth_endpoints.py        # /auth/* endpoints
│   ├── test_company_endpoints.py     # /companies/* endpoints
│   ├── test_job_endpoints.py         # /jobs/*, /public/jobs/*
│   └── test_application_endpoints.py # /applications/*, /public/jobs/*/apply
├── e2e/                     # End-to-end tests (configurable URL)
│   ├── config.py           # Environment configuration
│   └── test_complete_flow.py # Full user journey tests
└── performance/
    └── test_response_times.py # Performance analytics
```

---

## Test Categories

### 1. Unit Tests (`tests/unit/`)

**Purpose**: Test individual components in isolation with mocks

**Files**:
- `test_models.py` - SQLAlchemy model creation, relationships, validation
- `test_schemas.py` - Pydantic schema validation, field constraints
- `test_services.py` - Storage service logic (GCS mocked)

**Run**: `pytest tests/unit/ -v`

**Coverage**:
- ✅ All models (Company, User, Job, Application, StatusHistory)
- ✅ All schemas (auth, company, job, application)
- ✅ Storage service (upload, signed URLs, path generation)

**Mocking**:
- GCS client fully mocked
- Database uses SQLite in-memory (fast)
- No external dependencies

---

### 2. Integration Tests (`tests/integration/`)

**Purpose**: Test API endpoints with real FastAPI TestClient and test database

**Files**:
- `test_auth_endpoints.py` - Registration, login, current user
- `test_company_endpoints.py` - Get/update company profile
- `test_job_endpoints.py` - CRUD jobs, public job page, view counter
- `test_application_endpoints.py` - Submit application, list, update status, resume URLs, history

**Run**: `pytest tests/integration/ -v`

**Coverage**:
- ✅ All 20+ API endpoints
- ✅ Authentication and authorization
- ✅ Multi-tenant isolation (company_id filtering)
- ✅ Error responses (401, 403, 404, 409, 422)
- ✅ File upload validation
- ✅ Status history tracking

**Test Database**:
- SQLite in-memory (isolated per test)
- Automatic setup/teardown
- Fast and reliable

---

### 3. End-to-End Tests (`tests/e2e/`)

**Purpose**: Test complete user flows against live server (local or staging)

**Files**:
- `config.py` - Environment configuration (URL switching)
- `test_complete_flow.py` - Full journey: register → create job → apply → hire

**Run**:
- Local: `pytest tests/e2e/ -v`
- Staging: `E2E_BASE_URL=https://staging.api.com pytest tests/e2e/ -v`
- Production: `E2E_BASE_URL=https://api.subtribe.com pytest tests/e2e/ -v`

**Coverage**:
- ✅ Complete user journey (13 steps)
- ✅ Registration and authentication
- ✅ Company profile management
- ✅ Job creation and publishing
- ✅ Public job page viewing
- ✅ Application submission with resume
- ✅ Application management
- ✅ Status changes with history
- ✅ Edge cases (duplicate applications)

**Environment Variables**:
```bash
E2E_BASE_URL=http://localhost:8000     # Target server
E2E_COMPANY_CODE=TEST-abc123           # Test company code
E2E_TEST_EMAIL=test@example.com        # Existing user email (for staging/prod)
E2E_TEST_PASSWORD=password123          # Existing user password
```

---

### 4. Performance Tests (`tests/performance/`)

**Purpose**: Measure response times and generate performance analytics

**Files**:
- `test_response_times.py` - Measures all endpoints, prints detailed analytics

**Run**:
- Local: `pytest tests/performance/ -v -s`
- Staging: `E2E_BASE_URL=https://staging.api.com pytest tests/performance/ -v -s`

**Metrics Tracked**:
- Response time per endpoint (min, max, mean, median, stdev)
- Performance ratings (Excellent < 100ms, Good < 200ms, Acceptable < 500ms)
- Aggregate statistics across all endpoints
- Performance distribution

**Endpoints Measured**:
- ✅ Health check
- ✅ Auth endpoints (login, /auth/me)
- ✅ Job endpoints (list, get, public page)
- ✅ Application endpoints (list, get, history)

**Output Example**:
```
GET /health
  Rating: ⚡ Excellent
  Mean: 45.23ms
  Median: 42.10ms

GET /jobs
  Rating: ✅ Good
  Mean: 156.78ms
  Median: 150.45ms

AGGREGATE STATISTICS
Total API calls: 120
Overall mean: 123.45ms
Performance distribution:
  ⚡ Excellent (<100ms): 45 (37.5%)
  ✅ Good (<200ms): 60 (50.0%)
  ⚠️ Acceptable (<500ms): 15 (12.5%)
```

---

## Running Tests

### Run All Tests
```bash
pytest -v
```

### Run Specific Category
```bash
pytest tests/unit/ -v              # Unit tests only
pytest tests/integration/ -v       # Integration tests only
pytest tests/e2e/ -v              # E2E tests only
pytest tests/performance/ -v -s   # Performance tests (with output)
```

### Run with Coverage
```bash
pytest --cov=app --cov-report=html
```

### Run E2E Against Staging
```bash
E2E_BASE_URL=https://staging.api.com pytest tests/e2e/ -v
```

### Run Performance Tests
```bash
# Local server
pytest tests/performance/test_response_times.py -v -s

# Staging server
E2E_BASE_URL=https://staging.api.com pytest tests/performance/ -v -s
```

---

## Test Fixtures (conftest.py)

### Database Fixtures
- `test_db` - Fresh SQLite in-memory database per test
- `override_get_db` - Override FastAPI dependency

### Client Fixtures
- `client` - FastAPI TestClient with test database

### Auth Fixtures
- `test_company` - Creates test company
- `test_user` - Creates test user
- `test_user_2` - Second user (for status changes)
- `auth_headers` - JWT token in headers dict
- `mock_get_current_user` - Skip Supabase validation

### Data Fixtures
- `test_job` - Creates test job
- `test_application` - Creates test application

### Mock Fixtures
- `mock_storage_service` - Mocked GCS service
- `mock_supabase_client` - Mocked Supabase Auth
- `sample_pdf_file` - Path to test.pdf

---

## Development Workflow

### Before Committing Code
```bash
# Run all tests
pytest -v

# Check linting
ruff check app/

# Run specific endpoint tests if you changed code
pytest tests/integration/test_job_endpoints.py -v
```

### After Adding New Endpoint
1. Add integration test in `tests/integration/test_*_endpoints.py`
2. Update E2E flow if needed
3. Run tests: `pytest tests/integration/ -v`

### Performance Regression Testing
```bash
# Run before and after changes
pytest tests/performance/ -v -s > perf_before.txt
# Make changes
pytest tests/performance/ -v -s > perf_after.txt
# Compare results
```

---

## Test Dependencies

**Required packages** (already in `requirements.txt`):
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `httpx` - HTTP client for E2E tests
- `fastapi[all]` - Includes TestClient

**Optional** (for future):
- `pytest-cov` - Coverage reporting
- `pytest-xdist` - Parallel test execution
- `locust` - Load testing

---

## Future Improvements

### Short-term (Post-MVP)
- [ ] Add code coverage reporting (target: 80%+)
- [ ] Add CI/CD integration (GitHub Actions)
- [ ] Add load testing (100+ concurrent users)
- [ ] Add security tests (SQL injection, XSS)

### Long-term
- [ ] Contract testing (Pact)
- [ ] Chaos engineering tests
- [ ] Accessibility testing (WCAG compliance)
- [ ] Browser automation tests (Playwright)

---

## Notes

- **Philosophy**: Fast, reliable, maintainable tests
- **Test Database**: SQLite in-memory (fast, isolated)
- **Mocking**: External services only (GCS, Supabase Auth)
- **E2E**: Can run against any environment (local, staging, prod)
- **Performance**: Tracks trends, not absolute thresholds

**Questions?** See `tests/README.md` or check individual test files for examples.

---

**Last Updated**: 2025-10-07  
**Coverage**: All Phase 1-7 features fully tested
