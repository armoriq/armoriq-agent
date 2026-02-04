'use client';

import { API_CONFIG, ENDPOINTS } from './constants';
import type {
  TokenPair,
  User,
  Conversation,
  Message,
  LLMConfig,
  LLMProvider,
  MCPConfig,
  MCPStatus,
  IntentPlan,
  StreamChunk,
  ChatRequest,
} from './types';

// =============================================================================
// TOKEN MANAGEMENT
// =============================================================================
const TOKEN_KEY = 'armoriq_tokens';

export function getTokens(): TokenPair | null {
  if (typeof window === 'undefined') return null;
  const stored = localStorage.getItem(TOKEN_KEY);
  if (!stored) return null;
  try {
    return JSON.parse(stored) as TokenPair;
  } catch {
    return null;
  }
}

export function setTokens(tokens: TokenPair): void {
  localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function getAccessToken(): string | null {
  return getTokens()?.access_token ?? null;
}

// =============================================================================
// API CLIENT
// =============================================================================
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_CONFIG.BASE_URL}${API_CONFIG.API_PREFIX}${endpoint}`;
  const token = getAccessToken();

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// =============================================================================
// AUTH API
// =============================================================================
export const authApi = {
  async register(email: string, password: string, name: string): Promise<TokenPair> {
    const tokens = await apiRequest<TokenPair>(ENDPOINTS.AUTH.REGISTER, {
      method: 'POST',
      body: JSON.stringify({ email, password, name }),
    });
    setTokens(tokens);
    return tokens;
  },

  async login(email: string, password: string): Promise<TokenPair> {
    const tokens = await apiRequest<TokenPair>(ENDPOINTS.AUTH.LOGIN, {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setTokens(tokens);
    return tokens;
  },

  async getGoogleAuthUrl(): Promise<{ auth_url: string }> {
    return apiRequest(ENDPOINTS.AUTH.GOOGLE);
  },

  async refresh(): Promise<TokenPair> {
    const currentTokens = getTokens();
    if (!currentTokens) throw new Error('No refresh token');

    const tokens = await apiRequest<TokenPair>(ENDPOINTS.AUTH.REFRESH, {
      method: 'POST',
      body: JSON.stringify({ refresh_token: currentTokens.refresh_token }),
    });
    setTokens(tokens);
    return tokens;
  },

  async me(): Promise<User> {
    return apiRequest(ENDPOINTS.AUTH.ME);
  },

  async logout(): Promise<void> {
    try {
      await apiRequest(ENDPOINTS.AUTH.LOGOUT, { method: 'POST' });
    } finally {
      clearTokens();
    }
  },
};

// =============================================================================
// CHAT API
// =============================================================================
export const chatApi = {
  async getConversations(): Promise<Conversation[]> {
    return apiRequest(ENDPOINTS.CHAT.CONVERSATIONS);
  },

  async getHistory(conversationId: string): Promise<Message[]> {
    return apiRequest(ENDPOINTS.CHAT.HISTORY(conversationId));
  },

  async deleteConversation(conversationId: string): Promise<void> {
    await apiRequest(ENDPOINTS.CHAT.CONVERSATION(conversationId), {
      method: 'DELETE',
    });
  },

  async *streamChat(request: ChatRequest): AsyncGenerator<StreamChunk> {
    const url = `${API_CONFIG.BASE_URL}${API_CONFIG.API_PREFIX}${ENDPOINTS.CHAT.STREAM}`;
    const token = getAccessToken();

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Stream failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error('No reader available');

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6)) as StreamChunk;
            yield data;
            if (data.type === 'done' || data.type === 'error') {
              return;
            }
          } catch {
            // Skip invalid JSON
          }
        }
      }
    }
  },
};

// =============================================================================
// LLM API
// =============================================================================
export const llmApi = {
  async getProviders(): Promise<{ providers: LLMProvider[] }> {
    return apiRequest(ENDPOINTS.LLM.PROVIDERS);
  },

  async getConfigs(): Promise<LLMConfig[]> {
    return apiRequest(ENDPOINTS.LLM.CONFIGS);
  },

  async addConfig(provider: string, apiKey: string, isDefault = false): Promise<LLMConfig> {
    return apiRequest(ENDPOINTS.LLM.CONFIG, {
      method: 'POST',
      body: JSON.stringify({ provider, api_key: apiKey, is_default: isDefault }),
    });
  },
};

// =============================================================================
// MCP API
// =============================================================================
export const mcpApi = {
  async list(): Promise<MCPConfig[]> {
    return apiRequest(ENDPOINTS.MCP.LIST);
  },

  async getStatus(): Promise<MCPStatus[]> {
    return apiRequest(ENDPOINTS.MCP.STATUS);
  },

  async add(config: Partial<MCPConfig>): Promise<MCPConfig> {
    return apiRequest(ENDPOINTS.MCP.ADD, {
      method: 'POST',
      body: JSON.stringify(config),
    });
  },

  async reconnect(mcpId: string): Promise<{ status: string }> {
    return apiRequest(ENDPOINTS.MCP.RECONNECT(mcpId), { method: 'POST' });
  },

  async delete(mcpId: string): Promise<void> {
    await apiRequest(ENDPOINTS.MCP.DELETE(mcpId), { method: 'DELETE' });
  },
};

// =============================================================================
// PLANS API
// =============================================================================
export const plansApi = {
  async list(): Promise<IntentPlan[]> {
    return apiRequest(ENDPOINTS.PLANS.LIST);
  },

  async get(planId: string): Promise<IntentPlan> {
    return apiRequest(ENDPOINTS.PLANS.DETAIL(planId));
  },
};
