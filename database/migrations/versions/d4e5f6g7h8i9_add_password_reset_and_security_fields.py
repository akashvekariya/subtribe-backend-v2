"""add password reset and security fields to users

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2025-12-29 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6g7h8i9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6g7h8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add password reset and security tracking fields to users table."""
    # Password Reset fields
    op.add_column(
        "users",
        sa.Column("password_reset_token", sa.String(64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "password_reset_expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "password_reset_requested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )

    # Security Tracking fields
    op.add_column(
        "users",
        sa.Column("last_login_ip", sa.String(45), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "last_password_change",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("locked_until", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Index for password reset token lookup
    op.create_index(
        "ix_users_password_reset_token",
        "users",
        ["password_reset_token"],
    )


def downgrade() -> None:
    """Remove password reset and security tracking fields from users table."""
    # Drop index first
    op.drop_index("ix_users_password_reset_token", table_name="users")

    # Drop Security Tracking fields
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
    op.drop_column("users", "last_password_change")
    op.drop_column("users", "last_login_ip")

    # Drop Password Reset fields
    op.drop_column("users", "password_reset_requested_at")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_token")
