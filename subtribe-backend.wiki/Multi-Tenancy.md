# Multi-Tenancy

Row-level isolation strategy for secure data separation.

---

## Overview

**Strategy**: Single database with application-level filtering  
**Isolation Key**: `company_id`  
**Enforcement**: Mandatory in all tenant-scoped queries

---

## Architecture

### Single Database Approach

All companies (tenants) share:
- Same PostgreSQL database
- Same tables
- Same application instance

**Benefits**:
- Simpler infrastructure
- Cost-effective
- Easy backups
- Single schema migrations
- Cross-tenant analytics possible

**Trade-offs**:
- Requires careful query filtering
- One database outage affects all tenants
- Scaling limits (1000+ tenants may need sharding)

---

## Implementation

### Tenant-Scoped Tables

Tables with `company_id` column:
- `users`
- `jobs`
- `applications`

Tables without `company_id` (global):
- `companies` (tenant definition)
- `application_status_history` (filtered via application)

### Query Pattern

**❌ WRONG** (missing company_id filter):
```python
# Security vulnerability - returns all companies' jobs!
stmt = select(Job).where(Job.status == "active")
```

**✅ CORRECT** (includes company_id):
```python
# Safe - only returns current company's jobs
stmt = select(Job).where(
    Job.company_id == current_user["company_id"],
    Job.status == "active"
)
```

### Enforcement

**Application Level**: Every query MUST include `company_id` filter

**Code Review Checklist**:
- [ ] Does query have `company_id` filter?
- [ ] Is filter coming from JWT (not request body)?
- [ ] Is relationship join filtered by `company_id`?

---

## JWT Claims

### Token Structure

```json
{
  "user_id": "uuid",
  "company_id": "uuid",
  "role": "admin",
  "email": "user@company.com",
  "exp": 1234567890
}
```

**Source**: Backend JWT (not Supabase JWT)

**Why?** Supabase JWT doesn't contain `company_id`. Backend creates enriched JWT after validating Supabase token.

### Usage in Endpoints

```python
from app.dependencies import get_current_user

@router.get("/jobs")
async def list_jobs(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # current_user["company_id"] is guaranteed to exist
    stmt = select(Job).where(Job.company_id == current_user["company_id"])
    ...
```

---

## Security Measures

### 1. Mandatory Filtering

**Rule**: Never query tenant-scoped tables without `company_id` filter

**Examples**:

```python
# Jobs
Job.company_id == current_user["company_id"]

# Applications
Application.company_id == current_user["company_id"]

# Users
User.company_id == current_user["company_id"]
```

### 2. Foreign Key Checks

When creating records, ensure foreign key belongs to same company:

```python
# ❌ WRONG - no validation
application = Application(job_id=job_id, ...)

# ✅ CORRECT - validate job belongs to company
job = await db.get(Job, job_id)
if not job or job.company_id != current_user["company_id"]:
    raise NotFoundError(message="Job not found", code="job_not_found")

application = Application(
    job_id=job_id,
    company_id=current_user["company_id"],  # Explicit company_id
    ...
)
```

### 3. JWT Validation

**Never trust client-provided company_id**:

```python
# ❌ WRONG - client could lie
data = {"company_id": "malicious-company-id", ...}
job = Job(**data)

# ✅ CORRECT - use JWT claim
job = Job(
    company_id=current_user["company_id"],  # From JWT
    ...
)
```

---

## Row-Level Security (RLS)

### Current Status

**V1**: RLS policies disabled (application-level filtering only)

**Why?** Simpler implementation, faster MVP delivery

### Future (V1.1)

**Enable RLS for defense-in-depth**:

```sql
-- Example RLS policy (not yet implemented)
CREATE POLICY jobs_isolation ON jobs
  USING (company_id = current_setting('app.company_id')::uuid);
```

**Benefits**:
- Database-level security
- Protection against application bugs
- Compliance requirements

**Trade-offs**:
- More complex queries
- Performance overhead
- Harder to debug

---

## Testing Multi-Tenancy

### Test Checklist

