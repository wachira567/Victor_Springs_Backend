"""add_saved_properties_table

Revision ID: 5db90e32e802
Revises: 65a46f147c28
Create Date: 2025-12-11 14:32:27.955542

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5db90e32e802'
down_revision: Union[str, None] = '65a46f147c28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
