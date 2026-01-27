"""merge_heads

Revision ID: b4feaa74fed8
Revises: e71f87cc765a, f3846590de32
Create Date: 2025-11-26 12:46:35.318128

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4feaa74fed8'
down_revision: Union[str, Sequence[str], None] = ('e71f87cc765a', 'f3846590de32')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
