# Setup Reference Guide

> **Quick reference** for configuring Supabase, GCS, database, and environment. Follow in order during Phase 0.

---

## 1. Supabase Setup {#supabase}

### Create Project
1. Go to [supabase.com](https://supabase.com) → New Project
2. Configure:
   - **Region**: South Asia (Mumbai) - `asia-south1`
   - **Database Password**: Generate strong password (save it)
   - **Pricing**: Free tier
3. Wait 2-3 minutes for provisioning

### Get Credentials
Go to **Settings → API**:
- `SUPABASE_URL`: Project URL
- `SUPABASE_ANON_KEY`: anon/public key
- `SUPABASE_SERVICE_KEY`: service_role key (click "Reveal")
- `SUPABASE_JWT_SECRET`: JWT Settings section

### Configure Auth Settings

**1. Turn OFF Email Confirmations**  
Go to **Authentication → Emails** in sidebar:
- Find "Confirm email" template
- Disable it (we use invitation-only system)

**2. Set Access Token Expiry**  
Go to **Settings → JWT Keys**:
- **Access Token Expiry Time**: Change from `3600` to `604800` seconds (7 days)
- Click **Save**
- Add this value to `.env` as `SUPABASE_ACCESS_TOKEN_EXPIRY=604800`

**Note on Refresh Tokens**: Refresh token expiry configuration requires Supabase Pro plan (can't be set on free tier). Document it in `.env` as `SUPABASE_REFRESH_TOKEN_EXPIRY=2592000` for reference, but it won't be used. Our backend uses a **dual JWT strategy** where we issue our own JWTs with company context after Supabase validates identity. Session duration is controlled by our backend config (`JWT_EXPIRY_DAYS=15`, `REFRESH_TOKEN_EXPIRY_DAYS=30`), not Supabase tokens.

### Get Database URL
Go to **Settings → Database → Connection string → URI**:
```
postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres
```

For SQLAlchemy (async):
```
postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres
```

### Enable RLS Policies (After Running Migrations)

**When**: After `alembic upgrade head` completes successfully

**How**: 
1. Go to Supabase Dashboard → **SQL Editor**
2. Open `database/rls_policies.sql` from project
3. Copy entire file and paste into SQL Editor
4. Click **Run**
5. Verify output shows RLS enabled and policies created

**Why separate from migrations**: RLS policies are security configuration, not schema. Defining them in Supabase ensures they persist across database resets and aren't lost if migrations are regenerated.

---

## 2. Google Cloud Storage {#gcs}

### Create Project
```bash
gcloud projects create subtribe-ats-prod --name="Subtribe ATS"
gcloud config set project subtribe-ats-prod
gcloud services enable storage-api.googleapis.com
```

### Create Bucket
```bash
gsutil mb -p subtribe-ats-prod \
  -c STANDARD \
  -l asia-south1 \
  -b on \
  gs://subtribe-ats-resumes-dev

# Block public access
gsutil iam ch -d allUsers gs://subtribe-ats-resumes-dev
```

### Create Service Account
```bash
# Create
gcloud iam service-accounts create subtribe-ats-storage \
  --display-name="Subtribe ATS Storage"

# Get email
SA_EMAIL=$(gcloud iam service-accounts list \
  --filter="displayName:Subtribe ATS Storage" \
  --format="value(email)")

# Grant permissions
gsutil iam ch serviceAccount:$SA_EMAIL:roles/storage.objectAdmin \
  gs://subtribe-ats-resumes-dev

# Download key
gcloud iam service-accounts keys create ~/subtribe-ats-storage-key.json \
  --iam-account=$SA_EMAIL

chmod 600 ~/subtribe-ats-storage-key.json
```

### File Storage Strategy

**GCS (Resumes Only)**:
- Candidate resumes uploaded to GCS private bucket
- Path: `{company_id}/{job_id}/{application_id}_{timestamp}_{filename}.pdf`
- Access via signed URLs (1-hour expiry)
- Validation: PDF only, <5MB

**External URLs (Logo/Avatar)**:
- `companies.logo_url` - Company provides external URL (no GCS upload for MVP)
- `users.avatar_url` - User provides external URL (no GCS upload for MVP)
- Other links: `linkedin_url`, `github_url`, `portfolio_url`, `website_url`
- Can add GCS upload endpoints in V1.1 if needed

---

## 3. Environment Configuration {#environment}

### Create `.env`
```bash
cp .env.development.example .env
```

### Generate JWT Secret
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Fill in `.env`
```bash
# App
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# Database (from Supabase)
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_ECHO=false

# Supabase (from dashboard)
SUPABASE_URL=https://[PROJECT].supabase.co
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_KEY=eyJhbGc...
SUPABASE_JWT_SECRET=your-jwt-secret
SUPABASE_ACCESS_TOKEN_EXPIRY=604800  # 7 days (set in Settings → JWT Keys)
SUPABASE_REFRESH_TOKEN_EXPIRY=2592000  # 30 days (Pro plan only, not used)

# Backend JWT (generate new, different from Supabase)
JWT_SECRET_KEY=your-generated-secret
JWT_ALGORITHM=HS256
JWT_EXPIRY_DAYS=15  # Our backend access token duration
REFRESH_TOKEN_EXPIRY_DAYS=30  # Our backend refresh token duration

# GCS (from above)
GCS_BUCKET_NAME=subtribe-ats-resumes-dev
GCS_PROJECT_ID=subtribe-ats-prod
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/subtribe-ats-storage-key.json

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]

# Pagination
DEFAULT_PAGE_SIZE=20
MAX_PAGE_SIZE=50

# File Upload
MAX_RESUME_SIZE_MB=5
ALLOWED_RESUME_TYPES=["pdf","docx"]

# Invitation
INVITATION_EXPIRY_HOURS=48
```

### Verify Configuration
```bash
python -c "from app.config import settings; print('✅ Config loaded')"
```

---

## 4. Database Setup {#database}

### Initialize Alembic
```bash
alembic init migrations
```

### Configure `alembic.ini`
Comment out the sqlalchemy.url line (we'll use env.py):
```ini
# sqlalchemy.url = driver://user:pass@localhost/dbname
```

### Configure `migrations/env.py`
Replace with configuration that:
- Imports all models
- Loads DATABASE_URL from settings
- Converts asyncpg to psycopg2 for migrations

**See**: Full example in detailed docs (database-setup.md)

### Create Models
Create in `app/models/`:
- `company.py` - Companies table
- `user.py` - Users table
- `invitation.py` - Invitations table
- `job.py` - Jobs table
- `application.py` - Applications table
- `status_history.py` - Status history table

**Schema reference**: [`database.md`](./database.md)

### Generate Initial Migration
```bash
alembic revision --autogenerate -m "Initial schema - 6 tables"
```

Review the generated file in `migrations/versions/`

### Apply Migration
```bash
alembic upgrade head
```

### Verify Tables
Check Supabase dashboard → Table Editor:
- companies
- users
- invitations
- jobs
- applications
- application_status_history

---

## 5. Bootstrap First Company {#bootstrap}

### Step 1: Create User in Supabase
**Via Supabase Dashboard**:
1. Go to **Authentication → Users**
2. Click **Add user**
3. Email: `admin@yourcompany.com`
4. Auto-generate password (or set manually)
5. **Auto Confirm User**: ✅ Enable
6. Copy the User UUID

### Step 2: Create Company & Link User (SQL)
Connect to Supabase database and run:

```sql
-- 1. Create company
INSERT INTO companies (id, name, slug, is_active, created_at, updated_at) 
VALUES (
  gen_random_uuid(),
  'Test Company',
  'test-company',
  true,
  NOW(),
  NOW()
) RETURNING id;

-- Copy the returned company ID, then:

-- 2. Link user
INSERT INTO users (
  id, company_id, auth_user_id, email, first_name, last_name,
  role, is_active, email_verified, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'PASTE-COMPANY-ID-HERE',
  'PASTE-AUTH-USER-UUID-HERE',
  'admin@yourcompany.com',
  'Admin',
  'User',
  'admin',
  true,
  true,
  NOW(),
  NOW()
);
```

### Step 3: Test Login
```bash
curl -X POST 'https://YOUR-PROJECT.supabase.co/auth/v1/token?grant_type=password' \
  -H "apikey: YOUR-ANON-KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@yourcompany.com",
    "password": "your-password"
  }'
```

Should return access_token and user object.

---

## 6. Storage Service Implementation {#storage-service}

### Create `app/services/storage.py`

```python
from google.cloud import storage
from datetime import datetime, timedelta
import re
import unicodedata

class StorageService:
    def __init__(self):
        self.client = storage.Client(project=settings.GCS_PROJECT_ID)
        self.bucket = self.client.bucket(settings.GCS_BUCKET_NAME)
    
    def sanitize_filename(self, name: str, max_length: int = 50) -> str:
        """Convert name to safe filename."""
        name = unicodedata.normalize('NFKD', name)
        name = name.encode('ascii', 'ignore').decode('ascii')
        name = name.lower().replace(' ', '_')
        name = re.sub(r'[^a-z0-9_]', '', name)
        name = re.sub(r'_+', '_', name).strip('_')
        return name[:max_length]
    
    def generate_path(
        self, company_id: str, job_id: str, 
        application_id: str, full_name: str, extension: str
    ) -> str:
        """Generate GCS path: {company}/{job}/{app}_{ts}_{name}.{ext}"""
        timestamp = int(datetime.utcnow().timestamp())
        sanitized_name = self.sanitize_filename(full_name)
        filename = f"{application_id}_{timestamp}_{sanitized_name}.{extension}"
        return f"{company_id}/{job_id}/{filename}"
    
    async def upload_resume(
        self, file, company_id: str, job_id: str,
        application_id: str, full_name: str, content_type: str
    ) -> str:
        """Upload file to GCS, return gs:// URI."""
        extension = "pdf" if "pdf" in content_type else "docx"
        path = self.generate_path(
            company_id, job_id, application_id, full_name, extension
        )
        
        blob = self.bucket.blob(path)
        blob.upload_from_file(file, content_type=content_type, timeout=60)
        
        return f"gs://{self.bucket.name}/{path}"
    
    def generate_signed_url(self, gcs_uri: str, expiration_minutes: int = 60) -> str:
        """Generate temporary download URL."""
        path = gcs_uri.replace(f"gs://{self.bucket.name}/", "")
        blob = self.bucket.blob(path)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET"
        )

storage_service = StorageService()
```

---

## 7. Exception Handlers {#error-handling}

### Create `app/exceptions.py`

```python
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from google.cloud.exceptions import GoogleCloudError

class AppException(Exception):
    def __init__(self, message: str, code: str, status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code

class AuthenticationError(AppException):
    def __init__(self, message: str = "Authentication required", code: str = "auth_required"):
        super().__init__(message, code, 401)

class PermissionError(AppException):
    def __init__(self, message: str = "Insufficient permissions", code: str = "forbidden"):
        super().__init__(message, code, 403)

class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found", code: str = "not_found"):
        super().__init__(message, code, 404)

class ConflictError(AppException):
    def __init__(self, message: str = "Resource already exists", code: str = "conflict"):
        super().__init__(message, code, 409)

def register_exception_handlers(app: FastAPI):
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {
                "type": exc.__class__.__name__.lower(),
                "code": exc.code,
                "message": exc.message
            }}
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = [{
            "field": ".".join(str(x) for x in err["loc"][1:]),
            "code": err["type"],
            "message": err["msg"]
        } for err in exc.errors()]
        
        return JSONResponse(
            status_code=400,
            content={"error": {
                "type": "validation_error",
                "code": "validation_failed",
                "message": "Request validation failed",
                "errors": errors
            }}
        )
    
    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(request: Request, exc: IntegrityError):
        if "duplicate key" in str(exc).lower():
            return JSONResponse(
                status_code=409,
                content={"error": {
                    "type": "conflict_error",
                    "code": "duplicate_entry",
                    "message": "A record with this value already exists"
                }}
            )
        return JSONResponse(status_code=400, content={"error": {
            "type": "database_error",
            "code": "integrity_constraint",
            "message": "Database constraint violation"
        }})
    
    @app.exception_handler(GoogleCloudError)
    async def gcs_exception_handler(request: Request, exc: GoogleCloudError):
        return JSONResponse(status_code=503, content={"error": {
            "type": "server_error",
            "code": "storage_unavailable",
            "message": "File storage temporarily unavailable"
        }})
```

### Register in `app/main.py`
```python
from app.exceptions import register_exception_handlers

app = FastAPI(title="Subtribe ATS")
register_exception_handlers(app)
```

---

## 8. Database Transaction Pattern

**Use for multi-step operations** (e.g., create application + upload file):

```python
async def create_application_with_resume(
    db: AsyncSession, job: Job, form_data: dict, resume_file: UploadFile
) -> Application:
    async with db.begin():  # Auto-rollback on exception
        # 1. Create application
        application = Application(
            job_id=job.id,
            company_id=job.company_id,
            full_name=form_data["full_name"],
            email=form_data["email"],
            status="applied"
        )
        db.add(application)
        await db.flush()  # Get ID
        
        # 2. Upload resume (if this fails, DB rolls back)
        resume_uri = await storage_service.upload_resume(
            file=resume_file.file,
            company_id=str(job.company_id),
            job_id=str(job.id),
            application_id=str(application.id),
            full_name=form_data["full_name"],
            content_type=resume_file.content_type
        )
        
        application.resume_url = resume_uri
        application.resume_filename = resume_file.filename
    
    return application  # Transaction committed
```

---

## Quick Commands

```bash
# Start server
uvicorn app.main:app --reload

# Create migration
alembic revision --autogenerate -m "description"

# Run migration
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Test config
python -c "from app.config import settings; print('OK')"

# Test GCS upload
python scripts/test_gcs.py
```

---

**Related**:
- **API Specs**: [`api-design.md`](./api-design.md)
- **Database Schema**: [`database.md`](./database.md)
- **Implementation Plan**: [`plan.md`](./plan.md)

