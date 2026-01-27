"""add resume_file_hash to applications

Revision ID: j8k9l0m1n2o3
Revises: i7j8k9l0m1n2
Create Date: 2026-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j8k9l0m1n2o3'
down_revision: Union[str, Sequence[str], None] = 'i7j8k9l0m1n2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add resume_file_hash column to applications table."""
    op.add_column(
        'applications',
        sa.Column('resume_file_hash', sa.String(64), nullable=True)
    )
    # Index for duplicate detection queries
    op.create_index(
        'idx_applications_resume_hash',
        'applications',
        ['resume_file_hash']
    )


def downgrade() -> None:
    """Remove resume_file_hash column from applications table."""
    op.drop_index('idx_applications_resume_hash', table_name='applications')
    op.drop_column('applications', 'resume_file_hash')
