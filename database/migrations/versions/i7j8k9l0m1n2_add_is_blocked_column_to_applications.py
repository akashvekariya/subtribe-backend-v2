"""add is_dealbreaker and is_flagged columns to applications

Revision ID: i7j8k9l0m1n2
Revises: h6i7j8k9l0m1
Create Date: 2026-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i7j8k9l0m1n2'
down_revision: Union[str, Sequence[str], None] = 'h6i7j8k9l0m1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_dealbreaker and is_flagged columns to applications table."""
    op.add_column(
        'applications',
        sa.Column('is_dealbreaker', sa.Boolean(), nullable=True)
    )
    op.add_column(
        'applications',
        sa.Column('is_flagged', sa.Boolean(), nullable=True)
    )

    # Migrate existing data: extract boolean flags from tier suffixes
    # Set is_dealbreaker = true where tier ends with '_blocked'
    op.execute("""
        UPDATE applications
        SET is_dealbreaker = true
        WHERE evaluation_tier LIKE '%_blocked'
    """)

    # Set is_flagged = true where tier ends with '_flagged'
    op.execute("""
        UPDATE applications
        SET is_flagged = true
        WHERE evaluation_tier LIKE '%_flagged'
    """)

    # Remove _blocked suffix from tier
    op.execute("""
        UPDATE applications
        SET evaluation_tier = REPLACE(evaluation_tier, '_blocked', '')
        WHERE evaluation_tier LIKE '%_blocked'
    """)

    # Remove _flagged suffix from tier
    op.execute("""
        UPDATE applications
        SET evaluation_tier = REPLACE(evaluation_tier, '_flagged', '')
        WHERE evaluation_tier LIKE '%_flagged'
    """)


def downgrade() -> None:
    """Remove is_dealbreaker and is_flagged columns from applications table."""
    op.drop_column('applications', 'is_flagged')
    op.drop_column('applications', 'is_dealbreaker')
