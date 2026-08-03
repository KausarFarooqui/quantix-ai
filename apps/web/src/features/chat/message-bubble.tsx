import { agentTypeLabel } from "@/features/chat/agent-labels";
import { cn } from "@/lib/utils";
import type { MessageResponse } from "@/types/api";

/** A single message in a conversation thread. `system` messages (none are
 * produced by the current backend, but the type allows for them) render as
 * a centered note rather than a bubble; `user`/`assistant` render as
 * left/right-aligned bubbles, with the producing agent labeled above an
 * assistant bubble when one is set. `pending` dims an optimistically
 * inserted message that hasn't been confirmed by the server yet. */
export function MessageBubble({ message, pending = false }: { message: MessageResponse; pending?: boolean }) {
  if (message.role === "system") {
    return <p className="my-2 text-center text-xs text-muted-foreground">{message.content}</p>;
  }

  const isUser = message.role === "user";

  return (
    <div className={cn("flex flex-col gap-1", isUser ? "items-end" : "items-start")}>
      {!isUser && message.agent_type && (
        <span className="text-xs font-medium text-muted-foreground">{agentTypeLabel(message.agent_type)}</span>
      )}
      <div
        className={cn(
          "max-w-[75%] whitespace-pre-wrap rounded-lg px-4 py-2 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "border border-border bg-card",
          pending && "opacity-70",
        )}
      >
        {message.content}
      </div>
      <span className="text-xs text-muted-foreground">{new Date(message.created_at).toLocaleTimeString()}</span>
    </div>
  );
}
