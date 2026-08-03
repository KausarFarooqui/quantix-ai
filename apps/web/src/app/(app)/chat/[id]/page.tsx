"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { AgentActivityPanel } from "@/features/chat/agent-activity-panel";
import { useAgentRuns, useConversation, useMessages, useSendMessage } from "@/features/chat/hooks";
import { MessageBubble } from "@/features/chat/message-bubble";
import { ConversationStatusBadge } from "@/features/chat/status-badge";
import { ApiError } from "@/lib/api-client";

export default function ChatThreadPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const conversation = useConversation(id);
  const messages = useMessages(id);
  const agentRuns = useAgentRuns(id);
  const sendMessage = useSendMessage(id);

  const [content, setContent] = React.useState("");
  const bottomRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    // Optional-chained on the method itself, not just the ref: jsdom (used
    // by the test suite) doesn't implement `scrollIntoView` at all, so
    // `bottomRef.current?.scrollIntoView(...)` would still throw there.
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages.data?.length, sendMessage.isPending]);

  // `sendMessage.mutate` clears the composer immediately and restores the
  // typed text only if the request fails — see the hook's docstring for
  // why the whole round trip can take tens of seconds (no streaming yet).
  function submitMessage() {
    const trimmed = content.trim();
    if (!trimmed || sendMessage.isPending) {
      return;
    }
    setContent("");
    sendMessage.mutate(trimmed, { onError: () => setContent(trimmed) });
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    submitMessage();
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitMessage();
    }
  }

  if (conversation.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  if (conversation.isError || !conversation.data) {
    return (
      <p className="text-sm text-destructive">
        {conversation.error instanceof ApiError ? conversation.error.message : "Couldn't load this conversation."}
      </p>
    );
  }

  const sendErrorMessage =
    sendMessage.error instanceof ApiError
      ? sendMessage.error.message
      : sendMessage.error
        ? "Couldn't send that message — please try again."
        : null;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <div className="flex flex-col gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">{conversation.data.title}</h1>
            <ConversationStatusBadge status={conversation.data.status} />
          </div>
          <button
            type="button"
            onClick={() => router.push("/chat")}
            className="text-sm text-muted-foreground hover:underline"
          >
            ← Back to conversations
          </button>
        </div>

        <div className="flex max-h-[60vh] flex-1 flex-col gap-3 overflow-y-auto rounded-lg border border-border p-4">
          {messages.isLoading && <p className="text-sm text-muted-foreground">Loading messages…</p>}
          {messages.isError && (
            <p className="text-sm text-destructive">
              {messages.error instanceof ApiError ? messages.error.message : "Couldn't load messages."}
            </p>
          )}
          {messages.data && messages.data.length === 0 && !sendMessage.isPending && (
            <p className="text-sm text-muted-foreground">Send a message below to start the conversation.</p>
          )}
          {messages.data?.map((message) => (
            <MessageBubble key={message.id} message={message} pending={message.id.startsWith("optimistic-")} />
          ))}
          {sendMessage.isPending && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-muted-foreground" />
              Agent is working…
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {sendErrorMessage && <p className="text-sm text-destructive">{sendErrorMessage}</p>}

        <form onSubmit={handleSubmit} className="flex gap-2">
          <Textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your data…"
            rows={2}
            className="flex-1 font-sans text-sm"
            disabled={sendMessage.isPending}
          />
          <Button type="submit" disabled={sendMessage.isPending || content.trim().length === 0}>
            {sendMessage.isPending ? "Sending…" : "Send"}
          </Button>
        </form>
      </div>

      <div>
        <AgentActivityPanel agentRuns={agentRuns.data ?? []} />
      </div>
    </div>
  );
}