**Isolation Tests**:
1. Create two companies (A and B)
2. Create resources in each (jobs, applications)
3. User from Company A should NOT see Company B's data
4. Verify across all endpoints

**Example Test**:
```
1. Company A: Create job "Backend Engineer"
2. Company B: Create job "Frontend Engineer"  
3. Login as Company A user
4. GET /jobs → Should only return "Backend Engineer"
5. GET /jobs/{company_b_job_id} → Should return 404
```

### Manual Testing

**Steps**:
1. Bootstrap two companies with different invite codes
2. Register users for each company
3. Login as Company A user
4. Attempt to access Company B resources
5. Verify 404 errors (not 403 - should appear as if resource doesn't exist)

---

## Common Pitfalls

### 1. Forgetting company_id Filter
```python
# Bug: Returns all companies' applications
stmt = select(Application).where(Application.status == "applied")

# Fix: Add company_id filter
stmt = select(Application).where(
    Application.company_id == current_user["company_id"],
    Application.status == "applied"
)
```

### 2. Using Request Body for company_id
```python
# Bug: Client can specify any company_id
@router.post("/jobs")
async def create_job(data: JobCreate, ...):
    job = Job(**data.dict())  # data.company_id could be malicious!

# Fix: Use JWT company_id
job = Job(
    **data.dict(exclude={"company_id"}),
    company_id=current_user["company_id"]
)
```

### 3. Joining Without Filtering
```python
# Bug: Could leak data through join
stmt = select(Application).join(Job).where(Job.status == "active")

# Fix: Filter both tables
stmt = select(Application).join(Job).where(
    Application.company_id == current_user["company_id"],
    Job.company_id == current_user["company_id"],
    Job.status == "active"
)
```

---

## Performance Considerations

### Indexes

**Critical indexes for multi-tenancy**:
```sql
CREATE INDEX idx_users_company_id ON users(company_id);
CREATE INDEX idx_jobs_company_id ON jobs(company_id);
CREATE INDEX idx_applications_company_id ON applications(company_id);
```

**Composite indexes for common filters**:
```sql
CREATE INDEX idx_jobs_company_status ON jobs(company_id, status);
CREATE INDEX idx_applications_company_status ON applications(company_id, status);
```

### Query Performance

**Good**: Indexes are used effectively
```python
# Uses idx_jobs_company_status
stmt = select(Job).where(
    Job.company_id == company_id,
    Job.status == "active"
)
```

**Bad**: Full table scan
```python
# No index on (status, company_id) order
stmt = select(Job).where(
    Job.status == "active",
    Job.company_id == company_id
)
```

---

## Scaling Considerations

### Current Capacity
- **Companies**: 1000+
- **Users per company**: 100+
- **Jobs per company**: 10,000+
- **Applications per job**: 100,000+

### Scaling Strategies

**When to shard** (future):
- Database size > 1TB
- Query latency > 200ms consistently
- 10,000+ companies

**Sharding options**:
1. **Database per tenant**: Each company gets own database
2. **Schema per tenant**: Shared database, separate schemas
3. **Horizontal sharding**: Distribute companies across databases

---

## Compliance

### Data Isolation

**Guarantees**:
- Each company's data is isolated
- Users can only access their company's data
- No cross-tenant queries possible

**Audit Trail**:
- All status changes logged with user_id
- Company context preserved in application records
- Ready for compliance audits

### GDPR Considerations

**Right to be forgotten**:
- Delete all user data by company_id
- Cascade deletes configured in foreign keys
- Application data preserved (anonymized)

**Data export**:
- Company can export all their data
- Filter by company_id across all tables
- JSON or CSV format

---

## Monitoring

### Metrics to Track

1. **Data leakage attempts**:
   - 404 errors for resources in different company_id
   - Failed authorization attempts

2. **Query performance**:
   - Queries missing company_id filter (slow query log)
   - Index usage statistics

3. **Data growth**:
   - Rows per company
   - Storage per company
   - Query patterns per company

---

**Related**:
- [Architecture](Architecture)
- [Database Schema](Database-Schema)
- [API Reference](API-Reference)

