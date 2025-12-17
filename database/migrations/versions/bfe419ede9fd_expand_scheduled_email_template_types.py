"""expand_scheduled_email_template_types

Revision ID: bfe419ede9fd
Revises: b4feaa74fed8
Create Date: 2025-11-26 12:46:44.611844

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bfe419ede9fd'
down_revision: Union[str, Sequence[str], None] = 'b4feaa74fed8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Expand scheduled_emails template_type to allow more values."""
    # Drop the old constraint
    op.drop_constraint(
        'valid_scheduled_email_template_type',
        'scheduled_emails',
        type_='check'
    )
    # Add new constraint with expanded values
    op.create_check_constraint(
        'valid_scheduled_email_template_type',
        'scheduled_emails',
        "template_type IN ('interview_invite', 'rejection', 'manual', 'bulk', 'custom')"
    )


def downgrade() -> None:
    """Revert to original constraint."""
    op.drop_constraint(
        'valid_scheduled_email_template_type',
        'scheduled_emails',
        type_='check'
    )
    op.create_check_constraint(
        'valid_scheduled_email_template_type',
        'scheduled_emails',
        "template_type IN ('interview_invite', 'rejection')"
    )
