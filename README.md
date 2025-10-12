# Subtribe ATS Backend

> **Status**: ✅ Production Deployed & Tested (2025-10-12)

Multi-tenant SaaS Applicant Tracking System for small-medium recruiting companies.

## Tech Stack

- **Framework**: FastAPI (Python 3.13)
- **Database**: PostgreSQL (Supabase)
- **Storage**: Google Cloud Storage
- **Auth**: Supabase Auth
- **Deployment**: Google Cloud Run

## Quick Start

### Prerequisites
- Python 3.13+
- PostgreSQL (Supabase account)
- Google Cloud account (for GCS and Cloud Run)

### Local Development

```bash
# 1. Clone and setup
git clone <repo-url>
cd subtribe-backend

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.development.example .env
# Edit .env with your credentials

# 5. Run migrations
alembic upgrade head

# 6. Start server
uvicorn app.main:app --reload
```

Server runs at `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## Architecture

### Multi-Tenancy
- Row-level isolation via `company_id` filter in all queries
- Single database, multiple companies
- Each user belongs to one company

### Key Features
- **Authentication**: Email/password via Supabase Auth
- **Jobs**: Create, update, list, and close job postings
- **Applications**: Public apply endpoint with resume upload
- **Resumes**: Stored in GCS with signed URLs for access
- **Status Tracking**: Track application status changes with history

### Project Structure
```
app/
├── main.py                 # FastAPI app & routes
├── config.py               # Environment configuration
├── database.py             # Database connection
├── dependencies.py         # Auth & DB dependencies
├── exceptions.py           # Error handlers
├── models/                 # SQLAlchemy models
├── schemas/                # Pydantic schemas
├── routers/                # API endpoints
└── services/               # Business logic (storage, etc.)
```

## API Endpoints

### Public
- `POST /jobs/{slug}/apply` - Submit job application

### Auth
- `POST /auth/register` - Register with company code
- `POST /auth/login` - Login with email/password
- `GET /auth/me` - Get current user

### Jobs (Protected)
- `POST /jobs` - Create job
- `GET /jobs` - List company jobs
- `GET /jobs/{id}` - Get job details
- `PATCH /jobs/{id}` - Update job
- `PATCH /jobs/{id}/close` - Close job

### Applications (Protected)
- `GET /applications/{id}` - Get application
- `PATCH /applications/{id}` - Update status
- `GET /applications/{id}/history` - Status history
- `GET /applications/{id}/resume/view` - View resume
- `GET /applications/{id}/resume/download` - Download resume

### Companies (Protected)
- `GET /companies/me` - Get company profile
- `PATCH /companies/me` - Update company

## Development

### Code Quality
```bash
# Linting
ruff check .

# Formatting
ruff format .

# Type checking
mypy app --ignore-missing-imports
```

### Database Migrations
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Testing
```bash
# Run unit tests
pytest tests/unit/ -v

# Run specific test
pytest tests/unit/test_schemas.py -v
```

## Deployment

Automated CI/CD via GitHub Actions:
- **Lint & Test**: Runs on all PRs and pushes
- **Deploy**: Auto-deploys to Cloud Run on push to `main`
- **Versioning**: Semantic versioning based on conventional commits

See [`.github/README.md`](.github/README.md) for detailed setup instructions.

## Environment Variables

Required environment variables (see `.env.development.example`):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://...

# Supabase Auth
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...
SUPABASE_JWT_SECRET=...

# Backend JWT
JWT_SECRET_KEY=...
JWT_ALGORITHM=HS256
JWT_EXPIRY_DAYS=15

# Google Cloud Storage
GCS_BUCKET_NAME=...
GCS_PROJECT_ID=...
GOOGLE_APPLICATION_CREDENTIALS=path/to/key.json

# App Config
CORS_ORIGINS=["http://localhost:3000"]
ENVIRONMENT=development
```

## Documentation

**📚 [View Full Documentation on GitHub Wiki →](../../wiki)**

### Quick Links
- [Architecture](../../wiki/Architecture) - System design and tech stack
- [API Reference](../../wiki/API-Reference) - Complete endpoint documentation
- [Database Schema](../../wiki/Database-Schema) - Tables and relationships
- [Development Guide](../../wiki/Development) - Local setup and patterns
- [Deployment Guide](../../wiki/Deployment) - CI/CD and Cloud Run
- [Project Status](../../wiki/Project-Status) - Current phase and roadmap

### Additional Resources
- **[CI/CD Setup](.github/README.md)** - GitHub Actions configuration guide
- **[Legacy Docs](vibe-plan/)** - Original planning documents (archived)

## License

Proprietary - All rights reserved

