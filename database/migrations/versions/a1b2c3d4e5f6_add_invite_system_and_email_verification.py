"""add invite system and email verification

Revision ID: a1b2c3d4e5f6
Revises: fa4e07a7f26d
Create Date: 2025-12-17 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "fa4e07a7f26d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add invite system and email verification fields."""
    # 1. Add email verification fields to users table
    op.add_column(
        "users",
        sa.Column(
            "email_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_verification_token", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_verification_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # 2. Make company_id nullable in users table
    op.alter_column(
        "users",
        "company_id",
        existing_type=postgresql.UUID(),
        nullable=True,
    )

    # 3. Add onboarding_completed to companies table
    op.add_column(
        "companies",
        sa.Column(
            "onboarding_completed", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )

    # 4. Create invites table
    op.create_table(
        "invites",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("role", sa.String(50), server_default=sa.text("'recruiter'"), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("uses_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("code"),
        sa.CheckConstraint("uses_count >= 0", name="positive_uses_count"),
        sa.CheckConstraint("max_uses IS NULL OR max_uses > 0", name="valid_max_uses"),
        sa.CheckConstraint(
            "role IN ('admin', 'recruiter', 'interviewer')", name="valid_invite_role"
        ),
    )

    # 5. Create indexes for invites table
    op.create_index("idx_invites_code", "invites", ["code"])
    op.create_index("idx_invites_company_id", "invites", ["company_id"])
    op.create_index("idx_invites_email", "invites", ["email"])

    # 6. Backfill: Mark existing users as email_verified (they have company_id)
    op.execute(
        """
        UPDATE users
        SET email_verified = true,
            email_verified_at = CURRENT_TIMESTAMP
        WHERE company_id IS NOT NULL
        """
    )

    # 7. Backfill: Mark existing companies as onboarding_completed
    op.execute(
        """
        UPDATE companies
        SET onboarding_completed = true
        """
    )


def downgrade() -> None:
    """Remove invite system and email verification fields."""
    # 1. Drop invites table and indexes
    op.drop_index("idx_invites_email", table_name="invites")
    op.drop_index("idx_invites_company_id", table_name="invites")
    op.drop_index("idx_invites_code", table_name="invites")
    op.drop_table("invites")

    # 2. Remove onboarding_completed from companies
    op.drop_column("companies", "onboarding_completed")

    # 3. Make company_id NOT NULL again (will fail if any NULL values exist)
    op.alter_column(
        "users",
        "company_id",
        existing_type=postgresql.UUID(),
        nullable=False,
    )

    # 4. Remove email verification fields from users
    op.drop_column("users", "email_verification_expires_at")
    op.drop_column("users", "email_verification_token")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verified")
