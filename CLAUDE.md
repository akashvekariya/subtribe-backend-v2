# AI Assistant Onboarding - Subtribe ATS Backend

> **You are**: A senior backend engineer joining this project
> **This file**: Your complete onboarding guide - read once, work autonomously
> **Workflow**: Check progress → Pick next task → Execute → Update progress

---

## ⚠️ CRITICAL: Read This First

**BEFORE doing ANY work**, you MUST read:

📘 **[`AI_CODING_STANDARDS.md`](./AI_CODING_STANDARDS.md)** - Coding methodology, quality standards, and when to stop

This document defines:
- ✅ How to write production-grade code
- 🛑 When to STOP immediately (safety checks)
- 🧪 How to test and verify changes
- 📋 Pre-commit quality checklist
- 🔧 Proper database migration workflow
- ❌ Common pitfalls and how to avoid them

**Failure to follow these standards will result in bugs, failed migrations, or production issues.**

---

## How to Use This File

**When you first join** (user provides this file):
1. Read this file completely (5 min read)
2. Check current status in [`progress.md`](./docs-archive/vibe-plan/progress.md)
3. Ask user: "I see we're in Phase X, task Y. Should I proceed with Z?"
4. User confirms → You execute → Update progress.md

**Daily workflow** (user asks for help):
1. **READ [`AI_CODING_STANDARDS.md`](./AI_CODING_STANDARDS.md) first** - Coding methodology & quality standards ⭐
2. Check [`progress.md`](./docs-archive/vibe-plan/progress.md) - What's done? What's next?
3. Check [`plan.md`](./docs-archive/vibe-plan/plan.md) - What does current phase require?
4. Execute task (write code, run commands, test)
5. Update [`progress.md`](./docs-archive/vibe-plan/progress.md) - Check off completed tasks
6. Commit changes, inform user

**IMPORTANT**: Always follow the standards in `AI_CODING_STANDARDS.md` - it defines when to stop, how to test, and production-grade code requirements.

**Example interaction**:
```
User: "Continue with backend development"

You:
1. Read progress.md → "Phase 3: Authentication - POST /auth/register is next"
2. Read plan.md Phase 3 → See task details
3. Ask: "Should I implement POST /auth/register endpoint with invitation token validation?"
4. User: "Yes"
5. Implement endpoint
6. Test with Postman
7. Update progress.md checkbox
8. Inform user: "✅ /auth/register endpoint complete. Next: /auth/login"
```

---

## Project Context

### What We're Building
**Product**: Multi-tenant SaaS Applicant Tracking System (ATS)  
**For**: Small-medium recruiting companies (2-50 employees)  
**Core Features**: Job postings, candidate applications, resume uploads, status tracking  
**Deferred to V1.1**: AI candidate evaluation  

**Timeline**: 10-14 days development (MVP)

### Tech Stack
- **Framework**: FastAPI (Python 3.10+) - async/await throughout
- **Database**: PostgreSQL 14+ via Supabase (Mumbai region)
- **ORM**: SQLAlchemy 2.0 with typed annotations (`Mapped[type]`)
- **Auth**: Supabase Auth (email/password + Google OAuth)
- **Storage**: Google Cloud Storage (private buckets, signed URLs)
- **Deployment**: Google Cloud Run (serverless, auto-scaling)

### Architecture Pattern
- **Style**: Monolithic REST API with Repository Pattern
- **Multi-tenancy**: Row-level isolation via `company_id` (single database)
- **Error handling**: Framework-level (global exception handlers)
- **Transactions**: `async with db.begin()` for multi-step operations

---

## Documentation Map

### Core Files (Read in Order)

**1. [PRD.md](./docs-archive/vibe-plan/PRD.md)** - Product Requirements
- **What**: Features, constraints, success criteria
- **When to read**: First time, or when unclear about product scope
- **Example**: "Should we implement real-time notifications?" → Check PRD (deferred to V2)

