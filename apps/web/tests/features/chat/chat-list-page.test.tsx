import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";

import ChatPage from "@/app/(app)/chat/page";
import type { ConversationResponse } from "@/types/api";
import { renderWithQueryClient } from "../../test-utils";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const listConversations = vi.fn();
vi.mock("@/features/chat/api", () => ({
  chatApi: {
    listConversations: (...args: unknown[]) => listConversations(...args),
  },
}));

function conversation(overrides: Partial<ConversationResponse> = {}): ConversationResponse {
  return {
    id: "conv-1",
    title: "Q3 revenue trends",
    dataset_id: null,
    status: "active",
    created_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

describe("ChatPage", () => {
  beforeEach(() => {
    listConversations.mockReset();
  });

  it("shows an empty state when there are no conversations", async () => {
    listConversations.mockResolvedValue([]);

    renderWithQueryClient(<ChatPage />);

    expect(await screen.findByText(/No conversations yet/)).toBeInTheDocument();
  });

  it("shows an error message when loading fails", async () => {
    listConversations.mockRejectedValue(new Error("network down"));

    renderWithQueryClient(<ChatPage />);

    expect(await screen.findByText("Couldn't load conversations.")).toBeInTheDocument();
  });

  it("lists conversations with their status", async () => {
    listConversations.mockResolvedValue([conversation()]);

    renderWithQueryClient(<ChatPage />);

    expect(await screen.findByText("Q3 revenue trends")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("links each conversation to its thread page", async () => {
    listConversations.mockResolvedValue([conversation()]);

    renderWithQueryClient(<ChatPage />);

    const link = await screen.findByRole("link", { name: /Q3 revenue trends/ });
    expect(link).toHaveAttribute("href", "/chat/conv-1");
  });
});
