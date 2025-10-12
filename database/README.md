# Database Management

All database-related scripts, migrations, and SQL files.

## Structure

```
database/
├── migrations/          # Alembic migration files
│   ├── versions/       # Auto-generated migration scripts
│   └── env.py          # Alembic environment config
├── rls_policies.sql    # Row-Level Security policies (run once in Supabase)
├── seeds/              # Seed data scripts (future)
└── README.md           # This file
```

## Usage

### Running Migrations

```bash
# Generate new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

### Setting Up RLS Policies

After running migrations, apply RLS policies once:

1. Go to Supabase Dashboard → **SQL Editor**
2. Copy content from `database/rls_policies.sql`
3. Paste and click **Run**

This enables Row-Level Security without enforcing restrictions (service role has full access via permissive policies).

### Seed Data (Future)

Place seed scripts in `seeds/` directory:
- `seeds/01_bootstrap_company.sql` - Create first company
- `seeds/02_test_data.sql` - Test jobs and applications

## Notes

- **Models**: Located in `app/models/` (standard FastAPI convention)
- **Database Engine**: Defined in `app/database.py` (FastAPI dependency)
- **Migrations**: Managed here via Alembic
- **RLS Policies**: Applied via Supabase SQL Editor (not in migrations)

