'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  MessageSquarePlus,
  MessageSquare,
  Settings,
  Plug,
  Shield,
  PanelLeftClose,
  PanelLeft,
  Trash2,
  MoreHorizontal,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { UserProfile } from '@/components/user-profile';
import type { Conversation } from '@/lib/types';

interface ChatSidebarProps {
  conversations: Conversation[];
  currentConversationId?: string;
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export function ChatSidebar({
  conversations,
  currentConversationId,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
  isCollapsed,
  onToggleCollapse,
}: ChatSidebarProps) {
  const pathname = usePathname();

  // Group conversations by date
  const groupedConversations = groupByDate(conversations);

  return (
    <TooltipProvider delayDuration={0}>
      <div
        className={cn(
          'flex h-full flex-col border-r bg-muted/30 transition-all duration-300',
          isCollapsed ? 'w-[60px]' : 'w-[280px]'
        )}
      >
        {/* Header */}
        <div className="flex h-14 items-center justify-between border-b px-3">
          {!isCollapsed && (
            <span className="font-semibold text-foreground">ArmorIQ</span>
          )}
          <div className="flex items-center gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={onNewChat}
                >
                  <MessageSquarePlus className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">New Chat</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={onToggleCollapse}
                >
                  {isCollapsed ? (
                    <PanelLeft className="h-4 w-4" />
                  ) : (
                    <PanelLeftClose className="h-4 w-4" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">
                {isCollapsed ? 'Expand' : 'Collapse'}
              </TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Conversations List */}
        <ScrollArea className="flex-1 px-2 py-2">
          {Object.entries(groupedConversations).map(([dateGroup, convs]) => (
            <div key={dateGroup} className="mb-4">
              {!isCollapsed && (
                <div className="mb-2 px-2 text-xs font-medium text-muted-foreground">
                  {dateGroup}
                </div>
              )}
              <div className="space-y-1">
                {convs.map((conv) => (
                  <ConversationItem
                    key={conv.id}
                    conversation={conv}
                    isActive={conv.id === currentConversationId}
                    isCollapsed={isCollapsed}
                    onSelect={() => onSelectConversation(conv.id)}
                    onDelete={() => onDeleteConversation(conv.id)}
                  />
                ))}
              </div>
            </div>
          ))}
          {conversations.length === 0 && !isCollapsed && (
            <div className="px-2 py-8 text-center text-sm text-muted-foreground">
              No conversations yet.
              <br />
              Start a new chat!
            </div>
          )}
        </ScrollArea>

        {/* Footer Navigation */}
        <div className="border-t p-2">
          <div className="space-y-1">
            <NavItem
              href="/settings/llm"
              icon={Settings}
              label="LLM Settings"
              isCollapsed={isCollapsed}
              isActive={pathname?.startsWith('/settings/llm')}
            />
            <NavItem
              href="/settings/mcp"
              icon={Plug}
              label="MCP Servers"
              isCollapsed={isCollapsed}
              isActive={pathname?.startsWith('/settings/mcp')}
            />
            <NavItem
              href="/plans"
              icon={Shield}
              label="Intent Plans"
              isCollapsed={isCollapsed}
              isActive={pathname?.startsWith('/plans')}
            />
          </div>
        </div>

        {/* User Profile */}
        {!isCollapsed && (
          <div className="border-t">
            <UserProfile />
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}

// Conversation item component
interface ConversationItemProps {
  conversation: Conversation;
  isActive: boolean;
  isCollapsed: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

function ConversationItem({
  conversation,
  isActive,
  isCollapsed,
  onSelect,
  onDelete,
}: ConversationItemProps) {
  if (isCollapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant={isActive ? 'secondary' : 'ghost'}
            size="icon"
            className="h-9 w-9"
            onClick={onSelect}
          >
            <MessageSquare className="h-4 w-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">{conversation.title}</TooltipContent>
      </Tooltip>
    );
  }

  return (
    <div
      className={cn(
        'group flex items-center gap-2 rounded-lg px-2 py-2 transition-colors cursor-pointer',
        isActive
          ? 'bg-accent text-accent-foreground'
          : 'hover:bg-accent/50 text-muted-foreground hover:text-foreground'
      )}
      onClick={onSelect}
    >
      <MessageSquare className="h-4 w-4 shrink-0" />
      <span className="flex-1 truncate text-sm">{conversation.title}</span>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 opacity-0 group-hover:opacity-100"
            onClick={(e) => e.stopPropagation()}
          >
            <MoreHorizontal className="h-3.5 w-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

// Navigation item component
interface NavItemProps {
  href: string;
  icon: React.ElementType;
  label: string;
  isCollapsed: boolean;
  isActive?: boolean;
}

function NavItem({ href, icon: Icon, label, isCollapsed, isActive }: NavItemProps) {
  if (isCollapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <Link href={href}>
            <Button
              variant={isActive ? 'secondary' : 'ghost'}
              size="icon"
              className="h-9 w-9"
            >
              <Icon className="h-4 w-4" />
            </Button>
          </Link>
        </TooltipTrigger>
        <TooltipContent side="right">{label}</TooltipContent>
      </Tooltip>
    );
  }

  return (
    <Link href={href}>
      <Button
        variant={isActive ? 'secondary' : 'ghost'}
        className="w-full justify-start gap-2"
      >
        <Icon className="h-4 w-4" />
        {label}
      </Button>
    </Link>
  );
}

// Helper to group conversations by date
function groupByDate(conversations: Conversation[]): Record<string, Conversation[]> {
  const groups: Record<string, Conversation[]> = {};
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const lastWeek = new Date(today.getTime() - 7 * 86400000);

  for (const conv of conversations) {
    const date = new Date(conv.updated_at);
    let group: string;

    if (date >= today) {
      group = 'Today';
    } else if (date >= yesterday) {
      group = 'Yesterday';
    } else if (date >= lastWeek) {
      group = 'Previous 7 Days';
    } else {
      group = 'Older';
    }

    if (!groups[group]) {
      groups[group] = [];
    }
    groups[group].push(conv);
  }

  return groups;
}
