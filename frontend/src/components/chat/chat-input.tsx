'use client';

import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { ArrowUp, Paperclip, Square } from 'lucide-react';
import { UI } from '@/lib/constants';

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop?: () => void;
  isLoading?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  onStop,
  isLoading,
  disabled,
  placeholder = 'Message ArmorIQ...',
}: ChatInputProps) {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [message]);

  const handleSubmit = () => {
    const trimmed = message.trim();
    if (!trimmed || isLoading || disabled) return;
    if (trimmed.length > UI.MAX_MESSAGE_LENGTH) return;

    onSend(trimmed);
    setMessage('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSend = message.trim().length > 0 && !disabled;

  return (
    <div className="relative mx-auto w-full max-w-3xl px-4">
      <div
        className={cn(
          'relative flex items-end gap-2 rounded-2xl border bg-background/80 backdrop-blur-sm shadow-lg transition-all',
          'focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2',
          disabled && 'opacity-50'
        )}
      >
        {/* Attachment button (placeholder) */}
        <Button
          variant="ghost"
          size="icon"
          className="mb-2 ml-2 h-8 w-8 shrink-0 text-muted-foreground hover:text-foreground"
          disabled={disabled || isLoading}
        >
          <Paperclip className="h-4 w-4" />
        </Button>

        {/* Input */}
        <Textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled || isLoading}
          rows={1}
          className={cn(
            'min-h-[44px] max-h-[200px] flex-1 resize-none border-0 bg-transparent py-3',
            'focus-visible:ring-0 focus-visible:ring-offset-0',
            'placeholder:text-muted-foreground/60'
          )}
        />

        {/* Send/Stop button */}
        <div className="mb-2 mr-2">
          {isLoading ? (
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 rounded-full bg-destructive/10 text-destructive hover:bg-destructive/20"
              onClick={onStop}
            >
              <Square className="h-3.5 w-3.5 fill-current" />
            </Button>
          ) : (
            <Button
              size="icon"
              className={cn(
                'h-8 w-8 rounded-full transition-all',
                canSend
                  ? 'bg-primary text-primary-foreground shadow-md hover:bg-primary/90'
                  : 'bg-muted text-muted-foreground cursor-not-allowed'
              )}
              disabled={!canSend}
              onClick={handleSubmit}
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Character count */}
      {message.length > UI.MAX_MESSAGE_LENGTH * 0.8 && (
        <div className="mt-1 text-right text-xs text-muted-foreground">
          <span className={message.length > UI.MAX_MESSAGE_LENGTH ? 'text-destructive' : ''}>
            {message.length}
          </span>
          /{UI.MAX_MESSAGE_LENGTH}
        </div>
      )}
    </div>
  );
}
