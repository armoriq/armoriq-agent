'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { llmApi } from '@/lib/api';
import { LLM_PROVIDERS, ROUTES } from '@/lib/constants';
import type { LLMConfig } from '@/lib/types';
import { ArrowLeft, Check, Eye, EyeOff, Loader2, Plus, Trash2 } from 'lucide-react';
import { ProviderIcon } from '@/components/icons/provider-icons';

export default function LLMSettingsPage() {
  const [configs, setConfigs] = useState<LLMConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [addingProvider, setAddingProvider] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  // Load configs
  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    try {
      const data = await llmApi.getConfigs();
      setConfigs(data);
    } catch (err) {
      console.error('Failed to load configs:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddConfig = async (providerId: string) => {
    if (!apiKey.trim()) return;
    setError('');
    setIsSaving(true);

    try {
      const newConfig = await llmApi.addConfig(providerId, apiKey, configs.length === 0);
      setConfigs((prev) => [...prev, newConfig]);
      setAddingProvider(null);
      setApiKey('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add configuration');
    } finally {
      setIsSaving(false);
    }
  };

  const configuredProviders = configs.map((c) => c.provider);

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20">
      {/* Header */}
      <header className="border-b bg-background/80 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-4xl items-center gap-4 px-4">
          <Link href={ROUTES.HOME}>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="font-semibold">LLM Providers</h1>
            <p className="text-xs text-muted-foreground">Configure your API keys</p>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto max-w-4xl p-4">
        {error && (
          <div className="mb-4 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          {Object.entries(LLM_PROVIDERS).map(([providerId, provider]) => {
            const isConfigured = configuredProviders.includes(providerId);
            const isAdding = addingProvider === providerId;

            return (
              <Card
                key={providerId}
                className={`transition-all ${isConfigured ? 'border-primary/50' : ''}`}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                        <ProviderIcon provider={providerId} className="h-5 w-5" />
                      </div>
                      <div>
                        <CardTitle className="text-lg">{provider.name}</CardTitle>
                        <CardDescription>
                          {provider.models.length} models available
                        </CardDescription>
                      </div>
                    </div>
                    {isConfigured && (
                      <Badge variant="secondary" className="gap-1">
                        <Check className="h-3 w-3" />
                        Configured
                      </Badge>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  {isAdding ? (
                    <div className="space-y-3">
                      <div className="relative">
                        <Input
                          type={showApiKey ? 'text' : 'password'}
                          placeholder="Enter API key"
                          value={apiKey}
                          onChange={(e) => setApiKey(e.target.value)}
                          disabled={isSaving}
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2"
                          onClick={() => setShowApiKey(!showApiKey)}
                        >
                          {showApiKey ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={() => handleAddConfig(providerId)}
                          disabled={!apiKey.trim() || isSaving}
                        >
                          {isSaving ? (
                            <>
                              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                              Validating...
                            </>
                          ) : (
                            'Save'
                          )}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setAddingProvider(null);
                            setApiKey('');
                          }}
                          disabled={isSaving}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-1">
                      {provider.models.slice(0, 3).map((m) => (
                        <Badge key={m.id} variant="outline" className="text-xs">
                          {m.name}
                        </Badge>
                      ))}
                      {provider.models.length > 3 && (
                        <Badge variant="outline" className="text-xs">
                          +{provider.models.length - 3} more
                        </Badge>
                      )}
                    </div>
                  )}
                  {!isAdding && !isConfigured && providerId !== 'ollama' && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-3 w-full gap-1"
                      onClick={() => setAddingProvider(providerId)}
                    >
                      <Plus className="h-3 w-3" />
                      Add API Key
                    </Button>
                  )}
                  {providerId === 'ollama' && !isConfigured && (
                    <p className="mt-3 text-xs text-muted-foreground">
                      Ollama runs locally. No API key needed.
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </main>
    </div>
  );
}
