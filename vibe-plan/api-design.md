# API Design Document

> **TLDR**: Complete REST API specification for Subtribe ATS. 20+ endpoints covering auth, jobs, applications, users. Authentication via Supabase (JWT), dual support (cookies + Bearer token). Error format: Stripe-inspired JSON. Pagination: offset-based. Multi-tenancy: auto-scoped via JWT `company_id`. File upload: through backend to GCS. Background tasks: FastAPI BackgroundTasks (MVP). **See**: [`./database.md`](./database.md) for data models, [`./NEXT-STEPS.md`](./NEXT-STEPS.md) for implementation order.

---

## 1. Overview

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Style** | RESTful API | Simple, standard, well-understood |
| **Framework** | FastAPI (async) | Modern, fast, auto-docs, type-safe |
| **Auth** | Supabase Auth (JWT) | Email/password + Google OAuth |
| **Token Delivery** | Cookies + Bearer header | Flexibility for different clients |
| **API Versioning** | None for V1 | Add `/api/v1` when needed |
| **Response Format** | JSON (full objects) | RESTful, reduces API calls |
| **Error Format** | Stripe/Slack-inspired | Consistent, developer-friendly |
| **Multi-Tenancy** | JWT `company_id` claim | Auto-scope all queries |

---

## 2. Authentication & Authorization

### 2.1. Authentication Flow (MVP Simplified)

**Supported Methods**:
- ✅ Email/Password via Supabase Auth
- ❌ Google OAuth (removed for MVP)

**Token Delivery**: 
- `Authorization: Bearer {token}` header
- JWT expiry: **20 days** (no refresh tokens for MVP)

### 2.2. JWT Structure (MVP Simplified)

Custom claims added by backend after Supabase auth:
- `company_id`: User's company UUID
- ~~`role`~~: Removed (everyone is admin in MVP)

**Implementation**: Create custom JWT with `company_id` claim post-Supabase auth, return to client. 20-day expiry.

### 2.3. JWT Validation

**FastAPI Dependency**: `get_current_user(request: Request) -> dict`
- Extracts token from cookie or Authorization header
- Validates with Supabase JWT secret
- Returns: `{"user_id", "company_id", "role", "email"}`
- Raises 401 if invalid/missing

### 2.4. Role-Based Access Control ❌ REMOVED FOR MVP

**Decision**: Everyone is admin with full access
- Simplifies MVP, faster to ship
- Multi-tenancy still enforced via `company_id` filtering
- **Future**: Add RBAC in V1.1

---

## 3. Multi-Tenancy Implementation

**Approach**: Auto-inject `company_id` filter in all queries
- Extract `company_id` from JWT
- Set PostgreSQL session variable: `SET LOCAL app.current_company_id = '{company_id}'`
- RLS policies enforce isolation (optional for V1)

**For MVP**: Skip RLS, just use application-level filtering in repositories.

---

## 4. API Endpoints

### 4.1. Authentication Endpoints

#### POST `/auth/register`
**Purpose**: Register new user with company code  
**Auth**: None

**Request**:
```json
{
  "email": "string (required, valid email)",
  "password": "string (required, min 8 chars)",
  "first_name": "string (required)",
  "last_name": "string (required)",
  "company_code": "string (required, e.g., ACME-x7k9p2)"
}
```

**Response** (201):
```json
{
  "user": {
    "id": "uuid",
    "email": "string",
    "first_name": "string",
    "last_name": "string",
    "company": {"id": "uuid", "name": "string", "slug": "string"}
  },
  "access_token": "jwt-string",
  "expires_at": "timestamp (20 days from now)"
}
```

**Side Effects**:
- Creates Supabase auth user
- Creates user in `users` table with matched `company_id`
- Auto-login (returns JWT)

**Validation**:
- Company code must exist and company must be active
- Email must not already exist
- Password min 8 characters

**Errors**:
- 400: Invalid company code
- 409: Email already registered

---

#### POST `/auth/login`
**Purpose**: Login with email/password  
**Auth**: None

**Request**:
```json
{
  "email": "string",
  "password": "string"
}
```

**Response** (200):
```json
{
  "user": {
    "id": "uuid",
    "email": "string",
    "first_name": "string",
    "last_name": "string",
    "company": {"id": "uuid", "name": "string", "slug": "string"}
  },
  "access_token": "jwt-string",
  "expires_at": "timestamp (20 days from now)"
}
```

