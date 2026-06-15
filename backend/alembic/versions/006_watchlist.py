"""Watchlist + opportunity prefs tables — Phase 9.

Revision ID: 006_watchlist
Revises: 005_ai_models
Create Date: 2026-06-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006_watchlist"
down_revision: Union[str, None] = "005_ai_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watchlist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("exchange", sa.String(10), server_default="NSE"),
        sa.Column("source", sa.String(20), server_default="manual"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("target_price", sa.String(20), nullable=True),
        sa.Column("snapshot", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "symbol", "exchange", name="uq_watchlist_user_symbol"),
    )
    op.create_index("ix_watchlist_items_user_id", "watchlist_items", ["user_id"])
    op.create_index("ix_watchlist_user_created", "watchlist_items", ["user_id", "created_at"])

    op.create_table(
        "user_opportunity_prefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("exchange", sa.String(10), server_default="NSE"),
        sa.Column("action", sa.String(20), server_default="avoid"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "symbol", "exchange", "action", name="uq_opp_pref_user_symbol_action"),
    )
    op.create_index("ix_user_opportunity_prefs_user_id", "user_opportunity_prefs", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_opportunity_prefs")
    op.drop_table("watchlist_items")
