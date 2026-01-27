"""add_evaluation_fields_to_applications

Revision ID: 0f8276c14590
Revises: g5h6i7j8k9l0
Create Date: 2026-01-04 20:23:20.846997

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0f8276c14590'
down_revision: Union[str, Sequence[str], None] = 'g5h6i7j8k9l0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add AI evaluation fields to applications table."""
    # Add evaluation_json column (full evaluation result)
    op.add_column(
        'applications',
        sa.Column('evaluation_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )

    # Add evaluation_score column (0-10 scale)
    op.add_column(
        'applications',
        sa.Column('evaluation_score', sa.Float(), nullable=True)
    )

    # Add evaluation_tier column (strong_match, good_match, etc.)
    op.add_column(
        'applications',
        sa.Column('evaluation_tier', sa.String(length=50), nullable=True)
    )

    # Add evaluated_at timestamp
    op.add_column(
        'applications',
        sa.Column('evaluated_at', sa.TIMESTAMP(timezone=True), nullable=True)
    )

    # Add index for sorting by evaluation score within a job
    op.create_index(
        'idx_applications_job_eval_score',
        'applications',
        ['job_id', 'evaluation_score'],
        unique=False
    )


def downgrade() -> None:
    """Remove AI evaluation fields from applications table."""
    op.drop_index('idx_applications_job_eval_score', table_name='applications')
    op.drop_column('applications', 'evaluated_at')
    op.drop_column('applications', 'evaluation_tier')
    op.drop_column('applications', 'evaluation_score')
    op.drop_column('applications', 'evaluation_json')
