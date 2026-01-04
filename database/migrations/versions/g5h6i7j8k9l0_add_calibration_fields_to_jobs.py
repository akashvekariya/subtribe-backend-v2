"""Add calibration fields to jobs table.

Revision ID: g5h6i7j8k9l0
Revises: d4e5f6g7h8i9
Create Date: 2025-01-03

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "g5h6i7j8k9l0"
down_revision = "d4e5f6g7h8i9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add calibration-related columns to jobs table
    op.add_column(
        "jobs",
        sa.Column(
            "calibration_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Calibration decisions made by recruiter",
        ),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "evaluation_framework",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="AI-generated evaluation framework for scoring candidates",
        ),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "calibrated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="When calibration was completed",
        ),
    )


def downgrade() -> None:
    op.drop_column("jobs", "calibrated_at")
    op.drop_column("jobs", "evaluation_framework")
    op.drop_column("jobs", "calibration_summary")
