# Database Schema

PostgreSQL schema for multi-tenant ATS backend.

---

## Overview

**Database**: PostgreSQL 14+ (Supabase)  
**ORM**: SQLAlchemy 2.0 (async)  
**Driver**: asyncpg  
**Migrations**: Alembic

---

## Tables

### companies
The tenant/organization entity.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `name` | VARCHAR(255) | Company name |
| `slug` | VARCHAR(100) | URL-friendly identifier (unique) |
| `invite_code` | VARCHAR(50) | Signup code for team members (e.g., `ACME-x7k9p2`) |
| `logo_url` | TEXT | Company logo URL |
| `website_url` | TEXT | Company website |
| `tagline` | TEXT | Short description for job pages |
| `about` | TEXT | Longer description for job pages |
| `is_active` | BOOLEAN | Company status |
| `created_at` | TIMESTAMPTZ | Record creation time |
| `updated_at` | TIMESTAMPTZ | Last update time |

**Indexes**: slug, invite_code, is_active

---

### users
Recruiters and admins.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `company_id` | UUID | Foreign key to companies |
| `auth_user_id` | UUID | Supabase auth user ID (unique) |
| `email` | VARCHAR(255) | User email (unique) |
| `first_name` | VARCHAR(100) | First name |
| `last_name` | VARCHAR(100) | Last name |
| `avatar_url` | TEXT | Profile picture URL |
| `role` | VARCHAR(50) | User role (admin, recruiter, interviewer) |
| `is_active` | BOOLEAN | Account status |
| `created_at` | TIMESTAMPTZ | Record creation time |
| `updated_at` | TIMESTAMPTZ | Last update time |

**Indexes**: company_id, email, auth_user_id, role

**Note**: MVP treats all users as admins.

---

### jobs
Job postings.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `company_id` | UUID | Foreign key to companies |
| `created_by` | UUID | Foreign key to users (job creator) |
| `title` | VARCHAR(255) | Job title |
| `slug` | VARCHAR(300) | URL slug (unique, format: `{title}-{uuid}`) |
| `description` | TEXT | Full job description (markdown) |
| `position_type` | VARCHAR(50) | full_time, part_time, contract, internship |
| `location_type` | VARCHAR(50) | remote, hybrid, onsite |
| `city` | VARCHAR(100) | City (if not remote) |
| `country` | VARCHAR(100) | Country |
| `min_salary` | INTEGER | Minimum salary (annual, currency agnostic) |
| `max_salary` | INTEGER | Maximum salary |
| `currency` | VARCHAR(10) | Currency code (USD, EUR, INR, etc.) |
| `skills_required` | JSONB | Array of required skills |
| `skills_nice_to_have` | JSONB | Array of nice-to-have skills |
| `min_experience_years` | INTEGER | Minimum years of experience |
| `max_experience_years` | INTEGER | Maximum years of experience |
| `screening_questions` | JSONB | Custom questions for applicants |
| `status` | VARCHAR(50) | draft, active, closed |
| `published_at` | TIMESTAMPTZ | When job was made active |
| `closed_at` | TIMESTAMPTZ | When job was closed |
| `views_count` | INTEGER | Public page views |
| `applications_count` | INTEGER | Number of applications |
| `created_at` | TIMESTAMPTZ | Record creation time |
| `updated_at` | TIMESTAMPTZ | Last update time |

**Indexes**: company_id, slug, status, created_by, published_at

**Slug Format**: `{sanitized-title}-{full-uuid}` ensures global uniqueness

---

