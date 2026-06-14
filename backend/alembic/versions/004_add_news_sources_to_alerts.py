"""Add news_sources column to alerts table.

Revision ID: 004_news_sources
Revises: 003_telegram_settings
Create Date: 2026-06-14

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '004_news_sources'
down_revision: Union[str, None] = '003_telegram_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'alerts',
        sa.Column('news_sources', postgresql.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column('alerts', 'news_sources')
