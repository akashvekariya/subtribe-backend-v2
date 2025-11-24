"""update_position_type_constraint_add_new_types

Revision ID: e71f87cc765a
Revises: 830ccb0cd993
Create Date: 2025-11-01 18:08:50.317402

MANUAL MIGRATION: Alembic cannot auto-detect CHECK constraint changes.
This migration updates the position_type CHECK constraint to support new job types:
- Added: temporary, other, volunteer
- Existing: full_time, part_time, contract, internship

Why manual migration is required:
Alembic autogenerate cannot detect CHECK constraint modifications (open issue since 2018).
We must manually drop and recreate the constraint with the new values.

References:
- Alembic issue #508: https://github.com/sqlalchemy/alembic/issues/508
- Job model: app/models/job.py (constraint updated in __table_args__)
- Validators: app/schemas/job.py (also enforces at application layer)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e71f87cc765a'
down_revision: Union[str, Sequence[str], None] = '830ccb0cd993'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update CHECK constraints to support new position types."""
    # Drop old position_type constraint (too restrictive)
    op.drop_constraint('valid_position_type', 'jobs', type_='check')

    # Create new constraint with additional position types
    op.create_check_constraint(
        'valid_position_type',
        'jobs',
        "position_type IN ('full_time', 'part_time', 'contract', 'temporary', 'other', 'volunteer', 'internship')"
    )


def downgrade() -> None:
    """Restore old position_type constraint (without new types)."""
    # Drop new constraint
    op.drop_constraint('valid_position_type', 'jobs', type_='check')

    # Restore old constraint (only 4 types)
    op.create_check_constraint(
        'valid_position_type',
        'jobs',
        "position_type IN ('full_time', 'part_time', 'contract', 'internship')"
    )
