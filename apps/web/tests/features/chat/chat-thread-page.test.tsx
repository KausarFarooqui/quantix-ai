import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ChatThreadPage from "@/app/(app)/chat/[id]/page";
import { ApiError } from "@/lib/api-client";
import type { AgentRunResponse, ConversationResponse, MessageResponse, SendMessageResponse } from "@/types/api";
import { renderWithQueryClient } from "../../test-utils";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => ({ id: "conv-1" }),
}));

const getConversation = vi.fn();
const listMessages = vi.fn();
const sendMessage = vi.fn();
const listAgentRuns = vi.fn();
vi.mock("@/features/chat/api", () => ({
  chatApi: {
    getConversation: (...args: unknown[]) => getConversation(...args),
    listMessages: (...args: unknown[]) => listMessages(...args),
    sendMessage: (...args: unknown[]) => sendMessage(...args),
    listAgentRuns: (...args: unknown[]) => listAgentRuns(...args),
  },
}));

const conversation: ConversationResponse = {
  id: "conv-1",
  title: "Q3 revenue trends",
  dataset_id: null,
  status: "active",
  created_at: "2026-08-01T00:00:00Z",
};

const userMessage: MessageResponse = {
  id: "m-1",
  conversation_id: "conv-1",
  role: "user",
  content: "What drove Q3 revenue?",
  agent_type: null,
  created_at: "2026-08-01T00:00:01Z",
};

const assistantMessage: MessageResponse = {
  id: "m-2",
  conversation_id: "conv-1",
  role: "assistant",
  content: "Revenue grew 12% quarter over quarter, mostly from enterprise renewals.",
  agent_type: "sql_generation",
  created_at: "2026-08-01T00:00:05Z",
};

const specialistRun: AgentRunResponse = {
  id: "run-1",
  agent_type: "sql_generation",
  status: "succeeded",
  output_summary: "Ran a query against the orders dataset.",
  tool_calls: [],
  prompt_tokens: 120,
  completion_tokens: 45,
  latency_ms: 1500,
  error_message: null,
  created_at: "2026-08-01T00:00:05Z",
};

describe("ChatThreadPage", () => {
  beforeEach(() => {
    getConversation.mockReset();
    listMessages.mockReset();
    sendMessage.mockReset();
    listAgentRuns.mockReset();
    getConversation.mockResolvedValue(conversation);
  });

  it("renders the conversation title and status", async () => {
    listMessages.mockResolvedValue([]);
    listAgentRuns.mockResolvedValue([]);

    renderWithQueryClient(<ChatThreadPage />);

    expect(await screen.findByText("Q3 revenue trends")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("No agents have run in this conversation yet.")).toBeInTheDocument();
  });

  it("shows an error message when the conversation fails to load", async () => {
    getConversation.mockRejectedValue(new ApiError("Not found", 404));
    listMessages.mockResolvedValue([]);
    listAgentRuns.mockResolvedValue([]);

    renderWithQueryClient(<ChatThreadPage />);

    expect(await screen.findByText("Not found")).toBeInTheDocument();
  });

  it("sends a message optimistically, shows a pending state, then renders the reply and agent activity", async () => {
    listMessages.mockResolvedValueOnce([]).mockResolvedValueOnce([userMessage, assistantMessage]);
    listAgentRuns.mockResolvedValueOnce([]).mockResolvedValueOnce([specialistRun]);

    let resolveSend: ((value: SendMessageResponse) => void) | undefined;
    sendMessage.mockImplementation(
      () =>
        new Promise<SendMessageResponse>((resolve) => {
          resolveSend = resolve;
        }),
    );

    const user = userEvent.setup();
    renderWithQueryClient(<ChatThreadPage />);
    await screen.findByText("Q3 revenue trends");

    await user.type(screen.getByPlaceholderText("Ask about your data…"), "What drove Q3 revenue?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    // Optimistic user message + pending indicator, before the mutation resolves.
    expect(await screen.findByText("What drove Q3 revenue?")).toBeInTheDocument();
    expect(screen.getByText("Agent is working…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();

    resolveSend?.({ message: assistantMessage, agent_runs: [specialistRun] });

    expect(await screen.findByText(/Revenue grew 12%/)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Agent is working…")).not.toBeInTheDocument());
    // "SQL generation" appears twice — once as the label above the
    // assistant's bubble, once in the agent activity panel.
    expect(screen.getAllByText("SQL generation").length).toBeGreaterThan(0);
    expect(screen.getByText("Succeeded")).toBeInTheDocument();
  });

  it("rolls back the optimistic message and restores the composer on failure", async () => {
    listMessages.mockResolvedValue([]);
    listAgentRuns.mockResolvedValue([]);
    sendMessage.mockRejectedValue(new ApiError("Something went wrong upstream", 502));

    const user = userEvent.setup();
    renderWithQueryClient(<ChatThreadPage />);
    await screen.findByText("Q3 revenue trends");

    const textarea = screen.getByPlaceholderText("Ask about your data…");
    await user.type(textarea, "What drove Q3 revenue?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("What drove Q3 revenue?")).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText("Something went wrong upstream")).toBeInTheDocument());
    // The rolled-back message list is empty again — checked via the
    // "nothing sent yet" placeholder rather than the absence of the
    // message text itself, since the composer's restored value renders
    // that same text inside the textarea and would otherwise collide.
    await waitFor(() =>
      expect(screen.getByText("Send a message below to start the conversation.")).toBeInTheDocument(),
    );
    expect(textarea).toHaveValue("What drove Q3 revenue?");
  });
});
