"""integrate supabase auth user fields

Revision ID: 90c506389f46
Revises: 832e47899289
Create Date: 2025-05-14 06:29:51.842898

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '90c506389f46'
down_revision: Union[str, None] = '832e47899289'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