### applications
Candidate applications.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `company_id` | UUID | Foreign key to companies |
| `job_id` | UUID | Foreign key to jobs |
| `first_name` | VARCHAR(100) | Candidate first name |
| `last_name` | VARCHAR(100) | Candidate last name |
| `email` | VARCHAR(255) | Candidate email |
| `phone` | VARCHAR(50) | Phone number (optional) |
| `linkedin_url` | TEXT | LinkedIn profile (optional) |
| `github_url` | TEXT | GitHub profile (optional) |
| `portfolio_url` | TEXT | Portfolio URL (optional) |
| `resume_url` | TEXT | GCS path (gs://bucket/path) |
| `resume_filename` | VARCHAR(255) | Original filename |
| `current_ctc` | INTEGER | Current compensation |
| `expected_ctc` | INTEGER | Expected compensation |
| `notice_period_days` | INTEGER | Notice period in days |
| `screening_answers` | JSONB | Answers to screening questions |
| `status` | VARCHAR(50) | applied, screening, interviewing, offer, hired, rejected |
| `applied_at` | TIMESTAMPTZ | Application submission time |
| `created_at` | TIMESTAMPTZ | Record creation time |
| `updated_at` | TIMESTAMPTZ | Last update time |

**Indexes**: company_id, job_id, email, status, applied_at

**Unique Constraint**: (job_id, email) - one application per candidate per job

---

### application_status_history
Status change audit trail.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `application_id` | UUID | Foreign key to applications |
| `from_status` | VARCHAR(50) | Previous status (NULL for initial) |
| `to_status` | VARCHAR(50) | New status |
| `changed_by` | UUID | Foreign key to users (NULL for system) |
| `notes` | TEXT | Change notes/reason |
| `created_at` | TIMESTAMPTZ | When change occurred |

**Indexes**: application_id, created_at

**Purpose**: Audit log for collaboration and compliance

---

## Relationships

```
companies (1) ─────< users (N)
companies (1) ─────< jobs (N)
companies (1) ─────< applications (N)
users (1) ─────────< jobs (N)  [created_by]
jobs (1) ───────────< applications (N)
applications (1) ───< application_status_history (N)
users (1) ───────────< application_status_history (N)  [changed_by]
```

---

## Multi-Tenancy Strategy

### Row-Level Isolation
Every tenant-scoped table includes `company_id`:
- `users`
- `jobs`
- `applications`

### Query Pattern
All queries must filter by `company_id`:
```python
# Example (not actual code)
jobs = query.where(Job.company_id == current_user.company_id)
```

### Security
- Application-level filtering (mandatory)
- RLS policies disabled for V1 (planned for V1.1)
- Service role bypasses RLS for admin operations

See [Multi-Tenancy](Multi-Tenancy) for implementation details.

---

## JSONB Fields

### jobs.screening_questions
```json
[
  {
    "id": "q1",
    "type": "text",
    "question": "Why do you want this role?",
    "required": true
  },
  {
    "id": "q2",
    "type": "select",
    "question": "Years of Python experience?",
    "options": ["0-2", "2-5", "5+"],
    "required": true
  }
]
```

### jobs.skills_required / skills_nice_to_have
```json
["Python", "FastAPI", "PostgreSQL", "Docker"]
```

### applications.screening_answers
```json
{
  "q1": "I'm passionate about building scalable systems...",
  "q2": "5+"
}
```

---

## Database Migrations

**Tool**: Alembic  
**Location**: `database/migrations/versions/`

### Migration Commands
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

**Note**: Migrations use psycopg2 (sync), runtime uses asyncpg (async).

---

## Indexes

### Performance-Critical Indexes
- `companies(slug)` - Public job page lookups
- `jobs(slug)` - Public job page lookups
- `applications(job_id, status)` - Candidate filtering
- `application_status_history(application_id, created_at)` - Timeline queries

### Multi-Tenant Indexes
- `users(company_id)`
- `jobs(company_id)`
- `applications(company_id)`

All tenant-scoped queries benefit from these indexes.

---

## Data Retention

**Current Policy**: Indefinite retention

**Future Considerations**:
- Archive old jobs (>1 year closed)
- Archive rejected applications (>6 months)
- GDPR compliance (right to be forgotten)

---

**Related**:
- [Architecture](Architecture)
- [Multi-Tenancy](Multi-Tenancy)
- [API Reference](API-Reference)

