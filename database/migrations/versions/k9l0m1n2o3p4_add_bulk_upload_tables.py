"""add bulk upload tables

Revision ID: k9l0m1n2o3p4
Revises: j8k9l0m1n2o3
Create Date: 2026-01-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "k9l0m1n2o3p4"
down_revision: str | Sequence[str] | None = "j8k9l0m1n2o3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add bulk upload tables and processing_status column to applications."""

    # 1. Create bulk_upload_batches table
    op.create_table(
        "bulk_upload_batches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("zip_gcs_uri", sa.String(500), nullable=True),
        sa.Column("total_files", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("valid_pdfs", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("processed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "status", sa.String(50), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="bulk_upload_batches_pkey"),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name="bulk_upload_batches_job_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="bulk_upload_batches_company_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            name="bulk_upload_batches_uploaded_by_fkey",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'extracting', 'processing', 'completed', 'failed')",
            name="valid_bulk_upload_batch_status",
        ),
    )

    # Create indexes for bulk_upload_batches
    op.create_index(
        "idx_bulk_upload_batches_company_status",
        "bulk_upload_batches",
        ["company_id", "status"],
    )
    op.create_index("idx_bulk_upload_batches_job", "bulk_upload_batches", ["job_id"])

    # 2. Create bulk_upload_tasks table
    op.create_table(
        "bulk_upload_tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column(
            "status", sa.String(50), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("cloud_task_name", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="bulk_upload_tasks_pkey"),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["bulk_upload_batches.id"],
            name="bulk_upload_tasks_batch_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="bulk_upload_tasks_application_id_fkey",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'queued', 'processing', 'completed', 'failed', 'skipped')",
            name="valid_bulk_upload_task_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts + 1",
            name="valid_bulk_upload_attempt_count",
        ),
    )

    # Create indexes for bulk_upload_tasks
    op.create_index(
        "idx_bulk_upload_tasks_batch_status", "bulk_upload_tasks", ["batch_id", "status"]
    )
    op.create_index(
        "idx_bulk_upload_tasks_application_unique",
        "bulk_upload_tasks",
        ["application_id"],
        unique=True,
    )

    # 3. Add processing_status column to applications table
    # Tracks data readiness (complete, processing) - separate from hiring pipeline status
    op.add_column(
        "applications",
        sa.Column(
            "processing_status",
            sa.String(50),
            server_default=sa.text("'complete'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "valid_application_processing_status",
        "applications",
        "processing_status IN ('complete', 'processing')",
    )
    op.create_index(
        "idx_applications_processing_status",
        "applications",
        ["job_id", "processing_status"],
    )


def downgrade() -> None:
    """Remove bulk upload tables and processing_status column."""

    # 1. Remove processing_status column from applications
    op.drop_index("idx_applications_processing_status", "applications")
    op.drop_constraint("valid_application_processing_status", "applications", type_="check")
    op.drop_column("applications", "processing_status")

    # 2. Drop bulk_upload_tasks table and indexes
    op.drop_index("idx_bulk_upload_tasks_application_unique", "bulk_upload_tasks")
    op.drop_index("idx_bulk_upload_tasks_batch_status", "bulk_upload_tasks")
    op.drop_table("bulk_upload_tasks")

    # 3. Drop bulk_upload_batches table and indexes
    op.drop_index("idx_bulk_upload_batches_job", "bulk_upload_batches")
    op.drop_index("idx_bulk_upload_batches_company_status", "bulk_upload_batches")
    op.drop_table("bulk_upload_batches")
