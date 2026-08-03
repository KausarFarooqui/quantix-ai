"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useConversations } from "@/features/chat/hooks";
import { ConversationStatusBadge } from "@/features/chat/status-badge";
import { ApiError } from "@/lib/api-client";

export default function ChatPage() {
  const conversations = useConversations();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Chat</h1>
        <Button asChild>
          <Link href="/chat/new">New conversation</Link>
        </Button>
      </div>

      {conversations.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {conversations.isError && (
        <p className="text-sm text-destructive">
          {conversations.error instanceof ApiError ? conversations.error.message : "Couldn't load conversations."}
        </p>
      )}

      {conversations.data && conversations.data.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <p className="text-sm text-muted-foreground">
              No conversations yet. Start one to ask questions about your data in plain language.
            </p>
            <Button asChild>
              <Link href="/chat/new">New conversation</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {conversations.data && conversations.data.length > 0 && (
        <div className="flex flex-col divide-y divide-border rounded-lg border border-border">
          {conversations.data.map((conversation) => (
            <Link
              key={conversation.id}
              href={`/chat/${conversation.id}`}
              className="flex items-center justify-between gap-4 px-4 py-3 hover:bg-accent"
            >
              <span className="truncate font-medium">{conversation.title}</span>
              <div className="flex shrink-0 items-center gap-3 text-sm text-muted-foreground">
                <ConversationStatusBadge status={conversation.status} />
                <span>{new Date(conversation.created_at).toLocaleString()}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
