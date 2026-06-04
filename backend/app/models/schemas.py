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


# =============================================================================
# API KEY SCHEMAS
# =============================================================================

class ApiKeyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    expiresAt: Optional[datetime] = None


class ApiKeyResponse(BaseModel):
    apiKeyId: UUID
    name: str
    description: Optional[str] = None
    keyPrefix: str
    status: str
    usageCount: int
    lastUsedAt: Optional[datetime] = None
    lastUsedIp: Optional[str] = None
    expiresAt: Optional[datetime] = None
    createdAt: datetime
    createdBy: Optional[str] = None

    class Config:
        from_attributes = True


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned only on creation — includes the raw key."""
    apiKey: str


# =============================================================================
# POLICY SCHEMAS
# =============================================================================

class PolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    # Accept either the DB field name (effect) or the frontend field name
    effect: Optional[str] = None
    defaultEnforcementAction: Optional[str] = None
    target: Optional[str] = None
    targetId: Optional[str] = None
    targetType: Optional[str] = None
    tools: Optional[list[str]] = None

    def resolved_effect(self) -> str:
        return self.defaultEnforcementAction or self.effect or "block"

    def resolved_target(self) -> Optional[str]:
        return self.targetId or self.target


class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    effect: Optional[str] = None
    defaultEnforcementAction: Optional[str] = None
    target: Optional[str] = None
    targetId: Optional[str] = None
    tools: Optional[list[str]] = None
    enabled: Optional[bool] = None
    isActive: Optional[bool] = None

    def resolved_effect(self) -> Optional[str]:
        return self.defaultEnforcementAction or self.effect

    def resolved_enabled(self) -> Optional[bool]:
        if self.isActive is not None:
            return self.isActive
        return self.enabled


class PolicyResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    effect: str
    target: Optional[str] = None
    tools: Optional[list[str]] = None
    enabled: bool
    createdAt: datetime

    class Config:
        from_attributes = True


# =============================================================================
# AUDIT LOG SCHEMAS
# =============================================================================

class AuditLogCreate(BaseModel):
    token: str
    plan_id: Optional[str] = None
    step_index: int = 0
    action: str
    tool: str
    input: Optional[Any] = None
    output: Optional[Any] = None
    status: str = "success"
    error_message: Optional[str] = None
    duration_ms: int = 0
    executed_at: str
    is_delegated: Optional[bool] = False
    delegated_by: Optional[str] = None
    delegated_to: Optional[str] = None


class AuditLogResponse(BaseModel):
    audit_id: str
    iap_audit_index: Optional[int] = None
    iap_commitment: Optional[str] = None
    iap_sync_status: str = "logged"


class AuditBatchCreate(BaseModel):
    rows: list[AuditLogCreate]


class AuditBatchResponse(BaseModel):
    written: int
    failures: list[str] = []


# =============================================================================
# IAP SDK TOKEN SCHEMAS
# =============================================================================

class SdkTokenCreate(BaseModel):
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    context_id: Optional[str] = None
    plan: Optional[dict[str, Any]] = None
    policy: Optional[dict[str, Any]] = None
    expires_in: float = 600.0


class SdkTokenResponse(BaseModel):
    success: bool = True
    plan_id: str
    intent_reference: str
    plan_hash: str
    merkle_root: str
    composite_identity: str
    step_proofs: list[Any] = []
    jwt_token: str
    token: dict[str, Any]
    client_info: dict[str, Any] = {}
    policy_validation: dict[str, Any] = {}


class VerifyStepCreate(BaseModel):
    token: str
    tool_name: Optional[str] = None
    step_index: Optional[int] = None
    path: Optional[str] = None
    proof: Optional[list[Any]] = None
    context: Optional[dict[str, Any]] = None


# =============================================================================
# DASHBOARD SCHEMAS
# =============================================================================

class TokensConsumed(BaseModel):
    input: int
    output: int
    total: int
    estimatedSpendUsd: float
    byModel: dict[str, dict[str, int]]


class DashboardSummary(BaseModel):
    product: str
    window: str
    deviceApprovals: dict[str, Any]
    activeApiKeys: dict[str, Any]
    intentPlans: dict[str, Any]
    auditEvents: dict[str, Any]
    allowRate: float
    tokensConsumed: TokensConsumed


class ActivityEntry(BaseModel):
    id: str
    action: str
    tool: str
    status: str
    executedAt: str
    agentId: Optional[str] = None
    sessionId: Optional[str] = None


class TimeseriesEntry(BaseModel):
    date: str
    allowed: int
    denied: int


# =============================================================================
# AGENT SCHEMAS
# =============================================================================

class AgentResponse(BaseModel):
    agentId: str
    name: str
    url: str
    orgId: Optional[str] = None
    severityLevel: str = "low"
    vulnerabilityScore: float = 0.0
    chainAttacksDetected: int = 0
    createdAt: str
    metadata: dict[str, Any] = {}
