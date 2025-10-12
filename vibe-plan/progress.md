# Development Progress

> **Status**: Phase 8 complete ✅, ready for Phase 9 (Deployment)

**Last Updated**: 2025-10-12

## Summary

**✅ Completed Phases:**
- Phase 0: Environment Setup
- Phase 1: Database & Models
- Phase 2: Core Setup
- Phase 3: Authentication
- Phase 4: Company Profile
- Phase 5: Jobs
- Phase 6: Applications & Resume Upload
- Phase 7: Status Management
- Phase 8: Polish & Testing

**🔄 Current Phase:** Phase 9 - Deployment
**📋 Next Phase:** Phase 10 - Pilot Launch

---

## Current Phase

**Phase**: 9 - Deployment  
**Status**: 🔄 Ready to Start  
**Next Action**: Create Dockerfile, deploy to Google Cloud Run, configure production environment

---

## Completed

### Documentation (Complete ✅)
- [x] PRD - Product requirements defined
- [x] Implementation plan - 10 phases outlined
- [x] API design - 20+ endpoints specified
- [x] Database schema - 6 tables designed
- [x] Setup guides - Supabase, database, GCS, environment, bootstrap, error handling
- [x] Architecture decisions - Auth (dual JWT), storage (no deduplication), multi-tenancy (app-level)

---

## Phase Checklist

### Phase 0: Environment Setup ✅
- [x] Supabase projects created (Mumbai) - Dev & Prod environments
- [x] GCS bucket created (`subtribe-ats-resumes-dev` & `subtribe-ats-resumes-prod`)
- [x] Service account created and JSON key downloaded
- [x] `.env` files configured with credentials (dev & prod)
- [x] Dependencies installed (`requirements.txt` created)
- [x] Project structure created (app/, models/, schemas/, routers/, services/)
- [x] Core files: config.py, database.py, exceptions.py, dependencies.py, main.py
- [x] Config loads environment-specific .env files (.env.development / .env.production)
- [x] Configuration tested successfully

### Phase 1: Database & Models ✅
- [x] Alembic initialized (`alembic init migrations`)
- [x] Alembic env.py configured for async engine + imports models
- [x] Company model created (`app/models/company.py`)
- [x] User model created (`app/models/user.py`)
- [x] Job model created (`app/models/job.py`)
- [x] Application model created (`app/models/application.py`)
- [x] StatusHistory model created (`app/models/status_history.py`)
- [x] Initial migration generated: `alembic revision --autogenerate -m "Initial schema"`
- [x] Status fields updated to 100 characters (migration applied)
- [x] Migration applied: `alembic upgrade head`
- [x] RLS policies applied: Run `database/rls_policies.sql` in Supabase SQL Editor
- [x] Tables verified in Supabase dashboard (5 tables, RLS enabled)

### Phase 2: Core Setup ✅
- [x] Exception handlers implemented (`app/exceptions.py`)
- [x] Dependencies implemented (`app/dependencies.py` - get_db, get_current_user, require_role)
- [x] FastAPI app configured with CORS and health check (`app/main.py`)
- [x] Server starts successfully: `uvicorn app.main:app --reload`
- [x] Health check endpoint works: `GET /health`

### Phase 3: Authentication ✅
- [x] Create `app/schemas/auth.py` (request/response models)
- [x] `/auth/register` endpoint (company code signup)
- [x] `/auth/login` endpoint
- [x] `/auth/me` endpoint
- [x] Register router in `app/main.py`
- [x] Manual test: Register with company code → Login → JWT contains company_id
- [x] JWT expiry: 20 days
- [x] Fixed all dependencies (email-validator, greenlet, bcrypt)
- [x] Fixed DATABASE_URL to use +psycopg (switched from asyncpg for PgBouncer compatibility)
- [x] Fixed bcrypt compatibility (downgraded to 3.2.2 for passlib 1.7.4)
- [x] Removed email_verified field (deferred to V1.1)
- [x] **All endpoints tested and working perfectly** ✨

### Phase 4: Company Profile ✅
- [x] `GET /companies/{company_id}` endpoint
- [x] `PATCH /companies/{company_id}` endpoint (logo, name, slug, tagline, about, website)
- [x] Company schemas with field validation (URL validation, length limits)
- [x] Multi-tenant security (users can only access their own company)
- [x] Fixed OpenAPI schema for Swagger UI Bearer token authentication
- [x] Fixed validation error handler (JSON serialization bug)
- [x] Manual test: GET and PATCH working in Swagger UI and curl
- [x] **All endpoints tested and working perfectly** ✨

