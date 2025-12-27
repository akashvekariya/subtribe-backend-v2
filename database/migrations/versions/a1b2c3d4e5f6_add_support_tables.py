"""add_support_tables

Revision ID: a1b2c3d4e5f6
Revises: b4feaa74fed8
Create Date: 2025-12-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'b4feaa74fed8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create support_tickets table
    op.create_table(
        'support_tickets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('subject', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='open'),
        sa.Column('priority', sa.String(50), nullable=False, server_default='medium'),
        sa.Column('discord_channel_id', sa.String(100), nullable=True),
        sa.Column('discord_thread_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for support_tickets
    op.create_index('ix_support_tickets_company_id', 'support_tickets', ['company_id'])
    op.create_index('ix_support_tickets_user_id', 'support_tickets', ['user_id'])
    op.create_index('ix_support_tickets_status', 'support_tickets', ['status'])
    op.create_index('ix_support_tickets_created_at', 'support_tickets', ['created_at'])

    # Create support_messages table
    op.create_table(
        'support_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('ticket_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('source', sa.String(50), nullable=False, server_default='dashboard'),
        sa.Column('discord_message_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for support_messages
    op.create_index('ix_support_messages_ticket_id', 'support_messages', ['ticket_id'])
    op.create_index('ix_support_messages_user_id', 'support_messages', ['user_id'])
    op.create_index('ix_support_messages_created_at', 'support_messages', ['created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes for support_messages
    op.drop_index('ix_support_messages_created_at', table_name='support_messages')
    op.drop_index('ix_support_messages_user_id', table_name='support_messages')
    op.drop_index('ix_support_messages_ticket_id', table_name='support_messages')

    # Drop support_messages table
    op.drop_table('support_messages')

    # Drop indexes for support_tickets
    op.drop_index('ix_support_tickets_created_at', table_name='support_tickets')
    op.drop_index('ix_support_tickets_status', table_name='support_tickets')
    op.drop_index('ix_support_tickets_user_id', table_name='support_tickets')
    op.drop_index('ix_support_tickets_company_id', table_name='support_tickets')

    # Drop support_tickets table
    op.drop_table('support_tickets')
