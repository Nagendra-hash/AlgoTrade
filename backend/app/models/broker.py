"""
Broker connection database model — persists Angel One sessions in PostgreSQL/Supabase
so connections survive server restarts and don't require reconnecting on every page load.
Path: backend/app/models/broker.py
"""
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid
from app.core.database import Base


class BrokerConnection(Base):
    __tablename__ = "broker_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_name = Column(String(20), nullable=False, default="angel_one")
    
    # Stored credentials (encrypted in production)
    api_key = Column(String(255), nullable=False)
    client_id = Column(String(100), nullable=False)
    
    # Stored credentials for re-login when token expires
    # These are stored to allow automatic reconnection without user re-entering them
    # IMPORTANT: In production, encrypt these fields at the application level
    encrypted_password = Column(Text, nullable=True)
    encrypted_totp_secret = Column(Text, nullable=True)
    
    # Current session tokens from Angel One
    jwt_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    feed_token = Column(Text, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    last_connected_at = Column(DateTime(timezone=True), nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<BrokerConnection {self.broker_name}:{self.client_id} user={str(self.user_id)[:8]}>"