**Side Effects**:
- Validates with Supabase
- Creates JWT with `company_id` claim
- Updates `last_login_at`

---

#### POST `/auth/google` ❌ REMOVED FOR MVP
**Decision**: Email/password only for MVP
- **Reason**: OAuth adds complexity, can add later based on user demand
- **Future**: Implement in V1.1 if requested

---

#### POST `/auth/logout`
**Purpose**: Logout user  
**Auth**: Required

**Response** (200):
```json
{
  "message": "Logged out successfully"
}
```

**Side Effects**:
- Revokes Supabase session
- Client should discard JWT

---

#### GET `/auth/me`
**Purpose**: Get current user info  
**Auth**: Required

**Response** (200):
```json
{
  "id": "uuid",
  "email": "string",
  "first_name": "string",
  "last_name": "string",
  "avatar_url": "string?",
  "company": {
    "id": "uuid",
    "name": "string",
    "slug": "string",
    "logo_url": "string?",
    "settings": {}
  },
  "last_login_at": "timestamp"
}
```

---

### 4.2. Invitation Endpoints ❌ REMOVED FOR MVP

**Decision**: Admin creates users manually or via simple company code signup
- See plan.md Phase 3 for user registration strategy
- **Future**: Re-implement invitation flow in V1.1

---

### 4.3. Company Endpoints

#### GET `/companies/me`
**Purpose**: Get current user's company  
**Auth**: Required

**Response** (200):
```json
{
  "id": "uuid",
  "name": "string",
  "slug": "string",
  "invite_code": "string",
  "domain": "string?",
  "logo_url": "string?",
  "website_url": "string?",
  "tagline": "string?",
  "about": "text?",
  "settings": {},
  "plan": "free|starter|pro",
  "created_at": "timestamp"
}
```

**Note**: `invite_code` is shown to admin for sharing with team members

---

#### PATCH `/companies/me`
**Purpose**: Update company settings  
**Auth**: Required (admin only)

**Request** (partial update):
```json
{
  "name": "string?",
  "logo_url": "string?",
  "tagline": "string?",
  "about": "text?",
  "website_url": "string?"
}
```

**Note**: These fields are shown to candidates on public job pages

**Response** (200): Updated company object

---

### 4.4. User Endpoints ❌ REMOVED FOR MVP

**Decision**: Manage users directly via SQL/Supabase dashboard
- **Reason**: No RBAC in MVP, everyone is admin
- **Future**: Add user management when implementing roles in V1.1

---

### 4.5. Job Endpoints

#### POST `/jobs`
**Purpose**: Create job posting  
**Auth**: Required (admin, recruiter)

**Request**:
```json
{
  "title": "string (required)",
  "description": "string (markdown, required)",
  "position_type": "full_time|part_time|contract|internship",
  "primary_role": "string",
  "experience_level": "entry|mid|senior|lead|principal",
  "department": "string?",
  "location_type": "remote|hybrid|onsite",
  "location_city": "string?",
  "location_state": "string?",
  "location_country": "string (default: United States)",
  "remote_policy": "remote_only|hybrid|onsite_only",
  "accepted_timezones": ["string"],
  "visa_sponsorship": false,
  "relocation_assistance": false,
  "salary_min": "integer?",
  "salary_max": "integer?",
  "salary_currency": "string (default: USD)",
  "equity_offered": false,
  "required_skills": ["string"],
  "preferred_skills": ["string"],
  "screening_questions": [
    {
      "id": "string",
      "question": "string",
      "type": "text|textarea|number|select",
      "required": true,
      "order": 1,
      "options": ["string"] // for select type
    }
  ],
  "status": "active|closed"
}
```

**Response** (201):
```json
{
  "id": "uuid",
  "company_id": "uuid",
  "created_by": "uuid",
  "title": "string",
  "slug": "{sanitized-title}-{job-uuid}",
  "status": "active",
  "public_url": "https://app.example.com/public/jobs/{slug}",
  "created_at": "timestamp",
  ...all other fields
}
```

**Notes**:
- `slug` format: `{sanitized-title}-{job-uuid}` (e.g., `backend-engineer-a1b2c3d4`)
- `created_by` auto-filled from JWT
- `company_id` auto-filled from JWT
- Default status: `active` (no draft state in MVP)

---

#### GET `/jobs`
**Purpose**: List jobs for company  
**Auth**: Required

**Query Params**:
- `status`: active|closed
- `search`: Search in title/description (optional for MVP)
- `sort`: created_at, applications_count, views_count (default: `-created_at`)
- `page`, `limit`: Pagination

