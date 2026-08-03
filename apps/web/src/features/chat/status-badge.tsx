import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { AgentRunStatus, ConversationStatus } from "@/types/api";

const CONVERSATION_STATUS: Record<ConversationStatus, { label: string; variant: BadgeProps["variant"] }> = {
  active: { label: "Active", variant: "success" },
  archived: { label: "Archived", variant: "secondary" },
};

const AGENT_RUN_STATUS: Record<AgentRunStatus, { label: string; variant: BadgeProps["variant"] }> = {
  running: { label: "Running", variant: "warning" },
  succeeded: { label: "Succeeded", variant: "success" },
  failed: { label: "Failed", variant: "destructive" },
};

export function ConversationStatusBadge({ status }: { status: ConversationStatus }) {
  const { label, variant } = CONVERSATION_STATUS[status];
  return <Badge variant={variant}>{label}</Badge>;
}

export function AgentRunStatusBadge({ status }: { status: AgentRunStatus }) {
  const { label, variant } = AGENT_RUN_STATUS[status];
  return <Badge variant={variant}>{label}</Badge>;
}
