"""add invite_type for org_creator invites

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-17 15:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add invite_type column and make company_id nullable for org_creator invites."""
    # 1. Add invite_type column with default 'team_member'
    op.add_column(
        "invites",
        sa.Column(
            "invite_type",
            sa.String(50),
            server_default=sa.text("'team_member'"),
            nullable=False,
        ),
    )

    # 2. Make company_id nullable (for org_creator invites that don't have a company)
    op.alter_column(
        "invites",
        "company_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    # 3. Add check constraint for valid invite_type values
    op.create_check_constraint(
        "valid_invite_type",
        "invites",
        "invite_type IN ('team_member', 'org_creator')",
    )

    # 4. Add check constraint to ensure team_member invites have company_id
    op.create_check_constraint(
        "valid_company_for_invite_type",
        "invites",
        "(invite_type = 'org_creator') OR (invite_type = 'team_member' AND company_id IS NOT NULL)",
    )

    # 5. Backfill: Set all existing invites to 'team_member' (they all have company_id)
    op.execute(
        """
        UPDATE invites
        SET invite_type = 'team_member'
        WHERE invite_type IS NULL OR invite_type = ''
        """
    )


def downgrade() -> None:
    """Remove invite_type column and make company_id non-nullable."""
    # 1. Drop the new check constraints
    op.drop_constraint("valid_company_for_invite_type", "invites", type_="check")
    op.drop_constraint("valid_invite_type", "invites", type_="check")

    # 2. Delete any org_creator invites (they don't have company_id)
    op.execute(
        """
        DELETE FROM invites WHERE invite_type = 'org_creator'
        """
    )

    # 3. Make company_id non-nullable again
    op.alter_column(
        "invites",
        "company_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )

    # 4. Drop invite_type column
    op.drop_column("invites", "invite_type")