**Response** (200):
```json
{
  "data": [
    {
      "id": "uuid",
      "title": "string",
      "slug": "string",
      "status": "string",
      "position_type": "string",
      "location_type": "string",
      "applications_count": 42,
      "views_count": 156,
      "created_by": {"id": "uuid", "first_name": "string", "last_name": "string"},
      "published_at": "timestamp",
      "created_at": "timestamp"
    }
  ],
  "pagination": {...}
}
```

---

#### GET `/jobs/{job_id}`
**Purpose**: Get job details  
**Auth**: Required

**Response** (200): Full job object with all fields

---

#### PATCH `/jobs/{job_id}`
**Purpose**: Update job  
**Auth**: Required

**Request**: Partial update (any fields from POST `/jobs`)

**Response** (200): Updated job object

**Notes**:
- Changing status to `active` sets `published_at` if null
- MVP: Only `active` and `closed` statuses

---

#### DELETE `/jobs/{job_id}` ⚠️ OPTIONAL FOR MVP
**Purpose**: Delete job (change status to `closed`)  
**Auth**: Required

**Alternative**: Just use PATCH to change status to `closed`

---

### 4.6. Application Endpoints

#### GET `/jobs/{job_id}/applications`
**Purpose**: List applications for a job  
**Auth**: Required

**Query Params**:
- `status`: applied|screening|interviewing|offer|hired|rejected
- `applied_after`: ISO 8601 date
- `applied_before`: ISO 8601 date
- `sort`: `-ai_score`, `applied_at` (default: `-applied_at`)
- `page`, `limit`: Pagination

**Response** (200):
```json
{
  "data": [
    {
      "id": "uuid",
      "job_id": "uuid",
      "first_name": "string",
      "last_name": "string",
      "email": "string",
      "phone": "string?",
      "linkedin_url": "string?",
      "resume_url": "string",
      "status": "string",
      "ai_score": 85,
      "ai_summary": "Strong match for Python...",
      "applied_at": "timestamp"
    }
  ],
  "pagination": {...}
}
```

---

#### GET `/applications/{application_id}`
**Purpose**: Get application details  
**Auth**: Required

**Response** (200):
```json
{
  "id": "uuid",
  "job": {"id": "uuid", "title": "string", "slug": "string"},
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone": "string?",
  "linkedin_url": "string?",
  "github_url": "string?",
  "portfolio_url": "string?",
  "resume_url": "string",
  "resume_filename": "string",
  "screening_answers": {},
  "status": "string",
  "ai_evaluation": {
    "score": 85,
    "summary": "string",
    "breakdown": {},
    "evaluated_at": "timestamp"
  }?,
  "source": "string?",
  "applied_at": "timestamp",
  "created_at": "timestamp"
}
```

---

#### PATCH `/applications/{application_id}`
**Purpose**: Update application status  
**Auth**: Required

**Request**:
```json
{
  "status": "screening|interviewing|offer|hired|rejected",
  "notes": "string (REQUIRED - recruiters need context)"
}
```

**Response** (200): Updated application object

**Side Effects**:
- Creates entry in `application_status_history`
- Updates application `status`

---

#### GET `/applications/{application_id}/history`
**Purpose**: Get status change history  
**Auth**: Required

**Response** (200):
```json
{
  "data": [
    {
      "id": "uuid",
      "from_status": "applied",
      "to_status": "screening",
      "changed_by": {"id": "uuid", "full_name": "string"},
      "notes": "string?",
      "created_at": "timestamp"
    }
  ]
}
```

---

### 4.7. Public Endpoints

#### GET `/public/jobs/{slug}`
**Purpose**: Get public job posting for candidates  
**Auth**: None

**Response** (200):
```json
{
  "id": "uuid",
  "company": {
    "name": "string",
    "logo_url": "string?",
    "website_url": "string?"
  },
  "title": "string",
  "description": "string (markdown)",
  "position_type": "string",
  "primary_role": "string",
  "experience_level": "string",
  "department": "string?",
  "location_type": "string",
  "location_city": "string?",
  "location_state": "string?",
  "location_country": "string",
  "remote_policy": "string",
  "visa_sponsorship": false,
  "relocation_assistance": false,
  "salary_min": "integer?",
  "salary_max": "integer?",
  "salary_currency": "string",
  "equity_offered": false,
  "required_skills": ["string"],
  "screening_questions": [...],
  "published_at": "timestamp"
}
```

