# Database Schema Design

> **TLDR**: PostgreSQL 14+ schema for multi-tenant ATS. 6 core tables: companies, users, invitations, jobs, applications, application_status_history. Strategy: Relational + JSONB for flexibility. Multi-tenancy: Single DB with row-level `company_id` isolation + optional RLS. ORM: SQLAlchemy async. Migrations: Alembic. **Related**: [`./api-design.md`](./api-design.md) for API endpoints, [`./NEXT-STEPS.md`](./NEXT-STEPS.md) for setup.

---

## 1. Overview

**Database**: PostgreSQL 14+ via Supabase  
**Strategy**: Hybrid relational + JSONB for flexibility  
**Multi-tenancy**: Single database with `company_id` scoping  
**ORM**: SQLAlchemy with async support (asyncpg driver)

---

## 2. Multi-Tenancy Architecture

### Approach
- **Single Database**: All tenants share one database
- **Row-Level Isolation**: Every tenant-scoped table includes `company_id`
- **Security**: Row-Level Security (RLS) policies in PostgreSQL to prevent cross-tenant data leaks
- **Scalability**: Start with 2-3 test tenants, architect for 100+ tenants

### Benefits
- Simpler infrastructure and backups
- Cost-effective for early stage
- Easy to query across tenants for analytics (if needed)
- Single schema migration process

### Future Considerations
- Monitor database size and query performance
- Consider sharding or database-per-tenant if scaling beyond 1000+ tenants

---

## 3. Core Tables (MVP Revised)

**Note**: Invitations table removed for MVP - users created manually by admin.

### 3.1. `companies`

The tenant/organization entity.

```sql
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,  -- For subdomain: {slug}.yourdomain.com
    invite_code VARCHAR(50) UNIQUE NOT NULL,  -- For user registration (e.g., ACME-x7k9p2)
    domain VARCHAR(255),  -- Company email domain for auto-verification
    logo_url TEXT,
    website_url TEXT,
    tagline TEXT,  -- Short description shown to candidates
    about TEXT,  -- Longer description shown on job pages
    
    -- Settings (as JSONB for flexibility)
    settings JSONB DEFAULT '{}'::jsonb,
    
    -- Subscription/plan info (for future)
    plan VARCHAR(50) DEFAULT 'free',  -- free, starter, pro, enterprise
    is_active BOOLEAN DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT slug_format CHECK (slug ~ '^[a-z0-9-]+$')
);

CREATE INDEX idx_companies_slug ON companies(slug);
CREATE INDEX idx_companies_invite_code ON companies(invite_code);
CREATE INDEX idx_companies_is_active ON companies(is_active);
```

**Settings JSONB**: Flexible company settings (branding, features, notifications)

---

### 3.2. `users`

Recruiters and admins who use the platform.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    
    -- Auth (managed by Supabase Auth, but we store reference)
    auth_user_id UUID UNIQUE,  -- Supabase auth.users.id
    email VARCHAR(255) UNIQUE NOT NULL,
    
    -- Profile
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    avatar_url TEXT,
    phone VARCHAR(50),
    
    -- Role & Permissions (MVP: Everyone is admin)
    role VARCHAR(50) NOT NULL DEFAULT 'admin',
    permissions JSONB DEFAULT '[]'::jsonb,  -- Future use
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    last_login_at TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_role CHECK (role IN ('admin', 'recruiter', 'interviewer'))
);

CREATE INDEX idx_users_company_id ON users(company_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_auth_user_id ON users(auth_user_id);
CREATE INDEX idx_users_role ON users(role);
```

**Role Definitions** (MVP Simplified):
- **MVP**: Everyone is `admin` with full access
- **Future**: Add `recruiter`, `interviewer` roles with granular permissions
- **Permissions JSONB**: Reserved for V2 RBAC implementation

---

### 3.3. `invitations` ❌ REMOVED FOR MVP

**Decision**: Admin creates users manually via SQL/Supabase dashboard.
- **Reason**: Simplifies MVP, faster to ship
- **Future**: Implement proper invitation flow in V1.1

---

### 3.4. `jobs`

Job postings created by recruiters.

Inspired by Wellfound schema but adapted for V1 needs.

```sql
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id),
    
    -- Basic Info
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,  -- Markdown supported
    
    -- Job Details (from Wellfound schema)
    position_type VARCHAR(50),  -- full_time, part_time, contract, internship
    primary_role VARCHAR(100),  -- e.g., "Backend Engineer", "Product Manager"
    
    experience_level VARCHAR(50),  -- entry, mid, senior, lead, principal
    department VARCHAR(100),
    
    -- Location
    location_type VARCHAR(50),  -- remote, hybrid, onsite
    location_city VARCHAR(100),
    location_state VARCHAR(100),
    location_country VARCHAR(100) DEFAULT 'United States',
    
    -- Remote work details
    remote_policy VARCHAR(50),  -- remote_only, hybrid, onsite_only
    accepted_timezones TEXT[],  -- Array of timezone strings
    
    -- Visa & Relocation
    visa_sponsorship BOOLEAN DEFAULT false,
    relocation_assistance BOOLEAN DEFAULT false,
    
    -- Salary (optional for V1)
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency VARCHAR(10) DEFAULT 'USD',
    equity_offered BOOLEAN DEFAULT false,
    
    -- Skills & Requirements (flexible JSONB)
    required_skills JSONB DEFAULT '[]'::jsonb,  -- ["Python", "FastAPI"]
    preferred_skills JSONB DEFAULT '[]'::jsonb,
    
    -- Custom Screening Questions (JSONB for flexibility)
    screening_questions JSONB DEFAULT '[]'::jsonb,
    
    -- Status (MVP: active | closed only)
    status VARCHAR(50) DEFAULT 'active',  -- active, closed
    
    -- Public URL slug
    slug VARCHAR(255) UNIQUE NOT NULL,  -- For /apply/{slug}
    
    -- Metadata
    views_count INTEGER DEFAULT 0,
    applications_count INTEGER DEFAULT 0,  -- Computed/cached periodically
    
    -- Timestamps
    published_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT valid_job_status CHECK (status IN ('active', 'closed')),
    CONSTRAINT valid_location_type CHECK (location_type IN ('remote', 'hybrid', 'onsite')),
    CONSTRAINT valid_position_type CHECK (position_type IN ('full_time', 'part_time', 'contract', 'internship'))
);

