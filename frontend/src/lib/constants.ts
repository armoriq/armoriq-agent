// =============================================================================
// API CONFIGURATION
// =============================================================================
export const API_CONFIG = {
  BASE_URL: process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000',
  API_PREFIX: '/api/v1',
} as const;

// =============================================================================
// API ENDPOINTS
// =============================================================================
export const ENDPOINTS = {
  // Auth
  AUTH: {
    LOGIN: '/auth/login',
    REGISTER: '/auth/register',
    GOOGLE: '/auth/google',
    GOOGLE_CALLBACK: '/auth/google/callback',
    REFRESH: '/auth/refresh',
    ME: '/auth/me',
    LOGOUT: '/auth/logout',
  },

  // Chat
  CHAT: {
    STREAM: '/chat/stream',
    HISTORY: (id: string) => `/chat/${id}/history`,
    CONVERSATIONS: '/chat/conversations',
    CONVERSATION: (id: string) => `/chat/${id}`,
  },

  // MCP
  MCP: {
    ADD: '/mcp/add',
    LIST: '/mcp',
    STATUS: '/mcp/status',
    RECONNECT: (id: string) => `/mcp/${id}/reconnect`,
    DELETE: (id: string) => `/mcp/${id}`,
    TOOLS: (id: string) => `/mcp/${id}/tools`,
  },

  // LLM
  LLM: {
    PROVIDERS: '/llm/providers',
    CONFIG: '/llm/config',
    CONFIGS: '/llm/configs',
  },

  // Plans
  PLANS: {
    LIST: '/plans',
    DETAIL: (id: string) => `/plans/${id}`,
  },
} as const;

// =============================================================================
// ROUTES (Frontend Pages)
// =============================================================================
export const ROUTES = {
  HOME: '/',
  CHAT: '/chat',
  CHAT_CONVERSATION: (id: string) => `/chat/${id}`,
  SETTINGS: '/settings',
  SETTINGS_LLM: '/settings/llm',
  SETTINGS_MCP: '/settings/mcp',
  PLANS: '/plans',
  LOGIN: '/login',
  REGISTER: '/register',
} as const;

// =============================================================================
// LLM PROVIDERS - Latest models as of January 2026
// =============================================================================
export const LLM_PROVIDERS = {
  openai: {
    id: 'openai',
    name: 'OpenAI',
    models: [
      { id: 'gpt-5', name: 'GPT-5', description: 'Most advanced model' },
      { id: 'gpt-5-mini', name: 'GPT-5 Mini', description: 'Fast and efficient' },
      { id: 'o3', name: 'O3', description: 'Advanced reasoning' },
      { id: 'o4-mini', name: 'O4 Mini', description: 'Fast reasoning' },
      { id: 'gpt-4.1', name: 'GPT-4.1', description: 'Reliable all-rounder' },
      { id: 'gpt-4o', name: 'GPT-4o', description: 'Multimodal capable' },
    ],
  },
  anthropic: {
    id: 'anthropic',
    name: 'Anthropic',
    models: [
      { id: 'claude-opus-4.5', name: 'Claude Opus 4.5', description: 'Most intelligent' },
      { id: 'claude-sonnet-4.5', name: 'Claude Sonnet 4.5', description: 'Best for coding' },
      { id: 'claude-haiku-4.5', name: 'Claude Haiku 4.5', description: 'Fast responses' },
      { id: 'claude-opus-4', name: 'Claude Opus 4', description: 'Previous flagship' },
      { id: 'claude-sonnet-4', name: 'Claude Sonnet 4', description: 'Balanced performance' },
    ],
  },
  google: {
    id: 'google',
    name: 'Google AI',
    models: [
      { id: 'gemini-3-pro', name: 'Gemini 3 Pro', description: 'Most powerful' },
      { id: 'gemini-3-deep-think', name: 'Gemini 3 Deep Think', description: 'Complex reasoning' },
      { id: 'gemini-3-flash', name: 'Gemini 3 Flash', description: 'Fast responses' },
      { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', description: 'Excellent coding' },
      { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', description: 'Cost efficient' },
    ],
  },
  mistral: {
    id: 'mistral',
    name: 'Mistral AI',
    models: [
      { id: 'mistral-large-3', name: 'Mistral Large 3', description: 'Most capable' },
      { id: 'codestral-25.01', name: 'Codestral 25.01', description: 'Best for code' },
      { id: 'magistral-medium', name: 'Magistral Medium', description: 'Chain-of-thought' },
      { id: 'ministral-14b', name: 'Ministral 14B', description: 'Efficient edge model' },
      { id: 'devstral-2', name: 'Devstral 2', description: 'Developer focused' },
    ],
  },
  openrouter: {
    id: 'openrouter',
    name: 'OpenRouter',
    models: [
      { id: 'openrouter/auto', name: 'Auto (Best)', description: 'Auto-select best' },
      { id: 'anthropic/claude-opus-4.5', name: 'Claude Opus 4.5', description: 'via OpenRouter' },
      { id: 'openai/gpt-5', name: 'GPT-5', description: 'via OpenRouter' },
      { id: 'google/gemini-3-pro', name: 'Gemini 3 Pro', description: 'via OpenRouter' },
    ],
  },
  ollama: {
    id: 'ollama',
    name: 'Ollama',
    models: [
      { id: 'llama3.3:70b', name: 'Llama 3.3 70B', description: 'Local, powerful' },
      { id: 'llama3.2:latest', name: 'Llama 3.2', description: 'Local, fast' },
      { id: 'qwen2.5:72b', name: 'Qwen 2.5 72B', description: 'Local, multilingual' },
      { id: 'deepseek-coder-v2', name: 'DeepSeek Coder V2', description: 'Local, coding' },
    ],
  },
} as const;

// =============================================================================
// DEFAULTS
// =============================================================================
export const DEFAULTS = {
  LLM_PROVIDER: 'openai',
  LLM_MODEL: 'gpt-5',
  TEMPERATURE: 0.7,
  MAX_TOKENS: 4096,
} as const;

// =============================================================================
// UI CONSTANTS
// =============================================================================
export const UI = {
  SIDEBAR_WIDTH: 280,
  SIDEBAR_COLLAPSED_WIDTH: 60,
  MAX_MESSAGE_LENGTH: 32000,
} as const;
