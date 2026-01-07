"""Rename resume_parsed_text to resume_parsed_md

Revision ID: h6i7j8k9l0m1
Revises: 8da679bb99d2
Create Date: 2026-01-07

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'h6i7j8k9l0m1'
down_revision: Union[str, None] = '8da679bb99d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename column from resume_parsed_text to resume_parsed_md
    op.alter_column(
        'applications',
        'resume_parsed_text',
        new_column_name='resume_parsed_md'
    )


def downgrade() -> None:
    # Rename column back from resume_parsed_md to resume_parsed_text
    op.alter_column(
        'applications',
        'resume_parsed_md',
        new_column_name='resume_parsed_text'
    )
