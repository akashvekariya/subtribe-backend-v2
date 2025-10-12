# Architecture

System design, technology choices, and architectural patterns.

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | FastAPI | Latest |
| Language | Python | 3.13+ |
| Database | PostgreSQL | 14+ |
| ORM | SQLAlchemy | 2.0 (async) |
| Auth | Supabase Auth | - |
| Storage | Google Cloud Storage | - |
| Deployment | Google Cloud Run | - |
| CI/CD | GitHub Actions | - |

---

## System Architecture

### Pattern
**Monolithic REST API** with async/await throughout

- Single codebase, simplified deployment
- FastAPI with Pydantic validation
- Repository pattern for data access
- Service layer for business logic

### Multi-Tenancy
**Row-level isolation** via `company_id` filtering

- Single database, multiple tenants
- Application-level filtering on all queries
- Each user belongs to one company
- Queries always include `WHERE company_id = ?`

See [Multi-Tenancy](Multi-Tenancy) for implementation details.

---

## Key Design Decisions

### Authentication Strategy
**Dual JWT System**

1. **Supabase JWT** - Identity validation only
2. **Backend JWT** - Contains `company_id` and `role` claims

**Why?** Supabase JWT doesn't contain company context. Backend creates a new JWT after validating Supabase token, adding multi-tenancy claims.

**Expiry**:
- Access token: 15 days
- Refresh token: 30 days

### File Storage Strategy
**No Deduplication**

- Each resume stored separately even if duplicate
- Multi-tenant isolation > cost savings
- Path: `{company_id}/{job_id}/{app_id}_{timestamp}_{name}.pdf`

**Cost**: ~$6/month for 100k resumes (acceptable)

### Database Strategy
**Async Runtime, Sync Migrations**

- **Runtime**: asyncpg for async operations
- **Migrations**: psycopg2 for Alembic (sync)

**Why?** Migrations are one-time operations, not performance-critical. Keeps Alembic simple.

### Error Handling
**Framework-Level Exception Handlers**

- Global FastAPI exception handlers
- Consistent JSON error responses
- No try/catch in every endpoint
- Automatic logging and monitoring

See [API Reference](API-Reference#error-responses) for error formats.

---

## Data Flow

### Application Submission Flow
```
1. Candidate submits form + resume (public endpoint)
2. Validate job is active
3. Validate file (PDF only, <5MB)
4. Check for duplicates (same email)
5. Begin database transaction
   - Create application record
   - Upload resume to GCS
   - Update application with resume URL
   - Create initial status history entry
6. Commit transaction (or rollback on failure)
7. Return application ID
```

### Authentication Flow
```
1. User logs in with email/password
2. Validate credentials via Supabase Auth
3. Get Supabase JWT (identity validation)
4. Backend validates Supabase JWT
5. Backend creates new JWT with company_id and role
6. Return backend JWT to client
7. Client uses backend JWT for all API calls
```

---

## Performance Targets

| Metric | Target | Actual |
|--------|--------|--------|
| API Response (p95) | < 200ms | ✅ ~150ms |
| File Upload (5MB) | < 5s | ✅ ~2-3s |
| Database Connections | 20 pool | ✅ Configured |
| Cloud Run Cold Start | < 3s | ✅ ~1-2s |

---

## Security

### Authentication & Authorization
- JWT validation on all protected routes
- Role-based access control (admin, recruiter)
- Company-scoped data access

### Data Protection
- Private GCS buckets (no public access)
- Signed URLs with 1-hour expiry
- Multi-tenant data isolation
- Input validation via Pydantic

### Infrastructure
- HTTPS only (enforced by Cloud Run)
- Secrets stored in GitHub Secrets
- Service accounts with least privilege
- Regular dependency updates

---

## Scalability

### Current Capacity
- **Companies**: 100+ concurrent
- **Applications**: Millions (PostgreSQL limit)
- **Storage**: Unlimited (GCS)
- **Requests**: Auto-scaling (Cloud Run)

### Bottlenecks & Mitigations
| Bottleneck | Mitigation |
|-----------|-----------|
| Database connections | Connection pooling (20 connections) |
| File uploads | Async processing, streaming uploads |
| API throughput | Cloud Run auto-scaling (0-100 instances) |
| Storage costs | GCS lifecycle policies (archive after 1 year) |

---

## Cost Estimates

**For 100k applications/month**:
- Supabase: Free tier (or $25/month Pro)
- GCS: ~$7/month (300GB storage)
- Cloud Run: ~$20/month (light usage)
- **Total**: ~$27-52/month

---

## Technology Choices Rationale

### Why FastAPI?
- Modern async/await support
- Automatic OpenAPI documentation
- Excellent performance
- Strong typing with Pydantic

### Why Supabase?
- Managed PostgreSQL
- Built-in auth system
- Mumbai region (low latency)
- Generous free tier

### Why Google Cloud Storage?
- High reliability (99.95% SLA)
- Signed URLs for security
- Mumbai region availability
- Pay-per-use pricing

### Why Cloud Run?
- Serverless (no server management)
- Auto-scaling (0 to 100 instances)
- Pay only for requests
- Easy CI/CD integration

---

## Future Considerations (V1.1+)

**Not implemented in V1**:
- Row-Level Security (RLS) policies - currently app-level only
- Real-time notifications - WebSockets or Server-Sent Events
- Advanced caching - Redis for hot data
- AI candidate evaluation - LLM integration
- Email notifications - currently console logs only

See [Project Status](Project-Status) for roadmap.

---

**Related**:
- [Database Schema](Database-Schema)
- [Multi-Tenancy](Multi-Tenancy)
- [API Reference](API-Reference)

