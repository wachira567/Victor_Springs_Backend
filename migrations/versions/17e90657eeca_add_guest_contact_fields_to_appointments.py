"""add_guest_contact_fields_to_appointments

Revision ID: 17e90657eeca
Revises: 3d679b434a31
Create Date: 2025-12-13 18:53:45.538692

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "17e90657eeca"
down_revision: Union[str, None] = "3d679b434a31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add guest contact fields to appointments table
    op.add_column("appointments", sa.Column("guest_name", sa.String(), nullable=True))
    op.add_column("appointments", sa.Column("guest_email", sa.String(), nullable=True))
    op.add_column("appointments", sa.Column("guest_phone", sa.String(), nullable=True))


def downgrade() -> None:
    # Remove guest contact fields from appointments table
    op.drop_column("appointments", "guest_name")
    op.drop_column("appointments", "guest_email")
    op.drop_column("appointments", "guest_phone")
