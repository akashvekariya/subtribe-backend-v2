# Implementation Plan

> **How**: Step-by-step development roadmap with phases, tasks, and references to detailed documentation.

---

## Overview

**Timeline**: 10-14 days (solo developer)  
**Approach**: MVP-first, test as you build, deploy early  
**Architecture**: Monolithic FastAPI app

---

## Phase 0: Environment Setup (Day 1 - Morning)

### Setup External Services
1. **Supabase** - Create project, get credentials
   - Region: Mumbai (asia-south1)
   - Get: JWT secret, anon key, service key, database URL
   - **Guide**: [`setup-reference.md#supabase`](./setup-reference.md#supabase)

2. **Google Cloud Storage** - Create bucket, service account
   - Bucket: `subtribe-ats-resumes-dev` (Mumbai, Standard)
   - Service account with Storage Object Admin
   - Download JSON key
   - **Guide**: [`setup-reference.md#gcs`](./setup-reference.md#gcs)

3. **Environment** - Configure `.env`
   - Copy `.env.development.example` → `.env`
   - Fill in Supabase + GCS credentials
   - Generate JWT_SECRET_KEY
   - **Guide**: [`setup-reference.md#environment`](./setup-reference.md#environment)

### Initialize Project
```bash
# Create project structure
mkdir -p app/{models,schemas,routers,repositories,services,dependencies}
touch app/{__init__.py,main.py,config.py,database.py}

# Install dependencies
pip install fastapi uvicorn sqlalchemy asyncpg alembic psycopg2-binary \
    pydantic pydantic-settings python-jose google-cloud-storage python-dotenv

# Test configuration loads
python -c "from app.config import settings; print('✅ Config OK')"
```

**Checkpoint**: Services configured, `.env` working

---

## Phase 1: Database & Models (Day 1 - Afternoon)

### Setup Database
1. **Alembic** - Initialize migrations
   ```bash
   alembic init migrations
   # Configure migrations/env.py
   ```
   - **Guide**: [`setup-reference.md#database`](./setup-reference.md#database)

2. **SQLAlchemy Models** - Create 6 tables
   - `app/models/company.py`
   - `app/models/user.py`
   - `app/models/invitation.py`
   - `app/models/job.py`
   - `app/models/application.py`
   - `app/models/status_history.py`
   - **Reference**: [`database.md`](./database.md) for schema details

3. **Run Migration**
   ```bash
   alembic revision --autogenerate -m "Initial schema"
   alembic upgrade head
   ```
   - Verify tables in Supabase dashboard

**Checkpoint**: All 6 tables created in database

---

## Phase 2: Core Setup (Day 2 - Morning)

### Authentication Foundation
1. **Exception Handlers** - `app/exceptions.py`
   - Global error handlers
   - **Reference**: [`error-handling.md`](./error-handling.md)

2. **Dependencies** - `app/dependencies.py`
   - `get_db()` - Database session
   - `get_current_user()` - JWT validation
   - `require_role()` - Role-based access

3. **FastAPI App** - `app/main.py`
   ```python
   app = FastAPI(title="Subtribe ATS")
   register_exception_handlers(app)
   # Add CORS, health check
   ```

**Checkpoint**: App starts, health check works

---

## Phase 3: Authentication (Day 2 - Afternoon)

### Auth Endpoints
Create `app/routers/auth.py`:

1. **POST /auth/register**
   - Validate company_code (lookup in companies table)
   - Create Supabase user
   - Create user in DB with matched company_id
   - Return JWT (auto-login)
   - **Reference**: [`api-design.md#auth`](./api-design.md#auth)

2. **POST /auth/login**
   - Validate with Supabase
   - Create JWT with `company_id` claim
   - JWT expiry: 20 days

3. **GET /auth/me**
   - Return current user + company

4. **POST /auth/logout** (optional)
   - Clear session

### User Registration Strategy ✅ DECIDED: Company Code Signup

**Implementation**:
1. Each company gets unique code (e.g., `ACME-x7k9p2`) stored in `companies.invite_code`
2. Add `POST /auth/register` endpoint:
   - Request: `{email, password, first_name, last_name, company_code}`
   - Validates company_code exists and company is active
   - Creates Supabase user
   - Creates user in DB with matched `company_id`
   - Returns JWT (auto-login)
3. Admin can view/regenerate company code in settings

**Benefits**: Easy team onboarding, no invitation management, self-service

### Bootstrap First Company
```sql
-- Create first company with invite code
INSERT INTO companies (name, slug, invite_code, is_active)
VALUES ('Test Company', 'testco', 'TESTCO-abc123', true);

-- Note the company_id, then manually register first user via API
```

### Test Manually
```bash
# Register first user
curl -X POST http://localhost:8000/auth/register \
  -d '{"email": "admin@test.com", "password": "Test@1234", "first_name": "Admin", "last_name": "User", "company_code": "TESTCO-abc123"}'

# Test login
curl -X POST http://localhost:8000/auth/login \
  -d '{"email": "admin@test.com", "password": "Test@1234"}'

# Verify JWT contains company_id
curl -H "Authorization: Bearer {token}" http://localhost:8000/auth/me
```

**Checkpoint**: Register → Login → JWT contains company_id

---

## Phase 4: Company Profile (Day 3 - Morning)

### Company Management
Create `app/routers/companies.py`:

1. **GET /companies/me** - Get current company
   - Return logo, name, slug, tagline, about, website

2. **PATCH /companies/me** - Update company profile
   - Update logo_url, name, tagline, about, website_url
   - **Important**: These fields shown to candidates on job pages

### Test
```bash
# Get company profile
GET /companies/me

# Update company profile
PATCH /companies/me
{"name": "Acme Corp", "logo_url": "https://...", "tagline": "We build stuff"}
```

**Checkpoint**: Company profile updates work and will be visible to candidates

---

## Phase 5: Jobs (Day 3-4)

### Job Management
Create `app/routers/jobs.py`:

1. **POST /jobs** - Create job
   - Generate slug: `{sanitized-title}-{job-uuid}`
   - Set created_by from JWT
   - Default status: `active`
   - **Reference**: [`api-design.md#jobs`](./api-design.md#jobs)

2. **GET /jobs** - List company's jobs
   - Filter by status (active | closed)
   - Sort by: created_at, applications_count, views_count
   - Paginate (20 per page)

3. **GET /jobs/{id}** - Job details
   - Check company_id matches

4. **PATCH /jobs/{id}** - Update job
   - All users are admin in MVP

5. **GET /public/jobs/{slug}** - Public job page
   - No auth required
   - Only active jobs
   - Increment view count (background task)

### Test
```bash
# Create job
POST /jobs
{
  "title": "Backend Engineer",
  "description": "...",
  "position_type": "full_time",
  "location_type": "remote"
}

# View public page
GET /public/jobs/backend-engineer-xyz
```

**Checkpoint**: CRUD works, public page accessible

---

## Phase 6: Applications & Resume Upload (Day 5-7)

### Application Submission
Create `app/routers/applications.py` + `app/services/storage.py`:

1. **Storage Service** - `app/services/storage.py`
   - `upload_resume()` - Upload to GCS
   - `generate_signed_url()` - Temporary access
   - Filename: `{app_id}_{timestamp}_{name}.{ext}`
   - **Reference**: [`setup-reference.md#gcs`](./setup-reference.md#gcs)

2. **POST /public/jobs/{slug}/apply** - Submit application
   - Validate file (PDF only, <5MB - strict)
   - Collect: first_name, last_name, email, phone, linkedin, github, portfolio
   - **Salary fields**: current_ctc, expected_ctc, notice_period_days
   - **TODO**: Ask user before implementing additional fields
   - Transaction: Create application → Upload resume → Update URL
   - Rollback if upload fails
   - **Reference**: [`error-handling.md#transactions`](./error-handling.md#transactions)

3. **GET /jobs/{job_id}/applications** - List applications
   - Filter by status (applied/screening/interviewing/offer/hired/rejected)
   - Sort by: applied_at, ai_score (future), relevance
   - Paginate (always paginate - expecting 500+ apps/job)

4. **GET /applications/{id}** - Application details
   - Generate signed URL for resume

5. **PATCH /applications/{id}** - Update status
   - Create status history entry

### Test End-to-End
```bash
# Submit application (use Postman with file upload)
POST /public/jobs/{slug}/apply
- first_name: John
- last_name: Doe
- email: john@example.com
- resume: [file]

# View in recruiter dashboard
GET /jobs/{job_id}/applications

# Download resume
GET /applications/{id}/resume
# Returns signed URL, valid 1 hour
```

**Checkpoint**: Full candidate flow works (apply → view → download resume)

---

## Phase 7: Status Management (Day 8)

### Status Tracking
1. **PATCH /applications/{id}** - Change status
   - Applied → Screening → Interviewing → Offer → Hired/Rejected
   - **Must include**: notes field (recruiters need to add context)
   - Create history entry in `application_status_history` with changed_by and timestamp

2. **GET /applications/{id}/history** - Status timeline
   - Show all status changes with notes
   - **Critical**: Recruiters rely on this for collaboration

**Checkpoint**: Can move candidates through pipeline with notes/audit trail

---

## Phase 8: Polish & Testing (Day 9-10)

### Refinements
1. **Error Handling**
   - Verify all exceptions caught
   - Test validation errors
   - Test duplicate submissions

2. **Manual Testing Checklist**
   - [ ] Register → Login → Invite → Register flow
   - [ ] Create job → View public page
   - [ ] Submit application → Upload resume
   - [ ] Change status → View history
   - [ ] Multi-tenant isolation (can't access other company's data)
   - [ ] File upload edge cases (too large, wrong type)

3. **Performance Check**
   - [ ] API responses < 200ms
   - [ ] Resume upload < 5s

4. **Security Audit**
   - [ ] JWT validation on protected routes
   - [ ] Company_id filtering on all queries
   - [ ] GCS bucket is private
   - [ ] No sensitive data in logs

---

## Phase 9: Deployment (Day 11-12)

### Cloud Run Deployment

1. **Create Dockerfile**
   ```dockerfile
   FROM python:3.10-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY . .
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
   ```

2. **Deploy**
   ```bash
   # Build and push
   gcloud builds submit --tag gcr.io/PROJECT_ID/subtribe-ats
   
   # Deploy to Cloud Run
   gcloud run deploy subtribe-ats \
     --image gcr.io/PROJECT_ID/subtribe-ats \
     --platform managed \
     --region asia-south1 \
     --set-env-vars ENVIRONMENT=production \
     --set-secrets DATABASE_URL=database-url:latest \
     --set-secrets JWT_SECRET_KEY=jwt-secret:latest
   ```

3. **Test Production**
   - Verify health check
   - Test login flow
   - Submit test application

**Checkpoint**: App running in production

---

## Phase 10: Pilot Launch (Day 13-14)

### Onboard First Customers
1. **Create companies** (SQL script for each)
2. **Invite admins**
3. **Training/support**
4. **Monitor errors** (Sentry, logs)

### Gather Feedback
- What's working?
- What's confusing?
- What's missing?

---

## Development Tips

### Daily Workflow
```bash
# Morning: Pull latest, check progress
git pull
cat progress.md

# Development
# - Build one feature at a time
# - Test with Postman after each endpoint
# - Commit frequently

# Evening: Update progress
# Update progress.md with what's done
git add .
git commit -m "Implemented {feature}"
git push
```

### Testing Strategy
- **Unit tests**: Skip for MVP (manual testing faster)
- **Integration tests**: Manual via Postman
- **E2E test**: Full flow (apply → hire)
- **Add pytest later** when patterns stabilize

### When Stuck
1. Check reference docs (api-design.md, database.md)
2. Check setup-reference.md for configuration
3. Check error-handling.md for patterns
4. Google error messages
5. Ask AI assistant

---

## References

- **API Specs**: [`api-design.md`](./api-design.md)
- **Database Schema**: [`database.md`](./database.md)
- **Setup Guides**: [`setup-reference.md`](./setup-reference.md)
- **Error Patterns**: [`error-handling.md`](./error-handling.md)
- **Progress Tracking**: [`progress.md`](./progress.md)

---

**Next**: Start Phase 0, update [`progress.md`](./progress.md) as you complete each phase.

