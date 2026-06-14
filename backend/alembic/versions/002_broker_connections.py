"""Broker connections table for persistent sessions.

Revision ID: 002_broker_connections
Revises: 001_initial
Create Date: 2024-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_broker_connections"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broker_connections",
        sa.Column("id",                postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",           postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("broker_name",       sa.String(20),  nullable=False, default="angel_one"),
        sa.Column("api_key",           sa.String(255), nullable=False),
        sa.Column("client_id",         sa.String(100), nullable=False),
        sa.Column("encrypted_password",    sa.Text,    nullable=True),
        sa.Column("encrypted_totp_secret", sa.Text,    nullable=True),
        sa.Column("jwt_token",         sa.Text,        nullable=True),
        sa.Column("refresh_token",     sa.Text,        nullable=True),
        sa.Column("feed_token",        sa.Text,        nullable=True),
        sa.Column("is_active",         sa.Boolean,     default=True, index=True),
        sa.Column("error_message",     sa.Text,        nullable=True),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_expires_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",        sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at",        sa.DateTime(timezone=True), nullable=False),
    )
    # Indexes are auto-created by index=True on column definitions above


def downgrade() -> None:
    op.drop_table("broker_connections")