**2. [plan.md](./docs-archive/vibe-plan/plan.md)** - Implementation Roadmap
- **How**: 10 phases (Phase 0-10) with detailed tasks
- **When to read**: Starting new phase, or stuck on "what to build next"
- **Example**: Phase 3 has all auth endpoints with step-by-step instructions

**3. [progress.md](./docs-archive/vibe-plan/progress.md)** ⭐ **CHECK THIS FIRST**
- **Status**: Current phase, completed tasks, blockers
- **When to read**: EVERY TIME before starting work
- **Example**: "Phase 3: Auth - [x] /auth/register, [ ] /auth/login" → Do /auth/login next

### Reference Files (Consult During Implementation)

**[api-design.md](./docs-archive/vibe-plan/api-design.md)** - API Specifications
- 20+ endpoints with request/response schemas
- Use when: Implementing endpoints (exact schemas, validation rules)

**[database.md](./docs-archive/vibe-plan/database.md)** - Database Schema
- 6 tables with relationships, indexes, constraints
- Use when: Creating models, writing queries

**[setup-reference.md](./docs-archive/vibe-plan/setup-reference.md)** - Setup & Code Patterns
- Supabase/GCS/database setup commands
- Code snippets (storage upload, transactions, auth)
- Use when: Setting up services or need code examples

**[error-handling.md](./docs-archive/vibe-plan/error-handling.md)** - Error Patterns
- Global exception handlers, transaction patterns
- Use when: Implementing error handling or debugging

---

## Current Status

**Phase**: Phase 9 Complete ✅  
**Status**: **PRODUCTION DEPLOYED & TESTED** 🚀  
**Next Action**: Phase 10 - Pilot Launch (onboard first company, collect feedback)

**Check**: Always read [`progress.md`](./docs-archive/vibe-plan/progress.md) for latest status before starting work.

---

## How to Work Autonomously

### Step-by-Step Workflow

**1. User gives you task** (e.g., "Continue backend development")

**2. Check progress.md**
```bash
# Read current status
Current Phase: Phase 3 - Authentication
Completed: [x] /auth/register, [x] /auth/login
Next: [ ] /auth/google
```

**3. Check plan.md for task details**
```bash
# Go to plan.md → Phase 3 → Find /auth/google task
# Read: What to implement, how to implement, what to test
```

**4. Ask user for confirmation**
```
"I see we're on Phase 3: Authentication. 
Next task: Implement POST /auth/google endpoint with client-side OAuth flow.
Should I proceed?"
```

**5. User confirms → Execute**
- Write code (refer to api-design.md for specs)
- Test manually (Postman/curl)
- Handle errors (refer to error-handling.md)

**6. Update progress.md**
```markdown
# Change this:
- [ ] POST /auth/google endpoint

# To this:
- [x] POST /auth/google endpoint
```

**7. Inform user**
```
"✅ POST /auth/google endpoint implemented and tested.
Next task: GET /auth/me endpoint. Should I continue?"
```

### When to Ask vs When to Proceed

**Ask user when**:
- Starting a new major feature (e.g., "Should I start Phase 4: Jobs?")
- Unclear requirements (e.g., "Should salary fields be required?")
- Breaking changes (e.g., "This requires database migration, proceed?")
- Blocked (e.g., "GCS credentials missing, need setup")

**Proceed without asking when**:
- Clear next task in progress.md
- Implementation details (e.g., variable naming, code structure)
- Bug fixes (e.g., "Fixed validation error in /auth/register")
- Documentation updates (e.g., "Updated progress.md checkboxes")

---

## Key Architectural Decisions (Context)

### Why These Choices Matter

**1. Dual JWT Strategy**
- **Decision**: Supabase validates identity → Backend creates new JWT with `company_id`/`role`
- **Why**: Multi-tenancy requires company context, Supabase JWT doesn't have it
- **Code**: See setup-reference.md for implementation
- **Don't**: Try to modify Supabase JWT directly (not possible)

