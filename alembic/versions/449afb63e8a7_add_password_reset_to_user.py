"""add_password_reset_to_user

Revision ID: 449afb63e8a7
Revises: 89ae6f081771
Create Date: 2025-05-13 16:40:10.220549

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '449afb63e8a7'
down_revision: Union[str, None] = '89ae6f081771'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
