# Development Guide

Local development setup and common patterns.

---

## Prerequisites

- Python 3.13+
- PostgreSQL 14+ (via Supabase)
- Google Cloud account (GCS)
- Git

---

## Initial Setup

### 1. Clone Repository
```bash
git clone <repo-url>
cd subtribe-backend
```

### 2. Create Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Copy example and edit:
```bash
cp .env.development.example .env
```

Required variables:
- `DATABASE_URL` - Supabase PostgreSQL connection string
- `SUPABASE_*` - Auth credentials from Supabase dashboard
- `JWT_SECRET_KEY` - Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `GCS_*` - Google Cloud Storage credentials
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to service account JSON key

See `.env.development.example` for full list.

### 5. Run Migrations
```bash
alembic upgrade head
```

### 6. Bootstrap First Company
```sql
-- Connect to Supabase SQL Editor and run:
INSERT INTO companies (name, slug, invite_code, is_active)
VALUES ('Test Company', 'testco', 'TESTCO-abc123', true);
```

### 7. Start Server
```bash
uvicorn app.main:app --reload
```

**Server**: http://localhost:8000  
**Docs**: http://localhost:8000/docs

---

## Project Structure

```
subtribe-backend/
├── app/
│   ├── main.py              # FastAPI app entry
│   ├── config.py            # Settings (environment variables)
│   ├── database.py          # Database connection
│   ├── dependencies.py      # Dependency injection (auth, DB)
│   ├── exceptions.py        # Global error handlers
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── company.py
│   │   ├── user.py
│   │   ├── job.py
│   │   ├── application.py
│   │   └── status_history.py
│   ├── schemas/             # Pydantic request/response schemas
│   │   ├── auth.py
│   │   ├── company.py
│   │   ├── job.py
│   │   └── application.py
│   ├── routers/             # API endpoints
│   │   ├── auth.py
│   │   ├── companies.py
│   │   ├── jobs.py
│   │   └── applications.py
│   └── services/            # Business logic
│       └── storage.py       # GCS operations
├── database/
│   ├── migrations/          # Alembic migrations
│   └── rls_policies.sql     # Row-Level Security policies
├── tests/                   # Unit tests
├── .env                     # Local environment (not in git)
├── requirements.txt         # Python dependencies
├── alembic.ini              # Alembic configuration
└── Dockerfile               # Container definition
```

---

## Development Workflow

### Daily Routine
```bash
# Activate environment
source .venv/bin/activate

# Pull latest changes
git pull

# Run migrations (if any)
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

### Making Changes

1. **Create feature branch**
   ```bash
   git checkout -b feature/add-export
   ```

2. **Write code**
   - Add/update models in `app/models/`
   - Add/update schemas in `app/schemas/`
   - Add/update endpoints in `app/routers/`
   - Add/update services in `app/services/`

3. **Test locally**
   - Use Swagger UI at http://localhost:8000/docs
   - Or use curl/Postman

4. **Run linters**
   ```bash
   ruff check .
   ruff format .
   ```

5. **Commit and push**
   ```bash
   git add .
   git commit -m "feat: add export functionality"
   git push origin feature/add-export
   ```

6. **Create pull request**
   - CI will run linting and tests
   - Merge to `main` triggers deployment

---

## Common Patterns

### Database Queries

**List with multi-tenant filtering:**
```python
from sqlalchemy import select
from app.models.job import Job

# Always filter by company_id
stmt = select(Job).where(
    Job.company_id == current_user["company_id"],
    Job.status == "active"
)
result = await db.execute(stmt)
jobs = result.scalars().all()
```

**Get single record:**
```python
stmt = select(Job).where(
    Job.id == job_id,
    Job.company_id == current_user["company_id"]  # CRITICAL
)
result = await db.execute(stmt)
job = result.scalar_one_or_none()

if not job:
    raise NotFoundError(message="Job not found", code="job_not_found")
