'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { plansApi } from '@/lib/api';
import { ROUTES } from '@/lib/constants';
import type { IntentPlan } from '@/lib/types';
import { ArrowLeft, Shield, CheckCircle, Clock, XCircle, Loader2 } from 'lucide-react';

export default function PlansPage() {
  const [plans, setPlans] = useState<IntentPlan[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadPlans();
  }, []);

  const loadPlans = async () => {
    try {
      const data = await plansApi.list();
      setPlans(data);
    } catch (err) {
      console.error('Failed to load plans:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'executing':
        return <Loader2 className="h-4 w-4 animate-spin text-yellow-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-destructive" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500/10 text-green-600 border-green-500/20';
      case 'executing':
        return 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20';
      case 'failed':
        return 'bg-destructive/10 text-destructive border-destructive/20';
      default:
        return 'bg-muted text-muted-foreground';
    }
  };

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
            <h1 className="font-semibold">Intent Plans</h1>
            <p className="text-xs text-muted-foreground">ArmorIQ captured execution plans</p>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto max-w-4xl p-4">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : plans.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-16">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                <Shield className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="mb-1 font-medium">No intent plans yet</h3>
              <p className="text-center text-sm text-muted-foreground">
                When you use tools in chat, ArmorIQ will capture
                <br />
                execution plans here for audit
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {plans.map((plan) => (
              <Card key={plan.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Shield className="h-4 w-4 text-primary" />
                      <CardTitle className="text-sm font-medium">
                        Plan {plan.id.slice(0, 8)}...
                      </CardTitle>
                    </div>
                    <Badge variant="outline" className={getStatusColor(plan.status)}>
                      {getStatusIcon(plan.status)}
                      <span className="ml-1 capitalize">{plan.status}</span>
                    </Badge>
                  </div>
                  <CardDescription>
                    {new Date(plan.created_at).toLocaleString()}
                    {plan.plan_hash && (
                      <span className="ml-2 font-mono text-xs">
                        Hash: {plan.plan_hash.slice(0, 12)}...
                      </span>
                    )}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground">Steps:</p>
                    <div className="flex flex-wrap gap-1">
                      {plan.plan_data.steps.map((step, i) => (
                        <Badge key={i} variant="secondary" className="text-xs">
                          {step.mcp}: {step.action}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
