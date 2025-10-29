# AI Coding Standards & Methodology

> **Purpose**: Maintain high-quality, production-grade code with proper testing, verification, and standards compliance.
> **Last Updated**: 2025-10-29

---

## Table of Contents

1. [Core Principles](#core-principles)
2. [Communication Standards](#communication-standards)
3. [Code Quality Standards](#code-quality-standards)
4. [Database Changes](#database-changes)
5. [Testing Methodology](#testing-methodology)
6. [When to Stop vs Continue](#when-to-stop-vs-continue)
7. [Git & Commits](#git--commits)
8. [Documentation](#documentation)
9. [Python-Specific Standards](#python-specific-standards)
10. [Error Handling](#error-handling)
11. [Checklist Before Production](#checklist-before-production)

---

## Core Principles

### ✅ Always Do
1. **Verify before executing** - Check configurations, understand impact
2. **Small, incremental changes** - One thing at a time, test each step
3. **Read before write** - Always read files/docs before modifying
4. **Test with scripts** - Create verification scripts instead of assumptions
5. **Follow the proper way** - Use framework patterns (e.g., Alembic autogenerate, not manual migrations)
6. **Document everything** - Update docs immediately after changes
7. **Check linting** - Run Ruff/Mypy before considering task complete
8. **Ask when unsure** - Clarify ambiguous requirements before coding

### ❌ Never Do
1. **Assume without verification** - Don't guess, test
2. **Rewrite migration files** - Let Alembic autogenerate from models
3. **Skip reading existing code** - Always understand context first
4. **Batch unrelated changes** - Keep changes focused and atomic
5. **Ignore test failures** - Fix immediately, don't proceed
6. **Push without verification** - Always verify locally first
7. **Create files unnecessarily** - Edit existing files when possible
8. **Use placeholders in production** - Complete implementations only

---

## Communication Standards

### Be Concise and Professional

**Principle**: Developers value clarity and brevity. Avoid verbose explanations unless specifically requested.

### ✅ Good Communication Examples

**After fixing a bug:**
```
✅ Fixed pagination schema mismatch in candidates list API.
Changed: Used total_pages instead of pages field.
Tested: API returns correct format.
```

**After completing a task:**
```
✅ Added database indexes for pagination (idx_jobs_company_created, idx_applications_job_applied).
Performance: ~10x faster queries.
Migration: Applied and tested.
```

**After investigation:**
```
Issue confirmed: PaginationMeta duplicated in job.py and application.py.
Fix: Create common.py, import from there.
Impact: Both endpoints affected.
```

### ❌ Bad Communication Examples

**Don't do this (too verbose):**
```
🎉 Great news! I've successfully completed the pagination bug fix that was
affecting the candidates list API endpoint. This was a fascinating issue
where we had two different PaginationMeta schemas defined in separate files,
and one was using the "pages" field while the other was using "total_pages".
After careful investigation and analysis, I determined that we needed to
create a unified schema in a common file. I then proceeded to update all
the imports across the codebase, ensuring that both endpoints now use the
same consistent pagination format. The changes have been tested thoroughly
and everything is working perfectly! 🚀✨
```

**Better version:**
```
✅ Fixed pagination schema duplication bug.
Changes: Created common.py, updated imports in job.py and application.py.
Result: Consistent total_pages field across endpoints.
```

### Communication Guidelines

**For simple tasks:**
- ✅ One-line summary: "✅ Fixed X. Changed Y. Tested Z."
- ❌ Avoid: Long explanations, emojis (unless user uses them), unnecessary details

**For complex tasks:**
- ✅ Bullet points with key changes
- ✅ Brief explanation of impact
- ❌ Avoid: Essay-style writeups, excessive formatting

**When reporting problems:**
- ✅ State problem clearly and concisely
- ✅ Propose solution briefly
- ✅ Ask specific question if needed
- ❌ Avoid: Long-winded explanations of what went wrong

**Status updates:**
```
✅ GOOD:
Migration applied. 3 indexes created. Database verified.

❌ BAD:
🎉 I'm thrilled to report that the migration has been successfully
applied to the database! All three performance indexes have been
created as expected, and I've thoroughly verified that everything
is working perfectly. The database is now optimized for pagination
queries and should see significant performance improvements! 🚀
```

### When to Provide Details

**DO provide detailed explanations when:**
- User explicitly asks for details ("explain why...")
- Investigating complex bugs (show thought process)
- Multiple approaches exist (explain trade-offs)
- Teaching/onboarding (educational context)
- Critical decisions that need approval

**DON'T provide details when:**
- Task is straightforward and completed
- User just wants status update
- Following standard patterns
- Bug was simple fix

### Summary Format Template

**For completed work:**
```
✅ [Task completed]
Changed: [Key changes, 1 line]
Result: [Outcome, 1 line]
```

**For issues found:**
```
⚠️ [Issue description]
Cause: [Root cause, 1 line]
Fix: [Proposed solution, 1 line]
```

**For questions:**
```
Need clarification on [X].
Options: A) [option], B) [option]
Which approach?
```

### No Unnecessary Emojis

- ✅ Use: Basic status indicators (✅ ❌ ⚠️)
- ❌ Avoid: Celebratory emojis (🎉 🚀 ✨) unless user uses them
- ❌ Avoid: Decorative emojis that add no value

---

## Code Quality Standards

### Before Committing Any Code

```bash
# 1. Check imports and syntax (fast)
python -c "from app.module import something; print('✅ Imports OK')"

# 2. Run Ruff linting (code quality)
ruff check app/ --select E,F,W,C90,I,N,UP,YTT,ASYNC,S,BLE,B,A,COM,C4,DTZ,T10,EM,ISC,ICN,G,PIE,T20,PT,Q,RSE,RET,SLF,SIM,TID,ARG,PTH,ERA,PD,PGH,PL,TRY,NPY,RUF

# 3. Run Ruff formatting check
ruff format --check app/

# 4. Run type checking (if using Mypy)
mypy app/ --strict

# 5. Verify application starts
python -c "from app.main import app; print('✅ App loads successfully')"
```

### Code Style Requirements

**Mandatory:**
- ✅ Type hints on all function parameters and return values
- ✅ Docstrings for all public functions/classes
- ✅ Maximum line length: 100 characters
- ✅ Use f-strings for string formatting
- ✅ Import order: stdlib → third-party → local (Ruff enforces)
- ✅ Use `pathlib.Path` instead of `os.path`
- ✅ Async functions must use `async`/`await` properly

**Example:**
```python
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job


async def get_job_by_id(db: AsyncSession, job_id: UUID) -> Job | None:
    """Fetch a job by its ID.

    Args:
        db: Database session
        job_id: UUID of the job to fetch

    Returns:
        Job object if found, None otherwise
    """
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
```

---

## Database Changes

### The Proper Way: Models → Migrations

**✅ ALWAYS Follow This Process:**

1. **Modify the model** (source of truth):
```python
# app/models/job.py
from sqlalchemy import Index

class Job(Base):
    # ... columns ...

    __table_args__ = (
        Index('idx_jobs_company_created', 'company_id', 'created_at'),
    )
```

2. **Let Alembic detect changes**:
```bash
alembic revision --autogenerate -m "add_job_indexes"
```

3. **Review the generated migration** (don't edit, just verify):
```python
# Check it looks correct
cat database/migrations/versions/XXXX_add_job_indexes.py
```

4. **Test the migration cycle**:
```bash
# Create test script first
python scripts/test_migration.py  # Before migration

# Apply
alembic upgrade head

# Verify
python scripts/test_migration.py  # After migration

# Test rollback
alembic downgrade -1

# Verify rollback worked
python scripts/test_migration.py

# Re-apply for production
alembic upgrade head
```

### ❌ NEVER Do This:

```python
# DON'T manually write migrations
def upgrade():
    op.create_index('idx_jobs_company_created', 'jobs', ['company_id', 'created_at'])
```

**Why?** Models and migrations get out of sync, future autogenerate breaks.

### When to Stop Immediately

**🚨 STOP if you see:**
- "Detected removed table" in autogenerate output
- Migration wants to DROP tables unexpectedly
- Alembic can't see your models (check `env.py` imports)
- Test script shows indexes missing after applying migration

**What to do:**
1. Delete the bad migration file
2. Investigate root cause (usually missing model imports in `env.py`)
3. Fix the issue
4. Regenerate migration
5. Test again before proceeding

---

## Testing Methodology

### Always Create Verification Scripts

**Don't assume, test!**

**Example: Testing Database Indexes**
```python
# scripts/test_indexes.py
async def check_indexes():
    """Verify indexes exist."""
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'jobs'
            AND indexname = 'idx_jobs_company_created';
        """))
        indexes = result.fetchall()

        if indexes:
            print("✅ Index exists")
            return True
        else:
            print("❌ Index missing")
            return False
```

### Test-Driven Changes

**Process:**
1. Write test script that checks for desired state
2. Run test (should fail/show current state)
3. Make the change
4. Run test again (should pass)
5. Test rollback if applicable

**Tools:**
- Python scripts for database verification
- `ruff check` for code quality
- `python -c "import..."` for import verification
- Actual API calls with `curl` or Postman

---

## When to Stop vs Continue

### 🛑 STOP Immediately When:

1. **Migration says DROP table** (unless you intended this)
2. **Test script fails** after your change
3. **Linter shows errors** (not warnings, errors)
4. **Imports fail** after changes
5. **You're unsure about the approach** (ask user first)
6. **Breaking changes** detected (ask before proceeding)
7. **Production database** involved (extra caution)

**Action:** Fix the issue, verify, then continue.

### ✅ Continue When:

1. **Test passes** and behavior is correct
2. **Linter shows zero errors** (warnings acceptable if known)
3. **Documentation updated** to reflect changes
4. **User explicitly confirmed** the approach
5. **Change is incremental** and doesn't break existing functionality
6. **Rollback tested** and works (for migrations)

### ⚠️ Ask User When:

1. Multiple valid approaches exist
2. Trade-offs need business decision
3. Breaking changes required
4. Unsure about requirements
5. Need access to external services
6. Major architectural decision

---

## Git & Commits

### Commit Standards

**Format:**
```
<type>: <description>

<body (optional)>

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `refactor:` Code refactoring (no functional change)
- `perf:` Performance improvement
- `docs:` Documentation only
- `style:` Formatting, missing semi-colons, etc.
- `test:` Adding tests
- `chore:` Maintenance (dependencies, build, etc.)

**Examples:**
```bash
git commit -m "$(cat <<'EOF'
fix: Standardize pagination schema across endpoints

- Created unified PaginationMeta in app/schemas/common.py
- Fixed field mismatch (pages vs total_pages)
- Added soft-delete filters to prevent showing deleted records

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### Before Committing

```bash
# 1. Check what's changed
git status
git diff

# 2. Run quality checks
ruff check app/ --select E,F
ruff format --check app/

# 3. Stage specific files (not git add .)
git add app/schemas/common.py
git add app/routers/jobs.py

# 4. Commit with proper message
git commit -m "fix: pagination schema standardization"

# 5. Verify commit
git log -1 --stat
```

### Never Commit:

- ❌ `.env` files (secrets)
- ❌ `__pycache__/` directories
- ❌ Temporary test scripts (unless useful long-term)
- ❌ Generated files (unless needed for deployment)
- ❌ IDE-specific files (.vscode, .idea)
- ❌ Large binary files without LFS

---

## Documentation

### Always Update Immediately

**After any change, update relevant docs:**

1. **Code changes** → API design docs
2. **Database changes** → Database schema docs
3. **New features** → Progress tracking
4. **Bug fixes** → Add to progress/changelog

### Documentation Standards

**API Examples:**
- ✅ Complete examples (not `{...}` placeholders)
- ✅ Realistic data values
- ✅ All required fields shown
- ✅ Include field types and constraints

**Code Comments:**
```python
# ✅ GOOD: Explains WHY, not WHAT
# Index for pagination queries (10x faster than sequential scan)
Index('idx_jobs_company_created', 'company_id', 'created_at')

# ❌ BAD: States the obvious
# Create an index
Index('idx_jobs_company_created', 'company_id', 'created_at')
```

**Docstrings:**
```python
def process_application(app: Application, job: Job) -> dict:
    """Process a candidate application and calculate match score.

    Validates application data, checks for duplicates, and runs
    initial AI screening if enabled for the job.

    Args:
        app: Application object with candidate data
        job: Job object with requirements

    Returns:
        dict with keys: score (int), summary (str), issues (list)

    Raises:
        ValidationError: If application data is invalid
        ConflictError: If candidate already applied to this job
    """
```

---

## Python-Specific Standards

### Type Hints (Mandatory)

```python
# ✅ GOOD
def calculate_total(items: list[dict], tax_rate: float = 0.1) -> float:
    return sum(item["price"] for item in items) * (1 + tax_rate)

# ❌ BAD
def calculate_total(items, tax_rate=0.1):
    return sum(item["price"] for item in items) * (1 + tax_rate)
```

### Async/Await

```python
# ✅ GOOD: Properly async
async def fetch_jobs(db: AsyncSession) -> list[Job]:
    result = await db.execute(select(Job))
    return result.scalars().all()

# ❌ BAD: Mixing sync and async
async def fetch_jobs(db: AsyncSession) -> list[Job]:
    result = db.execute(select(Job))  # Missing await!
    return result.scalars().all()
```

### SQLAlchemy 2.0 Patterns

```python
# ✅ GOOD: Explicit select()
stmt = select(Job).where(Job.company_id == company_id)
result = await db.execute(stmt)
jobs = result.scalars().all()

# ❌ BAD: Old-style query
jobs = db.query(Job).filter_by(company_id=company_id).all()
```

### Error Handling

```python
# ✅ GOOD: Let framework handle it
@router.get("/jobs/{job_id}")
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise NotFoundError(message="Job not found", code="job_not_found")

    return job

# ❌ BAD: Try/catch everywhere
@router.get("/jobs/{job_id}")
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Job).where(Job.id == job_id)
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise NotFoundError(message="Job not found", code="job_not_found")

        return job
    except Exception as e:
        # Framework already handles this!
        return {"error": str(e)}
```

---

## Error Handling

### Custom Exceptions (Framework-Level)

**Create custom exceptions:**
```python
# app/exceptions.py
class NotFoundError(Exception):
    """Resource not found (404)."""
    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
```

**Use in endpoints:**
```python
if not job:
    raise NotFoundError(message="Job not found", code="job_not_found")
```

**Register global handler:**
```python
# app/main.py
@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": {"type": "not_found", "code": exc.code, "message": exc.message}}
    )
```

### When to Use Try/Catch

**✅ Use try/catch for:**
- External service calls (GCS, third-party APIs)
- Optional operations (logging, analytics)
- Specific error recovery logic

**❌ Don't use try/catch for:**
- Validation errors (use Pydantic)
- Database errors (let framework handle)
- Every single operation (trust the framework)

---

## Checklist Before Production

### Pre-Commit Checklist

- [ ] All imports work: `python -c "from app.main import app"`
- [ ] Ruff linting passes: `ruff check app/ --select E,F`
- [ ] Ruff formatting clean: `ruff format --check app/`
- [ ] Type checking passes: `mypy app/` (if using)
- [ ] Manual testing done (Postman/curl)
- [ ] Documentation updated
- [ ] Migration tested (if database changed)
- [ ] No secrets in code (`.env` not committed)
- [ ] Commit message follows convention

### Pre-Deployment Checklist

- [ ] All tests pass: `pytest` (when tests exist)
- [ ] Migrations applied successfully
- [ ] Environment variables configured
- [ ] Database indexes verified
- [ ] API documentation up-to-date
- [ ] No breaking changes (or user informed)
- [ ] Rollback plan ready
- [ ] Monitoring/logging configured

### Pre-Push to Main

- [ ] Feature branch tested completely
- [ ] Code reviewed (by user or automated)
- [ ] CI/CD pipeline passes
- [ ] No merge conflicts
- [ ] Branch up-to-date with main
- [ ] Changelog/progress.md updated

---

## Linting Configuration

### Ruff Configuration (pyproject.toml or ruff.toml)

```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "F",    # pyflakes
    "W",    # pycodestyle warnings
    "C90",  # mccabe (complexity)
    "I",    # isort (import sorting)
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "S",    # bandit (security)
    "B",    # flake8-bugbear
    "A",    # flake8-builtins
    "C4",   # flake8-comprehensions
    "DTZ",  # flake8-datetimez
    "T10",  # flake8-debugger
    "EM",   # flake8-errmsg
    "ISC",  # flake8-implicit-str-concat
    "ICN",  # flake8-import-conventions
    "G",    # flake8-logging-format
    "PIE",  # flake8-pie
    "PT",   # flake8-pytest-style
    "Q",    # flake8-quotes
    "RSE",  # flake8-raise
    "RET",  # flake8-return
    "SIM",  # flake8-simplify
    "ARG",  # flake8-unused-arguments
    "PTH",  # flake8-use-pathlib
    "PL",   # pylint
    "RUF",  # ruff-specific rules
]

ignore = [
    "S101",   # assert-used (OK in tests)
    "PLR0913", # too-many-arguments (sometimes necessary)
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101", "PLR2004"]  # Allow asserts and magic values in tests
```

### Running Checks

```bash
# Quick check (errors only)
ruff check app/ --select E,F

# Full check (all rules)
ruff check app/

# Auto-fix safe issues
ruff check app/ --fix

# Format code
ruff format app/

# Check specific file
ruff check app/routers/jobs.py
```

---

## Common Pitfalls & Solutions

### Pitfall: Alembic Can't See Models

**Problem:**
```bash
alembic revision --autogenerate
# Output: Detected removed table 'jobs'
```

**Solution:**
```python
# database/migrations/env.py
from app.database import Base

# ADD THIS - Import all models so they register with Base.metadata
from app.models import application, company, job, status_history, user  # noqa: F401

target_metadata = Base.metadata
```

### Pitfall: Forgetting Soft-Delete Filters

**Problem:** Showing deleted records to users

**Solution:** Always filter by `deleted_at.is_(None)`:
```python
stmt = select(Job).where(
    Job.company_id == company_id,
    Job.deleted_at.is_(None)  # Add this!
)
```

### Pitfall: Missing Database Indexes

**Problem:** Slow pagination queries

**Solution:** Add composite indexes for common query patterns:
```python
__table_args__ = (
    Index('idx_jobs_company_created', 'company_id', 'created_at'),
)
```

### Pitfall: Inconsistent Schemas

**Problem:** Multiple `PaginationMeta` definitions

**Solution:** Create `app/schemas/common.py` for shared schemas:
```python
# app/schemas/common.py
class PaginationMeta(BaseModel):
    """Shared pagination schema."""
    page: int
    limit: int
    total: int
    total_pages: int
    has_more: bool
```

---

## Quick Reference Commands

```bash
# Development
uvicorn app.main:app --reload              # Start server
ruff check app/ --select E,F               # Quick lint
ruff format app/                           # Format code
python -c "from app.main import app"       # Test imports

# Database
alembic revision --autogenerate -m "desc"  # Create migration
alembic upgrade head                       # Apply migrations
alembic downgrade -1                       # Rollback one
alembic current                            # Show current version

# Testing
pytest                                     # Run tests (when available)
python scripts/test_something.py           # Custom test script

# Git
git status                                 # Check changes
git diff                                   # Review changes
git add <specific-file>                    # Stage specific files
git commit -m "type: description"          # Commit with message
git log --oneline -5                       # Recent commits
```

---

## Summary: The Golden Rules

1. **Be concise** - Quick summaries, no verbose explanations unless asked
2. **Models are source of truth** - Never write migrations manually
3. **Test before production** - Create verification scripts
4. **Stop when something's wrong** - Don't proceed on errors
5. **Read before write** - Understand context first
6. **Lint before commit** - Zero errors required
7. **Document immediately** - Don't defer docs
8. **One change at a time** - Incremental, testable changes
9. **Ask when unsure** - Clarify before implementing
10. **Follow framework patterns** - Use built-in capabilities
11. **Verify, verify, verify** - Test everything

---

**Remember:** Production-grade code takes time. Better to be cautious and correct than fast and broken. When in doubt, STOP and verify.

**Last Updated**: 2025-10-29
**Version**: 1.1 (Added Communication Standards)
**Applies to**: Subtribe ATS Backend (FastAPI + SQLAlchemy + PostgreSQL)