**Notes**:
- Only returns `active` jobs
- Increments `views_count` (async, non-blocking)
- Does NOT include: `company_id`, `created_by`, sensitive fields

---

#### POST `/public/jobs/{slug}/apply`
**Purpose**: Submit job application  
**Auth**: None  
**Content-Type**: `multipart/form-data`

**Request**:
```
first_name: string (required)
last_name: string (required)
email: string (required, valid email)
phone: string (optional)
linkedin_url: string (optional, valid URL)
github_url: string (optional, valid URL)
portfolio_url: string (optional, valid URL)
current_ctc: integer (optional, in base currency)
expected_ctc: integer (optional)
notice_period_days: integer (optional)
resume: File (required, PDF ONLY, max 5MB)
screening_answers: JSON string ({"q1": "answer1", ...})

**TODO**: Finalize fields with user before implementing
```

**Response** (201):
```json
{
  "id": "uuid",
  "message": "Application submitted successfully",
  "confirmation_email_sent": true
}
```

**Validation**:
- Resume: Required, **PDF ONLY** (strict), max 5MB
- Email: Valid format, unique per job (no duplicate applications)
- Screening answers: Validate against job's screening questions (if present)

**Background Tasks** (MVP: synchronous upload for reliability):
1. Upload resume to GCS (synchronous)
2. Parse resume text (background)
3. Send confirmation email (background, or just log for V1)

**Errors**:
- 400: Invalid file type, file too large, validation errors
- 404: Job not found or not active
- 409: Duplicate application (email already applied to this job)

---

## 5. Pagination

**Strategy**: Offset-based pagination (simple, good for < 1000 records)

**Query Parameters**:
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20, max: 50)

**Response Format**:
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 42,
    "total_pages": 3,
    "has_more": true
  }
}
```

**Configuration**: Set in `app/config.py`:
```python
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
```

**Future**: Switch to cursor-based pagination if performance issues with large datasets.

---

## 6. Error Handling

### 6.1. Error Response Format

**Inspired by Stripe/Slack**:
```json
{
  "error": {
    "type": "validation_error",
    "code": "invalid_email",
    "message": "The email address provided is invalid",
    "param": "email"
  }
}
```

**Error Types**:
- `authentication_error` (401)
- `authorization_error` (403)
- `validation_error` (400)
- `not_found_error` (404)
- `conflict_error` (409)
- `server_error` (500)

### 6.2. HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Successful GET, PATCH |
| 201 | Created | Successful POST (resource created) |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Validation errors, malformed requests |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Resource already exists, duplicate |
| 422 | Unprocessable Entity | Valid syntax, business logic error |
| 500 | Internal Server Error | Unexpected server errors |

### 6.3. Validation Errors (Multiple Fields)

```json
{
  "error": {
    "type": "validation_error",
    "code": "validation_failed",
    "message": "Request validation failed",
    "errors": [
      {
        "field": "email",
        "code": "invalid_format",
        "message": "Invalid email format"
      },
      {
        "field": "phone",
        "code": "required",
        "message": "Phone number is required"
      }
    ]
  }
}
```

### 6.4. Common Error Codes

**Authentication**:
- `missing_token`, `token_expired`, `invalid_token`, `invalid_credentials`

**Authorization**:
- `insufficient_permissions`, `company_mismatch`

**Validation**:
- `required`, `invalid_format`, `invalid_file_type`, `file_too_large`, `invalid_choice`, `out_of_range`

**Not Found**:
- `resource_not_found`, `job_not_found`, `application_not_found`

**Conflict**:
- `duplicate_email`, `duplicate_slug`, `duplicate_application`

---

## 7. Configuration Management

**File**: `app/config.py`

```python
from pydantic import BaseSettings

class Settings(BaseSettings):
    # App
    APP_NAME: str = "Subtribe ATS"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 20
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_JWT_SECRET: str
    SUPABASE_SERVICE_KEY: str
    
    # GCS
    GCS_BUCKET_NAME: str
    GCS_PROJECT_ID: str
    GOOGLE_APPLICATION_CREDENTIALS: str
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 50
    
    # File Upload
    MAX_RESUME_SIZE_MB: int = 5
    ALLOWED_RESUME_TYPES: list[str] = ["pdf", "docx"]
    
    # Invitation
    INVITATION_EXPIRY_HOURS: int = 48
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

**Environment Variables**: Create `.env.example` (see [`./NEXT-STEPS.md`](./NEXT-STEPS.md))

