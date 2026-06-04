"""
SQLAlchemy database models.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    LargeBinary,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class User(Base):
    """User model."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # Nullable for OAuth users
    name = Column(String(255), nullable=False)
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    avatar_url = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    mcp_configs = relationship("MCPConfig", back_populates="user", cascade="all, delete-orphan")
    llm_configs = relationship("UserLLMConfig", back_populates="user", cascade="all, delete-orphan")
    intent_plans = relationship("IntentPlan", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    """Conversation/chat session model."""

    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    intent_plans = relationship("IntentPlan", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """Chat message model."""

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(50), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=True)
    tool_calls = Column(JSONB, nullable=True)  # Tool calls made by assistant
    tool_results = Column(JSONB, nullable=True)  # Results from tool execution
    message_metadata = Column(JSONB, nullable=True)  # Additional metadata (renamed from 'metadata')
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class MCPConfig(Base):
    """User's MCP configuration."""

    __tablename__ = "mcp_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    connection_type = Column(String(50), nullable=False)  # stdio, sse, websocket
    url = Column(Text, nullable=True)  # For SSE/WebSocket
    command = Column(Text, nullable=True)  # For stdio
    args = Column(JSONB, nullable=True)  # Command arguments
    env = Column(JSONB, nullable=True)  # Environment variables
    enabled = Column(Boolean, default=True)
    idle_timeout_seconds = Column(Integer, default=300)  # 5 min default
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="mcp_configs")
    connection_status = relationship(
        "MCPConnectionStatus",
        back_populates="mcp_config",
        uselist=False,
        cascade="all, delete-orphan",
    )


class MCPConnectionStatus(Base):
    """MCP connection status for persistence across restarts."""

    __tablename__ = "mcp_connection_status"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mcp_config_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mcp_configs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status = Column(String(50), default="disconnected")  # disconnected, connecting, connected, error
    last_connected_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    cached_tools = Column(JSONB, nullable=True)  # Cache tools for quick startup
    error_message = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    mcp_config = relationship("MCPConfig", back_populates="connection_status")


class UserLLMConfig(Base):
    """User's LLM provider configuration."""

    __tablename__ = "user_llm_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(100), nullable=False)  # openai, anthropic, google, etc.
    api_key_encrypted = Column(LargeBinary, nullable=False)  # Encrypted API key
    is_default = Column(Boolean, default=False)
    settings = Column(JSONB, nullable=True)  # temperature, max_tokens, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="llm_configs")

    # Unique constraint: one config per provider per user
    __table_args__ = (
        # Index for faster lookups
        {"sqlite_autoincrement": True},
    )


class IntentPlan(Base):
    """ArmorIQ captured intent plans."""

    __tablename__ = "intent_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    plan_hash = Column(String(64), nullable=True)  # From ArmorIQ
    merkle_root = Column(String(64), nullable=True)  # From ArmorIQ
    plan_data = Column(JSONB, nullable=False)  # The actual plan
    token_expires_at = Column(DateTime, nullable=True)
    status = Column(String(50), default="pending")  # pending, executing, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="intent_plans")
    conversation = relationship("Conversation", back_populates="intent_plans")
    audit_logs = relationship("AuditLog", back_populates="intent_plan", cascade="all, delete-orphan")


class ApiKey(Base):
    """API keys issued to users for plugin/SDK authentication."""

    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    key_hash = Column(String(128), nullable=False, unique=True)  # bcrypt/sha256 hash
    key_prefix = Column(String(20), nullable=False)              # first 16 chars for display
    status = Column(String(20), default="active")               # active, revoked, expired
    last_used_at = Column(DateTime, nullable=True)
    last_used_ip = Column(String(45), nullable=True)
    usage_count = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    audit_logs = relationship("AuditLog", back_populates="api_key")


class Policy(Base):
    """ArmorClaude enforcement policies scoped to an API key / agent."""

    __tablename__ = "policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    effect = Column(String(20), default="allow")     # allow | deny | hold
    target = Column(String(200), nullable=True)      # agent_id or MCP server ID
    tools = Column(JSONB, nullable=True)             # list of tool name patterns
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class AuditLog(Base):
    """Per-tool-call audit trail emitted by the ArmorClaude plugin."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Link to issuing API key (nullable: SDK-direct calls may not have one)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True)
    # Link to intent plan (derived from the JWT token in the audit body)
    intent_plan_id = Column(UUID(as_uuid=True), ForeignKey("intent_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    product = Column(String(50), nullable=False, default="armorclaude", index=True)  # armorclaude | armorcodex
    tool = Column(String(200), nullable=False)
    action = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False)      # success | failed
    step_index = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    session_id = Column(String(64), nullable=True)
    executed_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    input_data = Column(JSONB, nullable=True)
    output_data = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)

    api_key = relationship("ApiKey", back_populates="audit_logs")
    intent_plan = relationship("IntentPlan", back_populates="audit_logs")
    user = relationship("User")
