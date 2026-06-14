"""Initial schema — all tables.

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email",         sa.String(255), nullable=False, unique=True),
        sa.Column("username",      sa.String(50),  nullable=False, unique=True),
        sa.Column("full_name",     sa.String(100), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active",     sa.Boolean,     default=True),
        sa.Column("is_verified",   sa.Boolean,     default=False),
        sa.Column("is_superuser",  sa.Boolean,     default=False),
        sa.Column("role",          sa.String(20),  default="trader"),
        sa.Column("phone",         sa.String(20),  nullable=True),
        sa.Column("avatar_url",    sa.String(500), nullable=True),
        sa.Column("bio",           sa.Text,        nullable=True),
        sa.Column("paper_trading_balance", sa.String(20), default="1000000"),
        sa.Column("email_verification_token", sa.String(255), nullable=True),
        sa.Column("password_reset_token",     sa.String(255), nullable=True),
        sa.Column("password_reset_expires",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",    sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at",    sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email",    "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])

    # orders
    op.create_table(
        "orders",
        sa.Column("id",                postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",           postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("broker_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("broker_order_id",   sa.String(100), nullable=True),
        sa.Column("symbol",            sa.String(50),  nullable=False),
        sa.Column("exchange",          sa.String(10),  nullable=False, default="NSE"),
        sa.Column("side",              sa.String(10),  nullable=False),
        sa.Column("order_type",        sa.String(30),  nullable=False),
        sa.Column("product_type",      sa.String(20),  nullable=False, default="INTRADAY"),
        sa.Column("status",            sa.String(20),  nullable=False, default="PENDING"),
        sa.Column("quantity",          sa.Integer,     nullable=False),
        sa.Column("price",             sa.Float,       nullable=True),
        sa.Column("trigger_price",     sa.Float,       nullable=True),
        sa.Column("average_price",     sa.Float,       nullable=True),
        sa.Column("filled_quantity",   sa.Integer,     nullable=True, default=0),
        sa.Column("stop_loss",         sa.Float,       nullable=True),
        sa.Column("take_profit",       sa.Float,       nullable=True),
        sa.Column("strategy_id",       postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_paper_trade",    sa.String(5),   nullable=False, default="true"),
        sa.Column("notes",             sa.Text,        nullable=True),
        sa.Column("broker_message",    sa.Text,        nullable=True),
        sa.Column("placed_at",         sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at",        sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at",       sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_symbol",  "orders", ["symbol"])

    # strategies
    op.create_table(
        "strategies",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",       postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name",          sa.String(200), nullable=False),
        sa.Column("description",   sa.Text,        nullable=True),
        sa.Column("strategy_type", sa.String(50),  default="custom"),
        sa.Column("status",        sa.String(20),  default="draft"),
        sa.Column("version",       sa.Integer,     default=1),
        sa.Column("user_prompt",   sa.Text,        nullable=True),
        sa.Column("python_code",   sa.Text,        nullable=True),
        sa.Column("entry_logic",   sa.Text,        nullable=True),
        sa.Column("exit_logic",    sa.Text,        nullable=True),
        sa.Column("risk_rules",    sa.Text,        nullable=True),
        sa.Column("indicators",    postgresql.JSON, nullable=True),
        sa.Column("parameters",    postgresql.JSON, nullable=True),
        sa.Column("symbols",       postgresql.JSON, nullable=True),
        sa.Column("timeframe",     sa.String(10),  default="1d"),
        sa.Column("exchange",      sa.String(10),  default="NSE"),
        sa.Column("max_position_size",  sa.Float,  default=10.0),
        sa.Column("stop_loss_pct",      sa.Float,  default=2.0),
        sa.Column("take_profit_pct",    sa.Float,  default=4.0),
        sa.Column("max_drawdown_pct",   sa.Float,  default=15.0),
        sa.Column("backtest_results",   postgresql.JSON, nullable=True),
        sa.Column("is_public",     sa.Boolean,     default=False),
        sa.Column("cloned_from",   postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("clone_count",   sa.Integer,     default=0),
        sa.Column("likes",         sa.Integer,     default=0),
        sa.Column("tags",          postgresql.JSON, nullable=True),
        sa.Column("is_paper_active", sa.Boolean,   default=False),
        sa.Column("is_live_active",  sa.Boolean,   default=False),
        sa.Column("broker_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at",    sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at",    sa.DateTime(timezone=True), nullable=False),
    )

    # alerts
    op.create_table(
        "alerts",
        sa.Column("id",           postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",      postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol",       sa.String(50),  nullable=False),
        sa.Column("exchange",     sa.String(10),  nullable=False, default="NSE"),
        sa.Column("name",         sa.String(200), nullable=True),
        sa.Column("condition",    sa.String(30),  nullable=False),
        sa.Column("target_value", sa.Float,       nullable=False),
        sa.Column("current_value",sa.Float,       nullable=True),
        sa.Column("status",       sa.String(20),  nullable=False, default="active"),
        sa.Column("is_repeating", sa.Boolean,     default=False),
        sa.Column("repeat_interval_minutes", sa.Integer, default=60),
        sa.Column("channels",     postgresql.JSON, nullable=True),
        sa.Column("notes",        sa.Text,        nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger_count",sa.Integer,     default=0),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",   sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at",   sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_alerts_user_id", "alerts", ["user_id"])
    op.create_index("ix_alerts_symbol",  "alerts", ["symbol"])

    # notifications
    op.create_table(
        "notifications",
        sa.Column("id",                postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",           postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_id",          postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title",             sa.String(300), nullable=False),
        sa.Column("message",           sa.Text,        nullable=False),
        sa.Column("symbol",            sa.String(50),  nullable=True),
        sa.Column("notification_type", sa.String(50),  default="alert"),
        sa.Column("data",              postgresql.JSON, nullable=True),
        sa.Column("channel",           sa.String(30),  default="in_app"),
        sa.Column("is_read",           sa.Boolean,     default=False),
        sa.Column("read_at",           sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",        sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"],  ["users.id"],  ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])

    # sentiment_cache
    op.create_table(
        "sentiment_cache",
        sa.Column("id",          postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol",      sa.String(50),  nullable=False, unique=True),
        sa.Column("exchange",    sa.String(10),  default="NSE"),
        sa.Column("score",       sa.Float,       nullable=False, default=0.0),
        sa.Column("label",       sa.String(20),  default="neutral"),
        sa.Column("confidence",  sa.Float,       nullable=False, default=0.0),
        sa.Column("explanation", sa.Text,        nullable=True),
        sa.Column("headlines",   postgresql.JSON, nullable=True),
        sa.Column("news_count",  sa.Integer,     default=0),
        sa.Column("cached_at",   sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at",  sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_stale",    sa.Boolean,     default=False),
    )
    op.create_index("ix_sentiment_cache_symbol", "sentiment_cache", ["symbol"])


def downgrade() -> None:
    op.drop_table("sentiment_cache")
    op.drop_table("notifications")
    op.drop_table("alerts")
    op.drop_table("strategies")
    op.drop_table("orders")
    op.drop_table("users")