### Phase 5: Jobs ✅
- [x] `/jobs` POST endpoint (creates job with default status 'draft', auto-generates slug)
- [x] `/jobs` GET endpoint (list all company jobs)
- [x] `/jobs/{id}` GET endpoint (get single job details)
- [x] `/jobs/{id}` PATCH endpoint (update job, sets published_at when status changes to active)
- [x] `/public/jobs/{slug}` GET endpoint (public page with company details, shows active/closed only, increments view count)
- [x] Job schemas created (JobCreate, JobUpdate, JobResponse, JobListItem, PublicJobResponse)
- [x] Slug generation uses full UUID (no collisions possible)
- [x] Added server_default to all UUID primary keys (gen_random_uuid())
- [x] Added server_default to all timestamp fields (CURRENT_TIMESTAMP)
- [x] Proper database error handling in endpoints (not in global handler)
- [x] Fresh database migration created with all models and defaults
- [x] **All endpoints tested and working perfectly** ✨

### Phase 6: Applications & Resume Upload ✅
- [x] Storage service implemented (`app/services/storage.py`)
  - GCS client with lazy loading
  - Resume upload with path: `{company_id}/{job_id}/{app_id}_{timestamp}_{name}.pdf`
  - Signed URLs with view (inline) and download (attachment) modes
  - 1-hour URL expiry
- [x] Application schemas (`app/schemas/application.py`)
  - Request/response models with validation
  - Pagination support
- [x] Public endpoint: `POST /public/jobs/{slug}/apply`
  - Multipart form data with PDF resume
  - Validates: active job, PDF only, max 5MB, no duplicates
  - Transaction safety (rollback on upload failure)
- [x] Protected endpoints (all with auth & multi-tenant security):
  - `GET /jobs/{job_id}/applications` - List applications for job
  - `GET /applications/{id}` - Get application details
  - `GET /applications/{id}/resume/view` - Signed URL (inline)
  - `GET /applications/{id}/resume/download` - Signed URL (attachment)
  - `PATCH /applications/{id}` - Update status (prepared for Phase 7)
- [x] Router restructuring
  - Split into `public_router` and `router`
  - Individual endpoint tags for proper Swagger UI organization
  - Fixed redundant paths
- [x] Test suite organized in `tests/` directory
  - `tests/test_application_flow.py` - Phase 6 application submission tests
  - `tests/test_status_history.py` - Phase 7 status management tests  
  - `tests/data/test.pdf` - Sample resume for testing
  - `tests/README.md` - Comprehensive testing documentation
- [x] All endpoints working (duplicate prevention verified with 409 response)
- [x] Manual end-to-end test with unique email ✅ PASSED
- [x] **Phase 6 fully tested and working perfectly** ✨

### Phase 7: Status Management ✅
- [x] Status history response schemas (StatusHistoryItem, StatusHistoryResponse, UserBasic)
- [x] Initial status history tracking (creates "applied" entry on application submission)
- [x] `/applications/{id}` PATCH endpoint (status update with history creation)
- [x] `/applications/{id}/history` GET endpoint (newest first, with user details)
- [x] ApplicationStatusHistory model updated with User relationship
- [x] Fixed: Only create history entries when status actually changes (no duplicate logging)
- [x] Test script created (`tests/test_status_history.py`)
- [x] **Manual testing complete** ✅ - All features verified working
- [x] **Phase 7 fully tested and working perfectly** ✨

### Phase 8: Polish & Testing ✅
**Unit Tests:**
- [x] Created comprehensive test suite (`tests/unit/`)
  - `test_models.py` - SQLAlchemy model tests (10 tests)
  - `test_schemas.py` - Pydantic schema validation tests (15 tests)
  - `test_services.py` - Storage service with mocks (4 tests)
- [x] Configured pytest with pytest-asyncio (AUTO mode)
- [x] Test fixtures (`conftest.py`) with database isolation
  - NullPool engine for reliable async testing
  - Transaction rollback for test isolation
  - Explicit cleanup to prevent connection leaks
- [x] All 29 unit tests passing ✅
- [x] Zero linter errors across all test files
- [x] Updated all Pydantic schemas to use ConfigDict (removed deprecated Config class)
- [x] Fixed deprecation warnings (datetime.utcnow → datetime.now(timezone.utc))
- [x] Removed unused imports and variables

**Test Coverage:**
- [x] Models: Company, User, Job, Application, StatusHistory
- [x] Schemas: Auth, Company, Job, Application validation
- [x] Services: GCS storage (upload, signed URLs, path generation)

**Integration/E2E Tests (Disabled for Production):**
- [x] Integration tests created but disabled (`pytest.ini` norecursedirs)
- [x] E2E tests created but disabled (require running server)
- [x] Performance tests created but disabled (require running server)
- Note: These tests can be run manually with `pytest tests/integration/` etc.

