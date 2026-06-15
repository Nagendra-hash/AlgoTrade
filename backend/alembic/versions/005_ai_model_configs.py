"""Add ai_model_configs table + missing strategy columns from drifted schema.

Revision ID: 005_ai_models
Revises: 004_news_sources
Create Date: 2026-06-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '005_ai_models'
down_revision: Union[str, None] = '004_news_sources'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_model_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(32), nullable=False),
        sa.Column('label', sa.String(64), nullable=True),
        sa.Column('api_key', sa.Text, nullable=True),
        sa.Column('base_url', sa.String(255), nullable=True),
        sa.Column('model', sa.String(128), nullable=False),
        sa.Column('temperature', sa.Float, nullable=True, server_default='0.3'),
        sa.Column('max_tokens', sa.Integer, nullable=True, server_default='2048'),
        sa.Column('system_prompt', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=True, server_default=sa.false()),
        sa.Column('fallback_order', sa.Integer, nullable=True, server_default='0'),
        sa.Column('last_test_status', sa.String(16), nullable=True),
        sa.Column('last_test_message', sa.Text, nullable=True),
        sa.Column('last_tested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_ai_model_configs_id', 'ai_model_configs', ['id'])
    op.create_index('ix_ai_model_configs_user_id', 'ai_model_configs', ['user_id'])
    op.create_index('ix_ai_model_configs_is_active', 'ai_model_configs', ['is_active'])
    op.create_index('ix_ai_model_configs_user_provider', 'ai_model_configs', ['user_id', 'provider'], unique=True)

    # Heal pre-existing schema drift — these columns are referenced by the ORM but missing in older DBs
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = {c['name'] for c in insp.get_columns('strategies')}
    if 'trailing_stop_enabled' not in existing:
        op.add_column('strategies', sa.Column('trailing_stop_enabled', sa.Boolean, nullable=True, server_default=sa.false()))
    if 'trailing_stop_pct' not in existing:
        op.add_column('strategies', sa.Column('trailing_stop_pct', sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_index('ix_ai_model_configs_user_provider', table_name='ai_model_configs')
    op.drop_index('ix_ai_model_configs_is_active', table_name='ai_model_configs')
    op.drop_index('ix_ai_model_configs_user_id', table_name='ai_model_configs')
    op.drop_index('ix_ai_model_configs_id', table_name='ai_model_configs')
    op.drop_table('ai_model_configs')
