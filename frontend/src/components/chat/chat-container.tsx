'use client';

import { useRef, useEffect, useState, useCallback } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChatMessage, StreamingMessage } from './chat-message';
import { ChatInput } from './chat-input';
import { ModelSelector } from './model-selector';
import { ChatSidebar } from './chat-sidebar';
import { chatApi, llmApi } from '@/lib/api';
import { DEFAULTS } from '@/lib/constants';
import { cn } from '@/lib/utils';
import type { Message, Conversation, StreamChunk } from '@/lib/types';
import { Sparkles, ArrowDown } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ChatContainerProps {
  initialConversations?: Conversation[];
  initialMessages?: Message[];
  initialConversationId?: string;
}

export function ChatContainer({
  initialConversations = [],
  initialMessages = [],
  initialConversationId,
}: ChatContainerProps) {
  // State
  const [conversations, setConversations] = useState<Conversation[]>(initialConversations);
  const [currentConversationId, setCurrentConversationId] = useState<string | undefined>(
    initialConversationId
  );
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [isLoading, setIsLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [streamingToolName, setStreamingToolName] = useState<string | undefined>();
  const [provider, setProvider] = useState<string>(DEFAULTS.LLM_PROVIDER);
  const [model, setModel] = useState<string>(DEFAULTS.LLM_MODEL);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [configuredProviders, setConfiguredProviders] = useState<string[]>([]);

  // Refs
  const scrollRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Fetch configured providers on mount
  useEffect(() => {
    const fetchConfigs = async () => {
      try {
        const configs = await llmApi.getConfigs();
        setConfiguredProviders(configs.map(c => c.provider));
        // Set default to first configured provider if available
        if (configs.length > 0) {
          const defaultConfig = configs.find(c => c.is_default) || configs[0];
          setProvider(defaultConfig.provider);
        }
      } catch (error) {
        console.error('Failed to fetch LLM configs:', error);
      }
    };
    fetchConfigs();
  }, []);

  // Scroll to bottom
  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  }, []);

  // Auto-scroll when new messages arrive
  useEffect(() => {
    if (isLoading || streamingContent) {
      scrollToBottom();
    }
  }, [messages, streamingContent, isLoading, scrollToBottom]);

  // Handle scroll to detect if we should show scroll button
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const target = e.target as HTMLDivElement;
    const isNearBottom = target.scrollHeight - target.scrollTop - target.clientHeight < 100;
    setShowScrollButton(!isNearBottom);
  }, []);

  // Send message
  const handleSend = async (content: string) => {
    if (!content.trim() || isLoading) return;

    // Add user message immediately
    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setStreamingContent('');
    setStreamingToolName(undefined);

    // Use ref to accumulate streaming content (avoids stale closure issues)
    let accumulatedContent = '';
    let newConversationId = currentConversationId;

    try {
      // Stream response
      for await (const chunk of chatApi.streamChat({
        conversation_id: currentConversationId,
        message: content,
        llm_provider: provider,
        llm_model: model,
      })) {
        switch (chunk.type) {
          case 'content':
            accumulatedContent += chunk.content || '';
            setStreamingContent(accumulatedContent);
            break;
          case 'tool_call':
            setStreamingToolName(chunk.tool_name);
            break;
          case 'tool_result':
            setStreamingToolName(undefined);
            break;
          case 'plan_captured':
            // Could show a notification
            break;
          case 'done':
            if (chunk.conversation_id) {
              newConversationId = chunk.conversation_id;
            }
            break;
          case 'error':
            throw new Error(chunk.message || 'Stream error');
        }
      }

      // Add assistant message with accumulated content
      if (accumulatedContent) {
        const assistantMessage: Message = {
          id: `temp-${Date.now()}-assistant`,
          role: 'assistant',
          content: accumulatedContent,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
      }

      // Update conversation ID if new
      if (newConversationId && newConversationId !== currentConversationId) {
        setCurrentConversationId(newConversationId);
        // Add to conversations list
        const newConv: Conversation = {
          id: newConversationId,
          title: content.slice(0, 50),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        setConversations((prev) => [newConv, ...prev]);
      }
    } catch (error) {
      console.error('Chat error:', error);
      // Add error message
      const errorMessage: Message = {
        id: `temp-${Date.now()}-error`,
        role: 'assistant',
        content: `Sorry, an error occurred: ${error instanceof Error ? error.message : 'Unknown error'}`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setStreamingContent('');
      setStreamingToolName(undefined);
    }
  };

  // Stop streaming
  const handleStop = () => {
    abortControllerRef.current?.abort();
    setIsLoading(false);
    setStreamingContent('');
    setStreamingToolName(undefined);
  };

  // New chat
  const handleNewChat = () => {
    setCurrentConversationId(undefined);
    setMessages([]);
  };

  // Select conversation
  const handleSelectConversation = async (id: string) => {
    if (id === currentConversationId) return;

    setCurrentConversationId(id);
    try {
      const history = await chatApi.getHistory(id);
      setMessages(history);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  // Delete conversation
  const handleDeleteConversation = async (id: string) => {
    try {
      await chatApi.deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (id === currentConversationId) {
        handleNewChat();
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  // Select model
  const handleModelSelect = (newProvider: string, newModel: string) => {
    setProvider(newProvider);
    setModel(newModel);
  };

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <ChatSidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onNewChat={handleNewChat}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={handleDeleteConversation}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Chat Area */}
      <div className="flex flex-1 flex-col">
        {/* Header */}
        <header className="flex h-14 items-center justify-between border-b px-4 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <ModelSelector
            provider={provider}
            model={model}
            onSelect={handleModelSelect}
            configuredProviders={configuredProviders}
          />
        </header>

        {/* Messages */}
        <div className="relative flex-1 overflow-hidden">
          <ScrollArea
            className="h-full"
            onScroll={handleScroll}
            ref={scrollRef}
          >
            <div className="mx-auto max-w-3xl">
              {messages.length === 0 && !isLoading ? (
                <EmptyState onSuggestionClick={handleSend} />
              ) : (
                <div className="pb-32 pt-4">
                  {messages.map((message) => (
                    <ChatMessage
                      key={message.id}
                      message={message}
                      provider={provider}
                    />
                  ))}
                  {isLoading && (
                    <StreamingMessage
                      content={streamingContent}
                      toolName={streamingToolName}
                      provider={provider}
                    />
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>
          </ScrollArea>

          {/* Scroll to bottom button */}
          {showScrollButton && (
            <Button
              size="icon"
              variant="secondary"
              className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full shadow-lg"
              onClick={() => scrollToBottom()}
            >
              <ArrowDown className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* Input */}
        <div className="border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 py-4">
          <ChatInput
            onSend={handleSend}
            onStop={handleStop}
            isLoading={isLoading}
          />
          <p className="mt-2 text-center text-xs text-muted-foreground">
            ArmorIQ verifies all tool executions for security
          </p>
        </div>
      </div>
    </div>
  );
}

// Empty state with suggestions
function EmptyState({ onSuggestionClick }: { onSuggestionClick: (text: string) => void }) {
  const suggestions = [
    'Explain how ArmorIQ protects my AI agent',
    'What tools are connected to my agent?',
    'Help me analyze a document',
    'Search the web for recent AI news',
  ];

  return (
    <div className="flex h-full flex-col items-center justify-center px-4 py-16">
      <div className="mb-8 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 shadow-lg">
        <Sparkles className="h-8 w-8 text-white" />
      </div>
      <h1 className="mb-2 text-2xl font-semibold text-foreground">
        How can I help you today?
      </h1>
      <p className="mb-8 text-muted-foreground">
        Start a conversation or try one of these suggestions
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {suggestions.map((suggestion, i) => (
          <button
            key={i}
            onClick={() => onSuggestionClick(suggestion)}
            className="rounded-lg border bg-card p-4 text-left text-sm transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}
