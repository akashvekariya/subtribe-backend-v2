"""add_email_template_enhancements

Revision ID: f3846590de32
Revises: 6698861bf4ae
Create Date: 2025-11-25 17:26:41.684693

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f3846590de32'
down_revision: Union[str, Sequence[str], None] = '6698861bf4ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop old constraints
    op.drop_constraint('valid_template_type', 'email_templates', type_='check')
    op.drop_constraint('uq_company_template_type', 'email_templates', type_='unique')

    # Add new columns
    op.add_column('email_templates', sa.Column('name', sa.String(length=100), nullable=True))
    op.add_column('email_templates', sa.Column('category', sa.String(length=50), server_default='custom', nullable=False))
    op.add_column('email_templates', sa.Column('wildcards', postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column('email_templates', sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False))

    # Populate name from template_type for existing records
    op.execute("UPDATE email_templates SET name = template_type WHERE name IS NULL")

    # Make name not nullable
    op.alter_column('email_templates', 'name', nullable=False)

    # Add new unique constraint
    op.create_unique_constraint('uq_company_template_name', 'email_templates', ['company_id', 'name'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop new constraint
    op.drop_constraint('uq_company_template_name', 'email_templates', type_='unique')

    # Drop new columns
    op.drop_column('email_templates', 'is_default')
    op.drop_column('email_templates', 'wildcards')
    op.drop_column('email_templates', 'category')
    op.drop_column('email_templates', 'name')

    # Restore old constraints
    op.create_unique_constraint('uq_company_template_type', 'email_templates', ['company_id', 'template_type'])
    op.create_check_constraint('valid_template_type', 'email_templates', "template_type IN ('interview_invite', 'rejection')")
