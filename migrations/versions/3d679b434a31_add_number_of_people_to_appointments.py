"""add_number_of_people_to_appointments

Revision ID: 3d679b434a31
Revises: de146672fbd9
Create Date: 2025-12-13 18:47:21.739368

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d679b434a31'
down_revision: Union[str, None] = 'de146672fbd9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add number_of_people column to appointments table
    op.add_column('appointments', sa.Column('number_of_people', sa.Integer(), nullable=True, default=1))


def downgrade() -> None:
    # Remove number_of_people column from appointments table
    op.drop_column('appointments', 'number_of_people')
