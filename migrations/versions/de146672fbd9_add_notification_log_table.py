"""add_notification_log_table

Revision ID: de146672fbd9
Revises: 149a5c59c5b7
Create Date: 2025-12-13 17:28:17.218621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de146672fbd9'
down_revision: Union[str, None] = '149a5c59c5b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create notification_logs table
    op.create_table('notification_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vacancy_alert_id', sa.Integer(), nullable=True),
        sa.Column('message_type', sa.String(), nullable=True),
        sa.Column('message_content', sa.Text(), nullable=True),
        sa.Column('recipient_phone', sa.String(), nullable=True),
        sa.Column('delivery_method', sa.String(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['vacancy_alert_id'], ['vacancy_alerts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Drop notification_logs table
    op.drop_table('notification_logs')
