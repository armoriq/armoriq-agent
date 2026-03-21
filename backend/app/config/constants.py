"""
Centralized constants for the entire backend.
All URLs, endpoints, timeouts, and defaults in one place.
"""


# =============================================================================
# API ENDPOINTS (Internal Routes)
# =============================================================================
class APIRoutes:
    """API route definitions."""

    PREFIX = "/api/v1"

    # Auth
    AUTH_PREFIX = "/auth"
    AUTH_LOGIN = "/login"
    AUTH_REGISTER = "/register"
    AUTH_GOOGLE = "/google"
    AUTH_GOOGLE_CALLBACK = "/google/callback"
    AUTH_REFRESH = "/refresh"
    AUTH_ME = "/me"
    AUTH_LOGOUT = "/logout"

    # Chat
    CHAT_PREFIX = "/chat"
    CHAT_SEND = ""
    CHAT_STREAM = "/stream"
    CHAT_HISTORY = "/{conversation_id}/history"
    CHAT_CONVERSATIONS = "/conversations"
    CHAT_CONVERSATION = "/{conversation_id}"

    # MCP
    MCP_PREFIX = "/mcp"
    MCP_ADD = "/add"
    MCP_LIST = ""
    MCP_STATUS = "/status"
    MCP_RECONNECT = "/{mcp_id}/reconnect"
    MCP_DELETE = "/{mcp_id}"
    MCP_UPDATE_TIMEOUT = "/{mcp_id}/timeout"
    MCP_TOOLS = "/{mcp_id}/tools"

    # LLM
    LLM_PREFIX = "/llm"
    LLM_PROVIDERS = "/providers"
    LLM_CONFIG = "/config"
    LLM_CONFIG_LIST = "/configs"
    LLM_CONFIG_DELETE = "/config/{config_id}"

    # Plans
    PLANS_PREFIX = "/plans"
    PLANS_LIST = ""
    PLANS_DETAIL = "/{plan_id}"


# =============================================================================
# EXTERNAL SERVICE URLS
# =============================================================================
class ExternalURLs:
    """External service URLs."""

    # LLM Providers
    OPENAI_API = "https://api.openai.com/v1"
    ANTHROPIC_API = "https://api.anthropic.com"
    GOOGLE_AI_API = "https://generativelanguage.googleapis.com"
    MISTRAL_API = "https://api.mistral.ai/v1"
    OPENROUTER_API = "https://openrouter.ai/api/v1"
    OLLAMA_DEFAULT = "http://localhost:11434"

    # ArmorIQ
    ARMORIQ_PROXY = "https://proxy.armoriq.io"

    # Google OAuth
    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


# =============================================================================
# TIMEOUTS & LIMITS
# =============================================================================
class Timeouts:
    """Timeout and limit configurations."""

    # MCP
    MCP_IDLE_DEFAULT_SECONDS = 300  # 5 minutes
    MCP_CONNECTION_TIMEOUT_SECONDS = 30
    MCP_CLEANUP_INTERVAL_SECONDS = 60

    # LLM
    LLM_REQUEST_TIMEOUT_SECONDS = 120
    LLM_STREAMING_TIMEOUT_SECONDS = 300

    # Auth
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7

    # ArmorIQ
    ARMORIQ_TOKEN_EXPIRE_SECONDS = 3600


# =============================================================================
# DEFAULT VALUES
# =============================================================================
class Defaults:
    """Default values for various settings."""

    # LLM
    LLM_TEMPERATURE = 0.7
    LLM_MAX_TOKENS = 4096

    # Pagination
    PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # Chat
    MAX_CONVERSATION_HISTORY = 50


# =============================================================================
# LLM PROVIDER MODELS
# =============================================================================
PROVIDER_MODELS: dict[str, list[str]] = {
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
        "o1-preview",
        "o1-mini",
    ],
    "anthropic": [
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
        "claude-3-opus-latest",
        "claude-3-sonnet-20240229",
    ],
    "google": [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ],
    "mistral": [
        "mistral-large-latest",
        "mistral-medium-latest",
        "mistral-small-latest",
    ],
    "ollama": [
        "llama3.2",
        "llama3.1",
        "mistral",
        "mixtral",
        "codellama",
    ],
    "openrouter": [
        "openai/gpt-4o",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-pro-1.5",
        "meta-llama/llama-3.1-405b-instruct",
        "openrouter/auto",
    ],
}

# List of all supported providers
SUPPORTED_PROVIDERS = list(PROVIDER_MODELS.keys())


# =============================================================================
# MCP CONNECTION TYPES
# =============================================================================
class MCPConnectionTypes:
    """MCP connection type definitions."""

    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"
    WEBSOCKET = "websocket"

    ALL = [STDIO, SSE, HTTP, WEBSOCKET]


# =============================================================================
# ERROR MESSAGES
# =============================================================================
class ErrorMessages:
    """Standardized error messages."""

    # Auth
    INVALID_CREDENTIALS = "Invalid email or password"
    TOKEN_EXPIRED = "Token has expired"
    TOKEN_INVALID = "Invalid token"
    USER_NOT_FOUND = "User not found"
    EMAIL_ALREADY_EXISTS = "Email already registered"
    UNAUTHORIZED = "Not authenticated"

    # MCP
    MCP_CONNECTION_FAILED = "Failed to connect to MCP server"
    MCP_NOT_FOUND = "MCP configuration not found"
    MCP_NOT_CONNECTED = "MCP is not connected"
    MCP_ALREADY_EXISTS = "MCP with this name already exists"

    # LLM
    LLM_PROVIDER_INVALID = "Invalid LLM provider"
    LLM_CONFIG_NOT_FOUND = "LLM configuration not found"
    LLM_API_KEY_INVALID = "Invalid API key for provider"

    # ArmorIQ
    ARMORIQ_VERIFICATION_FAILED = "ArmorIQ plan verification failed"
    ARMORIQ_TOKEN_EXPIRED = "ArmorIQ token has expired"

    # General
    INTERNAL_ERROR = "An internal error occurred"
    NOT_FOUND = "Resource not found"
    VALIDATION_ERROR = "Validation error"


# =============================================================================
# HTTP HEADERS
# =============================================================================
class Headers:
    """Custom HTTP headers."""

    # OpenRouter
    OPENROUTER_REFERER = "HTTP-Referer"
    OPENROUTER_TITLE = "X-Title"

    # SSE
    CACHE_CONTROL = "Cache-Control"
    CONNECTION = "Connection"


# =============================================================================
# DATABASE
# =============================================================================
class DatabaseTables:
    """Database table names."""

    USERS = "users"
    CONVERSATIONS = "conversations"
    MESSAGES = "messages"
    MCP_CONFIGS = "mcp_configs"
    MCP_CONNECTION_STATUS = "mcp_connection_status"
    USER_LLM_CONFIGS = "user_llm_configs"
    INTENT_PLANS = "intent_plans"
