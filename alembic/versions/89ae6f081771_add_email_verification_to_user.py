"""add_email_verification_to_user

Revision ID: 89ae6f081771
Revises: 8f87305a72d4
Create Date: 2025-05-13 16:35:48.876878

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '89ae6f081771'
down_revision: Union[str, None] = '8f87305a72d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