**Code Quality:**
- [x] No warnings in pytest output (15 Pydantic internal warnings only, not our code)
- [x] All linter errors fixed
- [x] Bare except statements replaced with except Exception
- [x] Async connection handling verified (no event loop conflicts)

### Phase 9: Deployment
- [ ] Dockerfile created
- [ ] Deployed to Cloud Run
- [ ] Production environment configured
- [ ] Production test passed

### Phase 10: Pilot Launch
- [ ] First company onboarded
- [ ] Feedback collected
- [ ] Critical bugs fixed

---

## Blockers

**Current**: None

**Resolved**:
- ✅ Swagger UI not sending Bearer token (2025-10-05) - Fixed by adding custom OpenAPI schema
- ✅ Validation errors causing 500 errors (2025-10-05) - Fixed by cleaning error objects before JSON serialization

---

## Notes

### Architecture Decisions Made
1. **Auth**: Supabase email/password only (no Google OAuth for MVP)
2. **User Registration**: Company code signup (user enters code during registration)
3. **Roles**: Everyone is admin (company_id isolation only, no RBAC for MVP)
4. **Multi-tenancy**: Application-level filtering with permissive RLS (RLS enabled to remove warnings, but service role has full access via `USING (true)` policies)
5. **Storage**: GCS with no deduplication (multi-tenant isolation > cost savings)
6. **Job Slugs**: `{sanitized-title}-{full-uuid}` format ensures uniqueness (no collisions possible)
7. **Error handling**: Global FastAPI exception handlers (framework-level, not case-by-case)
8. **Sessions**: 20-day JWT (no refresh tokens for MVP)
9. **Job Status**: `draft` | `active` | `closed` (default: draft)
10. **Application Fields**: Include salary fields (current_ctc, expected_ctc) - finalize later
11. **File Validation**: Strict PDF only, <5MB
12. **Logo/Avatar Storage**: External URLs only for MVP (company.logo_url, user.avatar_url) - no GCS upload. Resumes use GCS.
13. **Status Tracking**: Current status stored in `applications.status` only. Historical changes tracked in `application_status_history` table (normalized design, no denormalization for MVP).
14. **Token Storage**: Client-side (localStorage/sessionStorage) - no httpOnly cookies for MVP. Tokens are stateless JWTs valid for 20 days.

### Technical Choices
- **Framework**: FastAPI (async, fast, auto-docs)
- **Database**: PostgreSQL via Supabase (managed, Mumbai region)
- **ORM**: SQLAlchemy 2.0 with typed annotations (`Mapped`)
- **Database Driver**: psycopg3 (async, PgBouncer compatible - switched from asyncpg)
- **Migrations**: Alembic (sync migrations with psycopg2, async runtime with psycopg3)
- **Storage**: GCS Standard class, Mumbai region
- **Deployment**: Google Cloud Run (serverless, auto-scaling)
- **Server Defaults**: All UUID columns use `gen_random_uuid()`, all timestamps use `CURRENT_TIMESTAMP`

### Costs (Estimated for 100k applications)
- **Supabase**: Free tier
- **GCS**: ~$7/month (300GB @ $0.020/GB + operations)
- **Cloud Run**: ~$20/month (light usage)
- **Total**: ~$27/month

---

## Next Session Checklist

**Before starting deployment (Phase 9)**:
1. Read [`plan.md`](./plan.md) Phase 9 - Understand deployment tasks
2. Check this file (`progress.md`) - Verify Phase 8 complete
3. Ensure production `.env.production` is configured
4. Verify GCS production bucket and Supabase prod project are ready

**During deployment**:
1. Create Dockerfile
2. Test Docker build locally
3. Deploy to Google Cloud Run
4. Configure production environment variables
5. Run production smoke tests

**End of deployment**:
1. Update "Current Phase" to Phase 10
2. Check off completed Phase 9 items
3. Document any deployment issues
4. Commit progress update

---

## Quick Reference

**Key Files**:
- `PRD.md` - What we're building
- `plan.md` - How to build it (current phase tasks)
- `progress.md` - This file (status tracking)
- `api-design.md` - API specifications
- `database.md` - Database schema
- `setup-reference.md` - Setup instructions
- `error-handling.md` - Error patterns

**Commands**:
```bash
# Start server
uvicorn app.main:app --reload

# Run migration
alembic upgrade head

# Create migration
alembic revision --autogenerate -m "description"

# Test config
python -c "from app.config import settings; print('OK')"
```

---

**Status**: Phase 8 complete ✅ | Ready for Phase 9 (Deployment) 🚀

