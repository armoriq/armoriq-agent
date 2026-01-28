'use client';

import { cn } from '@/lib/utils';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Copy, Check, User, Wrench } from 'lucide-react';
import { useState } from 'react';
import type { Message as MessageType } from '@/lib/types';

// Provider icon components
const ProviderIcons: Record<string, React.FC<{ className?: string }>> = {
  openai: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855l-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365l2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z"/>
    </svg>
  ),
  anthropic: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M17.304 3.541h-3.467l6.475 16.918h3.468l-6.476-16.918zm-10.608 0L.22 20.459h3.521l1.294-3.547h6.609l1.294 3.547h3.52L10.01 3.541H6.696zm-.262 10.8l2.302-6.313 2.302 6.313H6.434z"/>
    </svg>
  ),
  google: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"/>
    </svg>
  ),
  mistral: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <rect x="0" y="0" width="6" height="6"/>
      <rect x="18" y="0" width="6" height="6"/>
      <rect x="0" y="6" width="6" height="6"/>
      <rect x="6" y="6" width="6" height="6"/>
      <rect x="18" y="6" width="6" height="6"/>
      <rect x="0" y="12" width="6" height="6"/>
      <rect x="6" y="12" width="6" height="6"/>
      <rect x="12" y="12" width="6" height="6"/>
      <rect x="18" y="12" width="6" height="6"/>
      <rect x="0" y="18" width="6" height="6"/>
      <rect x="18" y="18" width="6" height="6"/>
    </svg>
  ),
  openrouter: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 18c-4.411 0-8-3.589-8-8s3.589-8 8-8 8 3.589 8 8-3.589 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/>
    </svg>
  ),
  ollama: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-2-10c0 1.1-.9 2-2 2s-2-.9-2-2 .9-2 2-2 2 .9 2 2zm8 0c0 1.1-.9 2-2 2s-2-.9-2-2 .9-2 2-2 2 .9 2 2zm-4 5c-2.21 0-4 1.79-4 4h8c0-2.21-1.79-4-4-4z"/>
    </svg>
  ),
};

const getProviderColor = (provider: string): string => {
  const colors: Record<string, string> = {
    openai: 'bg-[#10a37f]',
    anthropic: 'bg-[#d4a27f]',
    google: 'bg-[#4285f4]',
    mistral: 'bg-[#f7931a]',
    openrouter: 'bg-gradient-to-br from-violet-500 to-purple-600',
    ollama: 'bg-gray-700',
  };
  return colors[provider] || 'bg-gradient-to-br from-violet-500 to-purple-600';
};

interface ChatMessageProps {
  message: MessageType;
  isStreaming?: boolean;
  provider?: string;
}

export function ChatMessage({ message, isStreaming, provider = 'openai' }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';
  const isTool = message.role === 'tool';

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const ProviderIcon = ProviderIcons[provider] || ProviderIcons.openai;

  return (
    <div
      className={cn(
        'group relative flex gap-4 px-4 py-5',
        isUser ? 'bg-transparent' : 'bg-muted/20'
      )}
    >
      {/* Avatar */}
      <Avatar className="h-8 w-8 shrink-0 shadow-sm">
        <AvatarFallback
          className={cn(
            'text-white',
            isUser
              ? 'bg-gradient-to-br from-blue-500 to-blue-600'
              : isTool
              ? 'bg-amber-500'
              : getProviderColor(provider)
          )}
        >
          {isUser ? (
            <User className="h-4 w-4" />
          ) : isTool ? (
            <Wrench className="h-4 w-4" />
          ) : (
            <ProviderIcon className="h-4 w-4" />
          )}
        </AvatarFallback>
      </Avatar>

      {/* Content */}
      <div className="flex-1 space-y-1.5 overflow-hidden min-w-0">
        {/* Role label */}
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">
            {isUser ? 'You' : isTool ? 'Tool' : provider.charAt(0).toUpperCase() + provider.slice(1)}
          </span>
          {isStreaming && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-500" />
              Generating...
            </span>
          )}
        </div>

        {/* Message content */}
        <div className="text-[15px] leading-relaxed text-foreground/90">
          {message.content ? (
            <div className="whitespace-pre-wrap break-words">
              {message.content}
            </div>
          ) : isStreaming ? (
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
            </div>
          ) : null}
        </div>

        {/* Tool calls indicator */}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2">
            {message.tool_calls.map((tc, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-300"
              >
                <Wrench className="h-3 w-3" />
                {tc.name}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      {!isUser && !isStreaming && message.content && (
        <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
            onClick={copyToClipboard}
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-green-500" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>
      )}
    </div>
  );
}

// Streaming message component
interface StreamingMessageProps {
  content: string;
  toolName?: string;
  isComplete?: boolean;
  provider?: string;
}

export function StreamingMessage({ content, toolName, isComplete, provider = 'openai' }: StreamingMessageProps) {
  const ProviderIcon = ProviderIcons[provider] || ProviderIcons.openai;

  return (
    <div className="group relative flex gap-4 bg-muted/20 px-4 py-5">
      <Avatar className="h-8 w-8 shrink-0 shadow-sm">
        <AvatarFallback className={cn('text-white', getProviderColor(provider))}>
          <ProviderIcon className="h-4 w-4" />
        </AvatarFallback>
      </Avatar>

      <div className="flex-1 space-y-1.5 overflow-hidden min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">
            {provider.charAt(0).toUpperCase() + provider.slice(1)}
          </span>
          {!isComplete && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-500" />
              {toolName ? `Executing ${toolName}...` : 'Generating...'}
            </span>
          )}
        </div>

        <div className="text-[15px] leading-relaxed text-foreground/90">
          {content ? (
            <div className="whitespace-pre-wrap break-words">
              {content}
              {!isComplete && (
                <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-foreground/60" />
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
            </div>
          )}
        </div>

        {toolName && (
          <div className="pt-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
              <Wrench className="h-3 w-3 animate-spin" />
              {toolName}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