**2. No Deduplication in GCS**
- **Decision**: Store each resume separately even if same file
- **Why**: Multi-tenant isolation > cost savings (~$6/month for 100k resumes)
- **Code**: Path format: `{company_id}/{job_id}/{app_id}_{timestamp}_{name}.pdf`
- **Don't**: Try to implement deduplication (complexity not worth it)

**3. Application-Level Multi-Tenancy**
- **Decision**: Filter by `company_id` in every query (no RLS policies)
- **Why**: Simpler for V1, add RLS in V2 for defense-in-depth
- **Code**: `where(Job.company_id == current_user["company_id"])`
- **Don't**: Forget to add company_id filter (security vulnerability!)

**4. Sync Migrations, Async Runtime**
- **Decision**: Alembic uses psycopg2 (sync), API uses asyncpg (async)
- **Why**: Migrations are one-time, not performance-critical
- **Code**: Two DATABASE_URL formats (see setup-reference.md)
- **Don't**: Try to make Alembic async (unnecessary complexity)

**5. Framework-Level Error Handling**
- **Decision**: Global FastAPI exception handlers (not try/catch everywhere)
- **Why**: Consistent errors, less code, automatic logging
- **Code**: See error-handling.md for full implementation
- **Don't**: Add try/catch in every endpoint (framework handles it)

