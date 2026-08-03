import { authFetch } from "@/lib/api-client";
import type {
  AgentRunResponse,
  ConversationCreateRequest,
  ConversationResponse,
  MessageCreateRequest,
  MessageResponse,
  SendMessageResponse,
} from "@/types/api";

/** Typed calls against `/conversations/*`. Every call goes through
 * `authFetch` — none of this is reachable without a session. There's no
 * streaming endpoint (see ADR-0004/ADR-0007): `sendMessage` is a plain
 * blocking POST that can take tens of seconds while the agent graph runs.
 */
export const chatApi = {
  listConversations: () => authFetch<ConversationResponse[]>("/conversations"),

  getConversation: (id: string) => authFetch<ConversationResponse>(`/conversations/${id}`),

  createConversation: (body: ConversationCreateRequest) =>
    authFetch<ConversationResponse>("/conversations", { method: "POST", body }),

  listMessages: (conversationId: string) =>
    authFetch<MessageResponse[]>(`/conversations/${conversationId}/messages`),

  sendMessage: (conversationId: string, body: MessageCreateRequest) =>
    authFetch<SendMessageResponse>(`/conversations/${conversationId}/messages`, {
      method: "POST",
      body,
    }),

  listAgentRuns: (conversationId: string) =>
    authFetch<AgentRunResponse[]>(`/conversations/${conversationId}/agent-runs`),
};
