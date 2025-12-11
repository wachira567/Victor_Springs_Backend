"""create_saved_properties_table

Revision ID: 58f22368ad25
Revises: 5db90e32e802
Create Date: 2025-12-11 18:30:02.527454

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '58f22368ad25'
down_revision: Union[str, None] = '5db90e32e802'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('saved_properties',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('property_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_saved_properties_id'), 'saved_properties', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_saved_properties_id'), table_name='saved_properties')
    op.drop_table('saved_properties')
