"""add cloud_task_name to scheduled_emails

Revision ID: fa4e07a7f26d
Revises: bfe419ede9fd
Create Date: 2025-11-26 14:16:57.113895

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa4e07a7f26d'
down_revision: Union[str, Sequence[str], None] = 'bfe419ede9fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add cloud_task_name column to scheduled_emails table."""
    op.add_column(
        'scheduled_emails',
        sa.Column('cloud_task_name', sa.String(500), nullable=True)
    )


def downgrade() -> None:
    """Remove cloud_task_name column from scheduled_emails table."""
    op.drop_column('scheduled_emails', 'cloud_task_name')
