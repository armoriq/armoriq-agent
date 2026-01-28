"""
Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, SecretStr


# =============================================================================
# AUTH SCHEMAS
# =============================================================================
class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    name: str


class UserCreate(UserBase):
    """User registration schema."""

    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    """User login schema."""

    email: EmailStr
    password: str


class UserResponse(UserBase):
    """User response schema."""

    id: UUID
    avatar_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TokenPair(BaseModel):
    """JWT token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Token refresh request."""

    refresh_token: str


# =============================================================================
# CHAT SCHEMAS
# =============================================================================
class MessageBase(BaseModel):
    """Base message schema."""

    role: str
    content: Optional[str] = None


class MessageCreate(MessageBase):
    """Message creation schema."""

    pass


class MessageResponse(MessageBase):
    """Message response schema."""

    id: UUID
    tool_calls: Optional[list[dict[str, Any]]] = None
    tool_results: Optional[list[dict[str, Any]]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    """Conversation creation schema."""

    title: Optional[str] = None


class ConversationResponse(BaseModel):
    """Conversation response schema."""

    id: UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    """Chat request schema."""

    conversation_id: Optional[UUID] = None  # None = new conversation
    message: str
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"


class ChatStreamChunk(BaseModel):
    """SSE stream chunk."""

    type: str  # content, tool_call, tool_result, plan_captured, done, error
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[dict[str, Any]] = None
    result: Optional[Any] = None
    plan_id: Optional[str] = None
    message: Optional[str] = None


# =============================================================================
# MCP SCHEMAS
# =============================================================================
class MCPConfigBase(BaseModel):
    """Base MCP config schema."""

    name: str
    connection_type: str  # stdio, sse, websocket
    url: Optional[str] = None
    command: Optional[str] = None
    args: Optional[list[str]] = None
    env: Optional[dict[str, str]] = None
    idle_timeout_seconds: int = 300


class MCPConfigCreate(MCPConfigBase):
    """MCP config creation schema."""

    pass


class MCPConfigUpdate(BaseModel):
    """MCP config update schema."""

    name: Optional[str] = None
    enabled: Optional[bool] = None
    idle_timeout_seconds: Optional[int] = None


class MCPConfigResponse(MCPConfigBase):
    """MCP config response schema."""

    id: UUID
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MCPStatusResponse(BaseModel):
    """MCP connection status response."""

    id: UUID
    name: str
    status: str  # disconnected, connecting, connected, error
    last_used: Optional[datetime] = None
    tool_count: int = 0
    idle_timeout_seconds: Optional[int] = 300
    error_message: Optional[str] = None


class MCPToolResponse(BaseModel):
    """MCP tool schema."""

    name: str
    description: Optional[str] = None
    input_schema: Optional[dict[str, Any]] = None


# =============================================================================
# LLM SCHEMAS
# =============================================================================
class LLMConfigCreate(BaseModel):
    """LLM config creation schema."""

    provider: str
    api_key: str  # Will be encrypted before storage
    is_default: bool = False
    settings: Optional[dict[str, Any]] = None  # temperature, max_tokens, etc.


class LLMConfigUpdate(BaseModel):
    """LLM config update schema."""

    api_key: Optional[str] = None
    is_default: Optional[bool] = None
    settings: Optional[dict[str, Any]] = None


class LLMConfigResponse(BaseModel):
    """LLM config response schema (without API key)."""

    id: UUID
    provider: str
    is_default: bool
    settings: Optional[dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LLMProviderInfo(BaseModel):
    """LLM provider information."""

    id: str
    name: str
    models: list[str]
    configured: bool = False  # Whether user has added API key


class LLMProvidersResponse(BaseModel):
    """Response with all available providers."""

    providers: list[LLMProviderInfo]


# =============================================================================
# INTENT PLAN SCHEMAS
# =============================================================================
class PlanStepSchema(BaseModel):
    """Single step in a plan."""

    action: str
    mcp: str
    description: Optional[str] = None
    params: Optional[dict[str, Any]] = None


class IntentPlanCreate(BaseModel):
    """Intent plan creation schema."""

    steps: list[PlanStepSchema]
    reasoning: Optional[str] = None


class IntentPlanResponse(BaseModel):
    """Intent plan response schema."""

    id: UUID
    conversation_id: Optional[UUID] = None
    plan_hash: Optional[str] = None
    plan_data: dict[str, Any]
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =============================================================================
# GENERAL SCHEMAS
# =============================================================================
class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    """Error response schema."""

    detail: str
    code: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