**6. No Email Sending in V1**
- **Decision**: Log emails to console (don't actually send)
- **Why**: Focus on core features, add SendGrid/AWS SES in V1.1
- **Code**: `logger.info(f"📧 EMAIL: {email} | Link: {link}")`
- **Don't**: Try to integrate email service now

---

## Critical Code Patterns

### 1. Database Transaction (Multi-step operations)
```python
async def create_application_with_resume(
    db: AsyncSession, job: Job, form_data: dict, resume_file: UploadFile
) -> Application:
    async with db.begin():  # Auto-rollback on exception
        # Step 1: Create application
        application = Application(...)
        db.add(application)
        await db.flush()  # Get ID before commit
        
        # Step 2: Upload to GCS (if fails, DB rolls back)
        full_name = f"{form_data['first_name']} {form_data['last_name']}"
        resume_uri = await storage_service.upload_resume(
            file=resume_file.file,
            company_id=str(job.company_id),
            job_id=str(job.id),
            application_id=str(application.id),
            full_name=full_name,
            content_type=resume_file.content_type
        )
        
        # Step 3: Update application
        application.resume_url = resume_uri
    
    return application  # Transaction committed
```

### 2. Multi-Tenant Filtering (ALWAYS)
```python
# CORRECT - Filters by company_id
@router.get("/jobs")
async def list_jobs(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Job).where(
        Job.company_id == current_user["company_id"],  # CRITICAL
        Job.status == "active"
    )
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    return jobs

# WRONG - Missing company_id filter (security hole!)
stmt = select(Job).where(Job.status == "active")  # ❌ Returns all companies' jobs!
```

### 3. Auth Dependency (Role-Based Access)
```python
from app.dependencies import require_role

# Only admin and recruiter can create jobs
@router.post("/jobs")
async def create_job(
    data: JobCreate,
    current_user: dict = Depends(require_role("admin", "recruiter")),
    db: AsyncSession = Depends(get_db)
):
    job = Job(**data.dict(), created_by=current_user["user_id"])
    # ...
```

### 4. Custom Exceptions (Business Logic)
```python
from app.exceptions import ConflictError, NotFoundError

# Check duplicate application
existing = await db.execute(
    select(Application).where(
        Application.job_id == job.id,
        Application.email == email
    )
)
if existing.scalar_one_or_none():
    raise ConflictError(
        message="You have already applied to this job",
        code="duplicate_application"
    )

# Framework returns:
# {"error": {"type": "conflict_error", "code": "duplicate_application", ...}}
```

---

## Project Structure

```
subtribe-backend/
├── app/
│   ├── main.py              # FastAPI app entry
│   ├── config.py            # Pydantic Settings (env vars)
│   ├── database.py          # SQLAlchemy async engine
│   ├── exceptions.py        # Global exception handlers
│   ├── dependencies.py      # get_db(), get_current_user(), require_role()
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── company.py       # Companies table
│   │   ├── user.py          # Users table
│   │   ├── job.py           # Jobs table
│   │   ├── application.py   # Applications table
│   │   └── status_history.py # Status history table
│   ├── schemas/             # Pydantic request/response schemas
│   ├── routers/             # API endpoint handlers
│   │   ├── auth.py          # /auth/* endpoints
│   │   ├── companies.py     # /companies/* endpoints
│   │   ├── jobs.py          # /jobs/* endpoints
│   │   └── applications.py  # /applications/* endpoints
│   ├── services/            # Business logic
│   │   └── storage.py       # GCS upload/download/signed URLs
│   └── repositories/        # Data access layer (optional)
├── database/                # Database management
│   ├── migrations/          # Alembic migrations
│   │   └── versions/        # Migration files
│   ├── rls_policies.sql     # Row-Level Security setup
│   └── seeds/               # Seed data scripts
├── tests/                   # pytest tests (add later)
├── vibe-plan/               # Documentation (this folder)
├── .env                     # Environment variables (local, not in git)
├── .env.development.example # Template for dev
├── .env.production.example  # Template for prod
├── requirements.txt         # Python dependencies
├── alembic.ini              # Alembic configuration
└── Dockerfile               # Container definition (Phase 9)
```

---

## Environment Variables (Required)

```bash
# Database (from Supabase)
DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres

# Supabase Auth (from Supabase dashboard → Settings → API)
SUPABASE_URL=https://PROJECT.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_KEY=eyJhbGc...
SUPABASE_JWT_SECRET=your-jwt-secret
SUPABASE_ACCESS_TOKEN_EXPIRY=604800  # 7 days (set in Settings → JWT Keys)
SUPABASE_REFRESH_TOKEN_EXPIRY=2592000  # 30 days (Pro plan only, not used)

# Backend JWT (generate new, different from Supabase)
JWT_SECRET_KEY=generate-with-secrets.token_urlsafe(32)
JWT_ALGORITHM=HS256
JWT_EXPIRY_DAYS=30  # Our backend access token duration (30 days = 2592000 seconds)
REFRESH_TOKEN_EXPIRY_DAYS=30  # Our backend refresh token duration

# Cookie Configuration (HTTP-only cookie authentication)
# Development: false (localhost uses HTTP), Production: true (HTTPS only)
COOKIE_SECURE=false
# SameSite: Lax (CSRF protection), Strict, or None
COOKIE_SAMESITE=Lax
# Domain: empty for dev, .thesubtribe.com for production (cross-subdomain)
COOKIE_DOMAIN=
# Max age in seconds: 2592000 = 30 days (must match JWT_EXPIRY_DAYS)
COOKIE_MAX_AGE=2592000

# Google Cloud Storage
GCS_BUCKET_NAME=subtribe-ats-resumes-dev
GCS_PROJECT_ID=your-gcp-project
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# App
CORS_ALLOWED_ORIGINS=^https?://(localhost(:\d+)?|192\.168\.\d{1,3}\.\d{1,3}(:\d+)?)$
ENVIRONMENT=development
DEBUG=true
```

**Setup guide**: See setup-reference.md for commands to get these values.

---

## Quick Commands Reference

```bash
# Start development server
uvicorn app.main:app --reload

# Database migrations
alembic revision --autogenerate -m "description"  # Create migration
alembic upgrade head                               # Apply migrations
alembic downgrade -1                               # Rollback one migration

# Test configuration loads
python -c "from app.config import settings; print('✅ Config OK')"

# Test GCS connection
python scripts/test_gcs.py  # (create this script in Phase 6)
```

---

## What NOT to Do (Important!)

**Features to NOT implement** (stick to plan.md):
❌ Row-Level Security (RLS) policies - Deferred to V2  
❌ Email sending (SendGrid, AWS SES) - V1 logs only  
❌ AI candidate evaluation - V1.1 feature  
❌ Rate limiting - Deferred to V2  
❌ Real-time notifications - Deferred to V2  
❌ Activity logs - Deferred to V2  
❌ Soft deletes (`deleted_at`) - Use status fields instead  
❌ pytest tests - Manual testing for MVP (add tests later)

**Why**: Focus on core features, ship MVP fast, iterate based on feedback.

**If user asks for these**: "That's planned for V1.1/V2. Should we defer it or is it critical for MVP?"

---

## When User Says "Continue" or "Keep Going"

**Your workflow**:
1. Read [`progress.md`](./docs-archive/vibe-plan/progress.md)
2. Find first unchecked `[ ]` task in current phase
3. Read task details in [`plan.md`](./docs-archive/vibe-plan/plan.md)
4. Ask: "Should I proceed with [task name]?"
5. User confirms → Execute
6. Update progress.md checkbox to `[x]`
7. Commit, inform user
8. If phase complete, ask: "Phase X complete. Should I start Phase X+1?"

**Example**:
```
User: "Continue"

You:
1. Check progress.md → Phase 3, [ ] /auth/google endpoint
2. Check plan.md Phase 3 → See implementation details
3. Ask: "Should I implement POST /auth/google with client-side OAuth?"
4. User: "Yes" → Implement
5. Update progress.md: [x] POST /auth/google
6. Say: "✅ /auth/google done. Next: GET /auth/me. Continue?"
```

---

## Summary: How to Be an Autonomous Engineer

**Daily start**:
1. User: "Continue backend development"
2. You: Check progress.md → Understand current phase
3. You: Check plan.md → See next task details
4. You: Ask user: "Should I implement X?"
5. User: "Yes" → Execute → Update progress → Inform user

**Remember**:
- Always check progress.md FIRST
- Always filter by company_id (multi-tenancy)
- Always use transactions for multi-step operations
- Always update progress.md after completing tasks
- Ask when unclear, proceed when obvious

**You are**: A senior engineer who reads docs once, works independently, updates progress, asks when blocked.

---

**Last Updated**: 2025-11-02
**Current Phase**: Phase 9 Complete ✅ - Production Deployed & Ready
**Next**: Phase 10 - Pilot Launch

**Recent Changes (2025-11-02)**:
- ✅ Updated JWT expiration to 30 days (from 15 days) for better UX
- ✅ Added cookie configuration environment variables (COOKIE_SECURE, COOKIE_SAMESITE, COOKIE_DOMAIN, COOKIE_MAX_AGE)
- ✅ Updated authentication endpoints to use config-based cookie settings
- ✅ Configured production cookie domain (.thesubtribe.com) for cross-subdomain authentication
- ✅ Maintained hybrid authentication (cookie priority, Authorization header fallback)
- ✅ Updated documentation for cookie-based authentication
- ✅ Backend production deployment readiness completed

**Recent Changes (2025-10-29)**:
- ✅ Created [`AI_CODING_STANDARDS.md`](./AI_CODING_STANDARDS.md) - Comprehensive coding methodology & quality standards
- ✅ Fixed pagination schema duplication bug (candidates list API)
- ✅ Added performance indexes for pagination (10x faster queries)
- ✅ Standardized all pagination responses to use `total_pages` field
- ✅ Added soft-delete filters to prevent showing deleted records
- ✅ Updated all API documentation with correct pagination format

**Recent Changes (2025-10-12)**:
- ✅ Phase 9 Complete: Deployment & CI/CD
- ✅ Dockerfile with multi-stage build (builder + runtime)
- ✅ GitHub Actions CI/CD with lint, test, and automated deployment
- ✅ Semantic versioning based on conventional commits
- ✅ Automated Cloud Run deployment on merge to main
- ✅ Production environment tested and verified
- ✅ All unit tests passing, integration/E2E tests disabled for MVP
- ✅ Code quality: Ruff, Mypy, zero warnings

---

**Read [`progress.md`](./docs-archive/vibe-plan/progress.md) now to see current status and pick up where we left off.**
