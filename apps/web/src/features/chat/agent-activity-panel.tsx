import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { agentTypeLabel } from "@/features/chat/agent-labels";
import { AgentRunStatusBadge } from "@/features/chat/status-badge";
import type { AgentRunResponse } from "@/types/api";

/** Lists specialist agent invocations for a conversation, most recent
 * first — an observability panel alongside the thread showing which of the
 * twelve specialists worked on each turn. Supervisor runs are filtered
 * out: they route to specialists but are never themselves user-facing (see
 * `AgentType`'s docstring on the backend enum). */
export function AgentActivityPanel({ agentRuns }: { agentRuns: AgentRunResponse[] }) {
  const specialistRuns = agentRuns.filter((run) => run.agent_type !== "supervisor");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Agent activity</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {specialistRuns.length === 0 && (
          <p className="text-sm text-muted-foreground">No agents have run in this conversation yet.</p>
        )}
        {specialistRuns
          .slice()
          .reverse()
          .map((run) => (
            <div
              key={run.id}
              className="flex flex-col gap-1 border-b border-border pb-3 last:border-b-0 last:pb-0"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{agentTypeLabel(run.agent_type)}</span>
                <AgentRunStatusBadge status={run.status} />
              </div>
              {run.output_summary && <p className="text-xs text-muted-foreground">{run.output_summary}</p>}
              {run.status === "failed" && run.error_message && (
                <p className="text-xs text-destructive">{run.error_message}</p>
              )}
              {run.latency_ms !== null && (
                <p className="text-xs text-muted-foreground">{(run.latency_ms / 1000).toFixed(1)}s</p>
              )}
            </div>
          ))}
      </CardContent>
    </Card>
  );
}