CREATE INDEX idx_jobs_company_id ON jobs(company_id);
CREATE INDEX idx_jobs_created_by ON jobs(created_by);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_slug ON jobs(slug);
CREATE INDEX idx_jobs_published_at ON jobs(published_at);
```

**Screening Questions JSONB**: Array of question objects with `{id, question, type, required, order, options?}`  
**Required Skills JSONB**: Simple string array (e.g., `["Python", "FastAPI", "PostgreSQL"]`)

---

### 3.5. `applications`

Candidate applications to jobs.

```sql
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    
    -- Candidate Info (from application form)
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    linkedin_url TEXT,
    github_url TEXT,
    portfolio_url TEXT,
    
    -- Salary Info (MVP: Added for recruiter workflow)
    current_ctc INTEGER,  -- Current salary in base currency
    expected_ctc INTEGER,  -- Expected salary
    notice_period_days INTEGER,  -- Notice period in days
    
    -- Resume
    resume_url TEXT NOT NULL,  -- GCS path: gs://bucket/company_id/job_id/resume.pdf
    resume_filename VARCHAR(255),
    resume_parsed_text TEXT,  -- Extracted text for AI processing
    
    -- Custom Screening Answers (JSONB matching job's screening_questions)
    screening_answers JSONB DEFAULT '{}'::jsonb,
    
    -- Pipeline Status
    status VARCHAR(50) DEFAULT 'applied',
    
    -- AI Evaluation (DEFER FOR NOW - TBD)
    -- We'll design this in ai-evaluation.md
    
    -- Application Metadata (optional, low-cost)
    source VARCHAR(100),  -- e.g., "direct", "linkedin", "referral"
    referrer_id UUID REFERENCES users(id),  -- If referred by someone
    
    -- Timestamps
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT valid_application_status CHECK (
        status IN ('applied', 'screening', 'interviewing', 'offer', 'hired', 'rejected')
    )
);

CREATE INDEX idx_applications_job_id ON applications(job_id);
CREATE INDEX idx_applications_company_id ON applications(company_id);
CREATE INDEX idx_applications_email ON applications(email);
CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_applications_applied_at ON applications(applied_at DESC);
```

**Screening Answers JSONB**: Key-value pairs matching job's screening questions (e.g., `{"q1": "120000", "q2": "..."}`)

**Application Fields Draft** (To be finalized during implementation):
- Basic: first_name, last_name, email, phone, linkedin_url, github_url, portfolio_url
- Salary: current_ctc, expected_ctc, notice_period_days
- Resume: PDF only, <5MB
- **TODO**: Review with user before implementing - may add more fields

---

### 3.6. `application_status_history`

Track status changes for audit trail and analytics.

```sql
CREATE TABLE application_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    
    from_status VARCHAR(50),
    to_status VARCHAR(50) NOT NULL,
    
    changed_by UUID REFERENCES users(id),
    notes TEXT,  -- Optional notes from recruiter
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_status_history_application_id ON application_status_history(application_id);
CREATE INDEX idx_status_history_created_at ON application_status_history(created_at);
```

---

## 4. AI Evaluation Tables (DEFERRED)

**Note**: To be designed in `ai-evaluation.md`. Placeholder for now.

Potential approaches:
- Option A: JSONB column in `applications` table
- Option B: Separate `evaluations` table with versioning
- Option C: Hybrid approach

This requires deep dive into:
- Evaluation schema (score, breakdown, matching skills, gaps)
- Versioning strategy (re-evaluation support)
- Queryability needs (filtering by score, skills match, etc.)

**Action**: Circle back after rest.

---

## 5. Supporting Tables

### 5.1. `activity_logs` (Optional for V1)

Audit trail for important actions.

```sql
CREATE TABLE activity_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id),
    user_id UUID REFERENCES users(id),
    
    action VARCHAR(100) NOT NULL,  -- e.g., "job.created", "application.status_changed"
    resource_type VARCHAR(50),  -- e.g., "job", "application"
    resource_id UUID,
    
    metadata JSONB DEFAULT '{}'::jsonb,
    ip_address INET,
    user_agent TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_activity_logs_company_id ON activity_logs(company_id);
