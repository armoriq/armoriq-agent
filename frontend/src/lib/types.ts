// =============================================================================
// USER TYPES
// =============================================================================
export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url?: string;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// =============================================================================
// CHAT TYPES
// =============================================================================
export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  tool_calls?: ToolCall[];
  tool_results?: ToolResult[];
  created_at: string;
}

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
}

export interface ToolResult {
  tool_call_id: string;
  result: unknown;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatRequest {
  conversation_id?: string;
  message: string;
  llm_provider: string;
  llm_model: string;
}

// =============================================================================
// STREAM TYPES
// =============================================================================
export interface StreamChunk {
  type: 'content' | 'tool_call' | 'tool_result' | 'plan_captured' | 'done' | 'error' | 'info';
  content?: string;
  tool_name?: string;
  result?: unknown;
  plan_id?: string;
  message?: string;
  conversation_id?: string;
}

// =============================================================================
// LLM TYPES
// =============================================================================
export interface LLMConfig {
  id: string;
  provider: string;
  is_default: boolean;
  settings?: Record<string, unknown>;
  created_at: string;
}

export interface LLMProvider {
  id: string;
  name: string;
  models: string[];
  configured: boolean;
}

// =============================================================================
// MCP TYPES
// =============================================================================
export interface MCPConfig {
  id: string;
  name: string;
  connection_type: 'stdio' | 'sse' | 'http' | 'websocket';
  url?: string;
  command?: string;
  args?: string[];
  enabled: boolean;
  idle_timeout_seconds: number;
  created_at: string;
}

export interface MCPStatus {
  id: string;
  name: string;
  status: 'disconnected' | 'connecting' | 'connected' | 'error';
  last_used?: string;
  tool_count: number;
  idle_timeout_seconds: number;
  error_message?: string;
}

export interface MCPTool {
  name: string;
  description?: string;
  input_schema?: Record<string, unknown>;
}

// =============================================================================
// PLAN TYPES
// =============================================================================
export interface IntentPlan {
  id: string;
  conversation_id?: string;
  plan_hash?: string;
  plan_data: {
    steps: PlanStep[];
  };
  status: 'pending' | 'executing' | 'completed' | 'failed';
  created_at: string;
  completed_at?: string;
}

export interface PlanStep {
  action: string;
  mcp: string;
  description?: string;
  params?: Record<string, unknown>;
}
