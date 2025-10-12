# Backend PRD - AI-Powered ATS

> **What**: Multi-tenant SaaS ATS backend with resume uploads, job management, and candidate tracking. AI evaluation deferred to V1.1.

---

## Product Overview

**Target Users**: Small-medium recruiting companies (2-50 employees)  
**Core Value**: Simple, fast ATS without enterprise complexity  
**MVP Timeline**: 10-14 days development

---

## Core Features (V1)

### 1. Authentication
- Email/password + Google OAuth via Supabase Auth
- Invitation-only signup (no public registration)
- JWT with custom claims (`company_id`, `role`)
- 14-day sessions, 30-day refresh tokens

### 2. User Management
- **Roles**: Admin, Recruiter, Interviewer
- Invite team members via email
- Company profile management

### 3. Job Management
- Create/edit/archive job postings
- Rich job details (salary, location, remote policy, skills)
- Custom screening questions (text, select, number)
- Public job pages with unique slugs

### 4. Application Management
- Public application submission
- Resume upload (PDF/DOCX, max 5MB)
- View candidates by job
- Manual status tracking (Applied → Screening → Interview → Offer → Hired/Rejected)
- Status history audit trail

### 5. File Storage
- GCS for resume storage
- Private buckets with signed URLs (1-hour expiry)
- Organized by company/job

---

## Technical Architecture

**Pattern**: Monolithic REST API with Repository Pattern  
**Multi-tenancy**: Row-level isolation via `company_id`  
**API Style**: RESTful, async/await throughout

### Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | FastAPI (Python 3.10+) |
| Database | PostgreSQL 14+ (Supabase) |
| ORM | SQLAlchemy 2.0 (async) |
| Auth | Supabase Auth |
| Storage | Google Cloud Storage |
| Hosting | Google Cloud Run |

### Database Schema

**6 Core Tables**:
- `companies` - Tenant/organization
- `users` - Recruiters, admins
- `invitations` - Pending user invites
- `jobs` - Job postings
- `applications` - Candidate applications
- `application_status_history` - Status change audit

**Details**: See [`database.md`](./database.md)

---

## API Endpoints

**20+ endpoints** covering:
- Auth: `/auth/register`, `/auth/login`, `/auth/google`, `/auth/me`
- Invitations: `/invitations` (create, validate)
- Jobs: `/jobs` (CRUD)
- Applications: `/jobs/{id}/applications`, `/applications/{id}`
- Public: `/public/jobs/{slug}`, `/public/jobs/{slug}/apply`

**Details**: See [`api-design.md`](./api-design.md)

---

## Key Decisions

### What's In (V1)
✅ Email/password + Google OAuth  
✅ Invitation-only system  
✅ Manual candidate status tracking  
✅ Resume uploads to GCS  
✅ Basic resume text extraction  
✅ Multi-tenant isolation (application-level)

### Deferred (V1.1+)
⏳ AI candidate evaluation (BAML framework)  
⏳ Email notifications (log only for V1)  
⏳ Rate limiting  
⏳ Real-time notifications  
⏳ Advanced search/filters  
⏳ Activity logs

---

## Non-Functional Requirements

**Performance**:
- API response < 200ms (p95)
- File upload < 5s for 5MB files
- Database connection pooling (20 connections)

**Security**:
- JWT validation on all protected routes
- Private GCS buckets (no public access)
- Input validation (Pydantic)
- Multi-tenant data isolation

**Scalability**:
- Designed for 100+ companies
- Async operations throughout
- Cloud Run auto-scaling

**Cost** (100k applications):
- Supabase: Free tier
- GCS: ~$7/month
- Cloud Run: ~$20/month
- **Total**: ~$27/month

---

## Success Criteria

**MVP Launch**:
- [ ] 3 pilot companies onboarded
- [ ] 50+ job postings created
- [ ] 500+ applications submitted
- [ ] < 1% error rate
- [ ] Positive user feedback

**V1.1 (AI)**:
- [ ] AI evaluation accuracy > 80%
- [ ] Evaluation time < 30 seconds/application
- [ ] 50% reduction in time-to-shortlist

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Supabase auth complexity | High | Simplified with backend enrichment (dual JWT) |
| File upload failures | Medium | Synchronous uploads, transaction rollback |
| Multi-tenant data leaks | High | Application-level filtering, RLS in V2 |
| Cost overruns | Low | Monitor usage, optimize storage |

---

**Related**:
- Implementation: [`plan.md`](./plan.md)
- Progress: [`progress.md`](./progress.md)

