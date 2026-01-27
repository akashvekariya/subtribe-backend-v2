"""add_ai_resume_eval_tables

Revision ID: 8da679bb99d2
Revises: 0f8276c14590
Create Date: 2026-01-04 21:25:53.704525

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8da679bb99d2'
down_revision: str | Sequence[str] | None = '0f8276c14590'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - Add AI Resume Evaluation tables and columns."""

    # 1. Add max_concurrent_ai_evaluations column to companies table
    op.add_column(
        'companies',
        sa.Column(
            'max_concurrent_ai_evaluations',
            sa.Integer(),
            nullable=True,
            comment='Max concurrent AI resume evaluations. If null, uses plan default.'
        )
    )

    # 2. Create ai_resume_eval_batches table
    op.create_table(
        'ai_resume_eval_batches',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('triggered_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('total_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('queued_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('processing_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('completed_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('failed_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('status', sa.String(50), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('estimated_seconds', sa.Integer(), nullable=True),
        sa.Column('estimated_completion_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('started_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('completed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('notification_sent', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('notification_sent_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('rate_limited_until', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.PrimaryKeyConstraint('id', name='ai_resume_eval_batches_pkey'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], name='ai_resume_eval_batches_job_id_fkey', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name='ai_resume_eval_batches_company_id_fkey', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id'], name='ai_resume_eval_batches_triggered_by_fkey', ondelete='SET NULL'),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')",
            name='valid_ai_resume_eval_batch_status'
        ),
    )

    # Create indexes for ai_resume_eval_batches
    op.create_index('idx_ai_resume_eval_batches_company_status', 'ai_resume_eval_batches', ['company_id', 'status'])
    op.create_index('idx_ai_resume_eval_batches_job', 'ai_resume_eval_batches', ['job_id'])

    # 3. Create ai_resume_eval_tasks table
    op.create_table(
        'ai_resume_eval_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('application_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(50), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('attempt_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('max_attempts', sa.Integer(), server_default=sa.text('5'), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_code', sa.String(50), nullable=True),
        sa.Column('scheduled_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('started_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('completed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('next_retry_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('cloud_task_name', sa.String(500), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id', name='ai_resume_eval_tasks_pkey'),
        sa.ForeignKeyConstraint(['batch_id'], ['ai_resume_eval_batches.id'], name='ai_resume_eval_tasks_batch_id_fkey', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], name='ai_resume_eval_tasks_application_id_fkey', ondelete='CASCADE'),
        sa.CheckConstraint(
            "status IN ('pending', 'queued', 'processing', 'completed', 'failed', 'retry_scheduled', 'skipped')",
            name='valid_ai_resume_eval_task_status'
        ),
        sa.CheckConstraint(
            'attempt_count >= 0 AND attempt_count <= max_attempts + 1',
            name='valid_ai_resume_eval_attempt_count'
        ),
    )

    # Create indexes for ai_resume_eval_tasks
    op.create_index('idx_ai_resume_eval_tasks_batch_status', 'ai_resume_eval_tasks', ['batch_id', 'status'])
    op.create_index(
        'idx_ai_resume_eval_tasks_retry',
        'ai_resume_eval_tasks',
        ['status', 'next_retry_at'],
        postgresql_where=sa.text("status = 'retry_scheduled'")
    )
    op.create_index(
        'idx_ai_resume_eval_tasks_stuck',
        'ai_resume_eval_tasks',
        ['status', 'started_at'],
        postgresql_where=sa.text("status = 'processing'")
    )
    op.create_index(
        'idx_ai_resume_eval_tasks_batch_app_unique',
        'ai_resume_eval_tasks',
        ['batch_id', 'application_id'],
        unique=True
    )

    # 4. Add AI resume evaluation columns to applications table
    op.add_column(
        'applications',
        sa.Column('ai_resume_eval_status', sa.String(50), nullable=True)
    )
    op.add_column(
        'applications',
        sa.Column(
            'ai_resume_eval_batch_id',
            postgresql.UUID(as_uuid=True),
            nullable=True
        )
    )

    # Add foreign key constraint for ai_resume_eval_batch_id
    op.create_foreign_key(
        'applications_ai_resume_eval_batch_id_fkey',
        'applications',
        'ai_resume_eval_batches',
        ['ai_resume_eval_batch_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade schema - Remove AI Resume Evaluation tables and columns."""

    # 1. Remove FK constraint and columns from applications
    op.drop_constraint('applications_ai_resume_eval_batch_id_fkey', 'applications', type_='foreignkey')
    op.drop_column('applications', 'ai_resume_eval_batch_id')
    op.drop_column('applications', 'ai_resume_eval_status')

    # 2. Drop ai_resume_eval_tasks table and indexes
    op.drop_index('idx_ai_resume_eval_tasks_batch_app_unique', 'ai_resume_eval_tasks')
    op.drop_index('idx_ai_resume_eval_tasks_stuck', 'ai_resume_eval_tasks')
    op.drop_index('idx_ai_resume_eval_tasks_retry', 'ai_resume_eval_tasks')
    op.drop_index('idx_ai_resume_eval_tasks_batch_status', 'ai_resume_eval_tasks')
    op.drop_table('ai_resume_eval_tasks')

    # 3. Drop ai_resume_eval_batches table and indexes
    op.drop_index('idx_ai_resume_eval_batches_job', 'ai_resume_eval_batches')
    op.drop_index('idx_ai_resume_eval_batches_company_status', 'ai_resume_eval_batches')
    op.drop_table('ai_resume_eval_batches')

    # 4. Remove column from companies
    op.drop_column('companies', 'max_concurrent_ai_evaluations')
