# Backend Documentation

> **Streamlined documentation** for building the Subtribe ATS backend. Read docs in order: PRD → Plan → Progress.

---

## 📖 Documentation Structure

### Main Docs (Read in Order)

1. **[PRD.md](./PRD.md)** - Product Requirements
   - What we're building
   - Core features, tech stack, architecture
   - Success criteria and constraints

2. **[plan.md](./plan.md)** - Implementation Plan
   - How to build it (10 phases)
   - Step-by-step tasks with references
   - Phase 0-10: Setup → Auth → Jobs → Applications → Deploy

3. **[progress.md](./progress.md)** - Development Progress
   - Current status (what's done, what's next)
   - Phase checklist
   - Blockers and notes

### Reference Docs (Consult During Development)

- **[api-design.md](./api-design.md)** - API Specifications
  - 20+ endpoints with request/response schemas
  - Authentication, pagination, error formats
  - Detailed endpoint behaviors

- **[database.md](./database.md)** - Database Schema
  - 6 core tables (companies, users, jobs, applications, etc.)
  - Relationships, indexes, constraints
  - Multi-tenancy strategy

- **[setup-reference.md](./setup-reference.md)** - Setup Guide
  - Supabase configuration
  - GCS bucket setup
  - Database initialization
  - Environment variables
  - Bootstrap first company
  - Code patterns (storage, errors, transactions)

- **[error-handling.md](./error-handling.md)** - Error Handling Architecture
  - Global exception handlers
  - Transaction patterns
  - Validation strategies
  - Logging and monitoring

### Deferred (V1.1)

- **[ai-evaluation.md](./ai-evaluation.md)** - AI candidate evaluation
  - BAML integration
  - Evaluation storage
  - Prompt engineering
  - (Not needed for V1)

### Archived

Old detailed documentation moved to `_archive/`: (Deleted by user as not needed anymore)
- Original setup guides (supabase, gcs, database, etc.)
- NEXT-STEPS.md
- overview.md
- pre-implementation-review.md
- REFACTORING-SUMMARY.md

---

## 🚀 Quick Start

### First Time Setup
```bash
# 1. Read PRD
cat PRD.md

# 2. Read implementation plan
cat plan.md

# 3. Follow Phase 0 in plan.md
# - Create Supabase project
# - Create GCS bucket
# - Configure .env
# Reference: setup-reference.md for commands

# 4. Continue with remaining phases
# Update progress.md as you complete tasks
```

### Returning to Development
```bash
# 1. Check progress
cat progress.md

# 2. See current phase tasks
cat plan.md | grep "Phase X"  # Replace X with current phase

# 3. Continue development
# Update progress.md checkboxes as you go
```

---

## 📁 File Organization

```
backend/
├── PRD.md                    # Product requirements
├── plan.md                   # Implementation roadmap
├── progress.md              # Current status
├── api-design.md            # API specifications
├── database.md              # Database schema
├── setup-reference.md       # Setup guide
├── error-handling.md        # Error patterns
└── ai-evaluation.md         # V1.1 feature (deferred)
```

---

## 🎯 Development Workflow

### Daily Routine
1. **Morning**: Check `progress.md` for current status
2. **Plan**: Read current phase tasks in `plan.md`
3. **Develop**: Build features, test with Postman
4. **Reference**: Check `api-design.md`, `database.md`, `setup-reference.md` as needed
5. **Evening**: Update `progress.md` checkboxes, commit changes

### When Stuck
1. Check `setup-reference.md` for configuration help
2. Check `error-handling.md` for common patterns
3. Check `api-design.md` for endpoint specs
4. Check `database.md` for schema details
5. Google error messages
6. Ask AI assistant

---

## 🔑 Key Decisions (Documented)

**Architecture**:
- Monolithic FastAPI (not microservices)
- Multi-tenant via `company_id` filtering
- Repository pattern for data access

**Auth**:
- Supabase Auth + custom JWT enrichment (dual JWT)
- 14-day access, 30-day refresh tokens
- Invitation-only signup

**Storage**:
- GCS private buckets with signed URLs
- No deduplication (multi-tenant isolation)
- Filename: `{app_id}_{timestamp}_{name}.{ext}`

**Error Handling**:
- Framework-level via FastAPI exception handlers
- Database transactions for multi-step operations
- Consistent JSON error responses

---

## 📊 Status

**Phase**: 0 - Environment Setup  
**Status**: Documentation complete, ready to start implementation  
**Next**: Create Supabase project

---

**Last Updated**: 2025-10-01

