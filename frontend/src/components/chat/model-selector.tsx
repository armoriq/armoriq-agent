'use client';

import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { LLM_PROVIDERS } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { ChevronDown, Check, Sparkles } from 'lucide-react';
import { ProviderIcon } from '@/components/icons/provider-icons';

interface ModelSelectorProps {
  provider: string;
  model: string;
  onSelect: (provider: string, model: string) => void;
  configuredProviders?: string[];
  compact?: boolean;
}

export function ModelSelector({
  provider,
  model,
  onSelect,
  configuredProviders = [],
  compact = false,
}: ModelSelectorProps) {
  const currentProvider = LLM_PROVIDERS[provider as keyof typeof LLM_PROVIDERS];
  const currentModel = currentProvider?.models.find((m) => m.id === model);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className={cn(
            'gap-2 font-medium',
            compact ? 'h-8 px-2 text-sm' : 'h-9 px-3'
          )}
        >
          <span className="flex items-center gap-2">
            <ProviderIcon provider={provider} className="h-4 w-4" />
            <span className="text-foreground">
              {compact ? currentModel?.name || model : `${currentProvider?.name || provider} / ${currentModel?.name || model}`}
            </span>
          </span>
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-80">
        {Object.entries(LLM_PROVIDERS).map(([providerId, providerData]) => (
          <div key={providerId}>
            <DropdownMenuLabel className="flex items-center gap-2 text-xs font-normal text-muted-foreground">
              <ProviderIcon provider={providerId} className="h-3.5 w-3.5" />
              <span>{providerData.name}</span>
              {!configuredProviders.includes(providerId) && providerId !== 'ollama' && (
                <span className="ml-auto rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                  Not configured
                </span>
              )}
            </DropdownMenuLabel>
            {providerData.models.map((m) => (
              <DropdownMenuItem
                key={m.id}
                onClick={() => onSelect(providerId, m.id)}
                disabled={!configuredProviders.includes(providerId) && providerId !== 'ollama'}
                className="cursor-pointer pl-8"
              >
                <div className="flex flex-1 items-center justify-between">
                  <div className="flex flex-col">
                    <span className="font-medium">{m.name}</span>
                    {m.description && (
                      <span className="text-xs text-muted-foreground">
                        {m.description}
                      </span>
                    )}
                  </div>
                  {providerId === provider && m.id === model && (
                    <Check className="h-4 w-4 text-primary" />
                  )}
                </div>
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// Simple model badge for display only
interface ModelBadgeProps {
  provider: string;
  model: string;
}

export function ModelBadge({ provider, model }: ModelBadgeProps) {
  const providerData = LLM_PROVIDERS[provider as keyof typeof LLM_PROVIDERS];
  const modelData = providerData?.models.find((m) => m.id === model);

  return (
    <div className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-medium">
      <ProviderIcon provider={provider} className="h-3 w-3" />
      <span>{providerData?.name || provider}</span>
      <span className="text-muted-foreground">/</span>
      <span className="text-foreground">{modelData?.name || model}</span>
    </div>
  );
}