```

### Transactions

**Multi-step operations:**
```python
async with db.begin():
    # Create application
    application = Application(...)
    db.add(application)
    await db.flush()  # Get application.id
    
    # Upload to GCS
    resume_url = await storage_service.upload_resume(...)
    
    # Update application
    application.resume_url = resume_url
    
# Auto-commit on success, rollback on exception
```

### Authentication

**Protected endpoint:**
```python
from app.dependencies import get_current_user

@router.get("/jobs")
async def list_jobs(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # current_user contains: user_id, company_id, role, email
    ...
```

**Role-based access:**
```python
from app.dependencies import require_role

@router.post("/jobs")
async def create_job(
    data: JobCreate,
    current_user: dict = Depends(require_role("admin", "recruiter")),
    db: AsyncSession = Depends(get_db)
):
    ...
```

### Error Handling

**Custom exceptions:**
```python
from app.exceptions import NotFoundError, ConflictError, AppException

# Not found
raise NotFoundError(message="Job not found", code="job_not_found")

# Conflict (duplicate)
raise ConflictError(message="Already applied", code="duplicate_application")

# Custom error
raise AppException(
    message="File too large",
    code="file_too_large",
    status_code=400
)
```

**Framework handles:**
- Converting to JSON response
- Setting correct status code
- Logging error
- Returning consistent format

---

## Database Migrations

### Create Migration
```bash
# After modifying models
alembic revision --autogenerate -m "Add new field to jobs"
```

### Review Migration
Check generated file in `database/migrations/versions/`

### Apply Migration
```bash
alembic upgrade head
```

### Rollback
```bash
alembic downgrade -1  # Rollback one migration
alembic downgrade <revision_id>  # Rollback to specific revision
```

### Migration Tips
- Always review auto-generated migrations
- Add data migrations separately if needed
- Test rollback before committing
- Never edit applied migrations

---

## Testing

### Manual Testing
Use Swagger UI at http://localhost:8000/docs

### Unit Tests
```bash
# Run all tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/test_schemas.py -v

# Run with coverage
pytest --cov=app tests/unit/
```

### Integration Tests
Disabled in V1 (manual testing via Swagger UI)

---

## Code Quality

### Linting
```bash
# Check for errors
ruff check .

# Auto-fix issues
ruff check --fix .
```

### Formatting
```bash
# Check formatting
ruff format --check .

# Auto-format
ruff format .
```

### Type Checking
```bash
mypy app --ignore-missing-imports
```

---

## Environment Variables

### Required
- `DATABASE_URL` - PostgreSQL connection string
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_ANON_KEY` - Supabase anon key
- `SUPABASE_SERVICE_KEY` - Supabase service role key
- `SUPABASE_JWT_SECRET` - Supabase JWT secret
- `JWT_SECRET_KEY` - Backend JWT secret
- `GCS_BUCKET_NAME` - GCS bucket name
- `GCS_PROJECT_ID` - GCP project ID
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to service account JSON

### Optional
- `JWT_ALGORITHM` - Default: HS256
- `JWT_EXPIRY_DAYS` - Default: 15
- `CORS_ORIGINS` - Default: ["*"]
- `ENVIRONMENT` - Default: development
- `DEBUG` - Default: true

See `.env.development.example` for full list with descriptions.

---

## Debugging

### Enable Debug Logging
```python
# In app/main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Database Query Logging
```python
# In app/database.py
engine = create_async_engine(
    settings.database_url,
    echo=True  # Logs all SQL queries
)
```

### VS Code Debug Configuration
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload"],
      "jinja": true,
      "justMyCode": false
    }
  ]
}
```

---

## Troubleshooting

### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>
```

### Database Connection Errors
1. Check DATABASE_URL in .env
2. Verify Supabase project is active
3. Check IP allowlist in Supabase settings
4. Test connection: `psql <DATABASE_URL>`

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Migration Errors
```bash
# Check current revision
alembic current

# Check migration history
alembic history

# Stamp database (if out of sync)
alembic stamp head
```

---

**Related**:
- [API Reference](API-Reference)
- [Database Schema](Database-Schema)
- [Deployment](Deployment)

