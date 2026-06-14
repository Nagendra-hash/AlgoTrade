"""003_add_telegram_settings_to_users

Revision ID: 003_telegram_settings
Revises: 002_broker_connections
Create Date: 2026-06-13

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003_telegram_settings'
down_revision: Union[str, None] = '002_broker_connections'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('telegram_bot_token', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('telegram_chat_id', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'telegram_chat_id')
    op.drop_column('users', 'telegram_bot_token')