CREATE INDEX idx_activity_logs_user_id ON activity_logs(user_id);
CREATE INDEX idx_activity_logs_action ON activity_logs(action);
CREATE INDEX idx_activity_logs_created_at ON activity_logs(created_at DESC);
```

---

## 6. Database Conventions

### Naming Conventions
- Tables: Plural, lowercase with underscores (`applications`, `status_history`)
- Columns: Lowercase with underscores (`created_at`, `company_id`)
- Primary Keys: `id` (UUID)
- Foreign Keys: `{table}_id` (e.g., `company_id`, `user_id`)
- Timestamps: Always include `created_at`, add `updated_at` for mutable entities

### Data Types
- IDs: `UUID` (better for distributed systems, no enumeration attacks)
- Timestamps: `TIMESTAMPTZ` (timezone-aware)
- Money: `INTEGER` (store cents, not dollars) or `NUMERIC(10,2)`
- Text: `VARCHAR(n)` for bounded, `TEXT` for unbounded
- Arrays: Use PostgreSQL native arrays (`TEXT[]`)
- Semi-structured: `JSONB` (indexed, queryable)

### Indexes
- Index all foreign keys
- Index columns used in WHERE, ORDER BY, JOIN frequently
- Compound indexes for common query patterns
- Use `EXPLAIN ANALYZE` to optimize queries

### Constraints
- Use `CHECK` constraints for enum-like fields
- Use `NOT NULL` where appropriate
- Use `UNIQUE` for natural keys (email, slug)
- Use `ON DELETE CASCADE` carefully (document cascade behavior)

---

## 7. Row-Level Security (RLS)

Enable PostgreSQL RLS to enforce multi-tenancy isolation at the database level.

**Example RLS Policy for `jobs` table**:
```sql
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON jobs
    USING (company_id = current_setting('app.current_company_id')::uuid);
```

**Implementation**:
- Set `app.current_company_id` session variable on each request
- Use SQLAlchemy events to automatically set this before queries
- Provides defense-in-depth against data leaks

---

## 8. Migrations

- **Tool**: Alembic (SQLAlchemy's migration tool)
- **Strategy**: 
  - Auto-generate migrations from SQLAlchemy models
  - Review and edit before applying
  - Test migrations on staging before production
  - Include both `upgrade()` and `downgrade()` functions
  - Never delete migrations from version control

---

## 9. Performance Considerations

### Indexing Strategy
- Start with indexes on foreign keys and common filters
- Monitor slow queries using Supabase dashboard
- Add indexes based on actual usage patterns

### Query Optimization
- Use `select_related`/`joinedload` for foreign keys to avoid N+1 queries
- Use `prefetch_related`/`selectinload` for collections
- Paginate large result sets (20-50 items per page)
- Use database-level sorting when possible

### Caching
- **Don't** cache `applications_count` on `jobs` table (as per user request)
- Use Redis for session data and rate limiting
- Cache computed AI evaluations (expensive to recompute)

### Scaling
- Connection pooling via SQLAlchemy (pool size: 20-40 for Cloud Run)
- Read replicas for analytics queries (future)
- Partitioning large tables by date if needed (future)

---

## 10. Data Integrity & Cleanup

### Soft Deletes vs Hard Deletes
- **Soft Delete**: Users, Jobs, Applications (set `deleted_at` timestamp)
  - Allows recovery, audit trails, referential integrity
  - Filter with `WHERE deleted_at IS NULL` in queries
- **Hard Delete**: Activity logs after 90 days, expired invitations
  - Use background jobs for cleanup

### Backup & Recovery
- Supabase provides automated daily backups
- Test restore process quarterly
- Export critical data to GCS for redundancy

---

## 11. Key Decisions

✅ **AI Evaluation Storage**: Deferred to V1.1 (design complete in [`./ai-evaluation.md`](./ai-evaluation.md))  
✅ **Application Metadata**: Skip for V1 (privacy-focused)  
✅ **Soft Deletes**: Use status field instead (e.g., `status = 'archived'`)  
✅ **Activity Logs**: Defer to V2  
✅ **Search**: Use Postgres FTS when needed (not V1 priority)

---

## 12. Implementation

**Next Steps**:
1. ✅ Schema design complete
2. ⏳ Set up Supabase connection (see [`./NEXT-STEPS.md`](./NEXT-STEPS.md))
3. ⏳ Create SQLAlchemy models
4. ⏳ Write Alembic initial migration
5. ⏳ Create seed data script
6. ⏳ Optional: Set up RLS policies

**Reference**: [`./api-design.md`](./api-design.md) for API implementation  
**Status**: Ready for implementation