---

## 8. File Upload Implementation

**Strategy**: Upload through backend (Option B)

**Flow**:
1. Receive file in `POST /public/jobs/{slug}/apply`
2. Validate file type (PDF/DOCX) and size (< 5MB)
3. **Upload to GCS synchronously** (before responding, to avoid data loss)
4. Store GCS path in `application.resume_url`
5. Background: Parse resume text, send confirmation email

**GCS Path Format**: `{company_id}/{job_id}/{application_id}/{filename}`

**Why Synchronous Upload?**:
- Avoids data loss if server crashes after response
- Resume is critical data, worth 2-3 second latency
- Can optimize later if needed

**Resume Parsing**: Use `pypdf` or `pdfplumber` for PDF, `python-docx` for DOCX.

---

## 9. Background Tasks

**V1 MVP Approach**: FastAPI `BackgroundTasks`

```python
@router.post("/public/jobs/{slug}/apply")
async def submit_application(
    background_tasks: BackgroundTasks,
    ...
):
    # 1. Validate input
    # 2. Upload resume to GCS (synchronous)
    # 3. Create application record
    
    # Background tasks (non-critical)
    background_tasks.add_task(parse_resume_text, application.id, resume_bytes)
    background_tasks.add_task(send_confirmation_email, email, first_name, last_name, job.title)
    
    return {"id": application.id, "message": "Application submitted"}
```

**Limitations**:
- Not durable (lost if server crashes)
- No retries
- Good enough for < 50 applications/day

**Future**: Upgrade to Cloud Tasks or Celery when volume increases.

---

## 10. Testing Strategy

**Coverage Requirement**: 90%+

**Test Structure**:
```
tests/
  unit/
    test_auth.py
    test_jobs.py
    test_applications.py
  integration/
    test_api_auth.py
    test_api_jobs.py
    test_api_applications.py
  fixtures/
    database.py
    auth.py
```

**Key Testing Patterns**:
- Mock Supabase Auth responses
- Mock GCS uploads
- Use separate test database
- Reset database between tests
- Create reusable fixtures (test user, test company, test job)

**Example Test**:
```python
def test_create_job(test_client, auth_headers, test_user):
    response = test_client.post(
        "/jobs",
        headers=auth_headers,
        json={"title": "Backend Engineer", "description": "...", ...}
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Backend Engineer"
```

---

## 11. API Documentation

FastAPI auto-generates OpenAPI docs:
- `/docs` - Swagger UI (interactive)
- `/redoc` - ReDoc (clean, documentation-focused)
- `/openapi.json` - OpenAPI spec

**Customization**:
```python
app = FastAPI(
    title="Subtribe ATS API",
    description="AI-Powered Recruitment Platform API",
    version="1.0.0"
)
```

---

## 12. Deployment Checklist

- [ ] Set environment variables in Cloud Run
- [ ] Configure CORS for production frontend URL
- [ ] Enable Sentry for error tracking
- [ ] Set up structured logging
- [ ] Configure database connection pooling
- [ ] Set GCS bucket permissions
- [ ] Test authentication flows
- [ ] Test file upload with 5MB files
- [ ] Monitor cold start times

---

## 13. Implementation Priority

**Phase 1: Auth & Setup** (Days 1-2)
1. FastAPI project structure
2. Database connection + Alembic
3. Supabase Auth integration
4. JWT validation middleware
5. Auth endpoints (register, login, logout, me)

**Phase 2: Core Entities** (Days 3-5)
1. Company & User models + endpoints
2. Invitation flow
3. Job CRUD endpoints
4. Bootstrap first company

**Phase 3: Applications** (Days 6-10)
1. Public job page endpoint
2. Application submission with file upload
3. GCS integration
4. Resume parsing (basic)
5. Application list/detail endpoints

**Phase 4: Polish** (Days 11-14)
1. Status history tracking
2. Error handling refinement
3. Logging and monitoring
4. Testing (critical paths)
5. Deployment

---

## Related Documents

- **Database Schema**: [`./database.md`](./database.md)
- **Setup Tasks**: [`./NEXT-STEPS.md`](./NEXT-STEPS.md)
- **Architecture Review**: [`./pre-implementation-review.md`](./pre-implementation-review.md)
- **Frontend Requirements**: [`../frontend/PRD.md`](../frontend/PRD.md)

---

**Last Updated**: 2025-09-30  
**Status**: Specification Complete  
**Next**: Create setup guides, then begin implementation

