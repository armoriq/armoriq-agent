'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { mcpApi } from '@/lib/api';
import { ROUTES } from '@/lib/constants';
import type { MCPStatus } from '@/lib/types';
import { ArrowLeft, Loader2, Plus, Plug, RefreshCw, Trash2, AlertCircle, CheckCircle, XCircle, Wrench } from 'lucide-react';

export default function MCPSettingsPage() {
  const [mcpList, setMcpList] = useState<MCPStatus[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [reconnectingId, setReconnectingId] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState('');
  const [connectionType, setConnectionType] = useState('stdio');
  const [url, setUrl] = useState('');
  const [command, setCommand] = useState('');
  const [args, setArgs] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadMCPs();
  }, []);

  const loadMCPs = async () => {
    try {
      const data = await mcpApi.getStatus();
      setMcpList(data);
    } catch (err) {
      console.error('Failed to load MCPs:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAdd = async () => {
    setError('');
    setIsSaving(true);

    try {
      await mcpApi.add({
        name,
        connection_type: connectionType as 'stdio' | 'sse' | 'http',
        url: connectionType !== 'stdio' ? url : undefined,
        command: connectionType === 'stdio' ? command : undefined,
        args: connectionType === 'stdio' && args ? args.split(' ') : undefined,
        idle_timeout_seconds: 300,
      });
      setShowAddDialog(false);
      resetForm();
      loadMCPs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add MCP');
    } finally {
      setIsSaving(false);
    }
  };

  const handleReconnect = async (id: string) => {
    setReconnectingId(id);
    try {
      await mcpApi.reconnect(id);
      loadMCPs();
    } catch (err) {
      console.error('Reconnect failed:', err);
    } finally {
      setReconnectingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await mcpApi.delete(id);
      setMcpList((prev) => prev.filter((m) => m.id !== id));
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const resetForm = () => {
    setName('');
    setConnectionType('stdio');
    setUrl('');
    setCommand('');
    setArgs('');
    setError('');
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'connected':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'connecting':
        return <Loader2 className="h-4 w-4 animate-spin text-yellow-500" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-destructive" />;
      default:
        return <AlertCircle className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected':
        return 'bg-green-500/10 text-green-600 border-green-500/20';
      case 'connecting':
        return 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20';
      case 'error':
        return 'bg-destructive/10 text-destructive border-destructive/20';
      default:
        return 'bg-muted text-muted-foreground';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20">
      {/* Header */}
      <header className="border-b bg-background/80 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-4xl items-center justify-between px-4">
          <div className="flex items-center gap-4">
            <Link href={ROUTES.HOME}>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <div>
              <h1 className="font-semibold">MCP Servers</h1>
              <p className="text-xs text-muted-foreground">Manage tool connections</p>
            </div>
          </div>
          <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
            <DialogTrigger asChild>
              <Button size="sm" className="gap-1">
                <Plus className="h-4 w-4" />
                Add MCP
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add MCP Server</DialogTitle>
                <DialogDescription>
                  Connect to an MCP server for additional tools
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                {error && (
                  <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
                    {error}
                  </div>
                )}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Name</label>
                  <Input
                    placeholder="My MCP Server"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Connection Type</label>
                  <Select value={connectionType} onValueChange={setConnectionType}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="stdio">Stdio (Local)</SelectItem>
                      <SelectItem value="sse">SSE (Remote)</SelectItem>
                      <SelectItem value="http">Direct HTTP (FastMCP)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {connectionType === 'stdio' ? (
                  <>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Command</label>
                      <Input
                        placeholder="npx -y @modelcontextprotocol/server-filesystem"
                        value={command}
                        onChange={(e) => setCommand(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Arguments (space-separated)</label>
                      <Input
                        placeholder="/path/to/directory"
                        value={args}
                        onChange={(e) => setArgs(e.target.value)}
                      />
                    </div>
                  </>
                ) : (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">URL</label>
                    <Input
                      placeholder="https://mcp-server.example.com/sse"
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                    />
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button variant="ghost" onClick={() => setShowAddDialog(false)}>
                  Cancel
                </Button>
                <Button onClick={handleAdd} disabled={!name || isSaving}>
                  {isSaving ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    'Add Server'
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto max-w-4xl p-4">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : mcpList.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-16">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                <Plug className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="mb-1 font-medium">No MCP servers</h3>
              <p className="mb-4 text-sm text-muted-foreground">
                Add MCP servers to give your agent access to tools
              </p>
              <Button onClick={() => setShowAddDialog(true)} size="sm">
                <Plus className="mr-1 h-4 w-4" />
                Add your first MCP
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {mcpList.map((mcp) => (
              <Card key={mcp.id}>
                <CardContent className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                      <Plug className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{mcp.name}</span>
                        <Badge variant="outline" className={getStatusColor(mcp.status)}>
                          {getStatusIcon(mcp.status)}
                          <span className="ml-1 capitalize">{mcp.status}</span>
                        </Badge>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Wrench className="h-3 w-3" />
                        {mcp.tool_count} tools
                        {mcp.error_message && (
                          <span className="text-destructive">• {mcp.error_message}</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => handleReconnect(mcp.id)}
                      disabled={reconnectingId === mcp.id}
                    >
                      <RefreshCw
                        className={`h-4 w-4 ${reconnectingId === mcp.id ? 'animate-spin' : ''}`}
                      />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive hover:text-destructive"
                      onClick={() => handleDelete(mcp.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
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
