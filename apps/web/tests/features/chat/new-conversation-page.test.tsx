import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import NewConversationPage from "@/app/(app)/chat/new/page";
import { ApiError } from "@/lib/api-client";
import type { DatasetResponse } from "@/types/api";
import { renderWithQueryClient } from "../../test-utils";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}));

const createConversation = vi.fn();
vi.mock("@/features/chat/api", () => ({
  chatApi: {
    createConversation: (...args: unknown[]) => createConversation(...args),
  },
}));

const listDatasets = vi.fn();
vi.mock("@/features/connectors/api", () => ({
  connectorsApi: {
    listDatasets: (...args: unknown[]) => listDatasets(...args),
  },
}));

function dataset(overrides: Partial<DatasetResponse> = {}): DatasetResponse {
  return {
    id: "ds-1",
    data_source_id: "src-1",
    name: "orders",
    table_identifier: "public.orders",
    schema: [],
    row_count: null,
    size_bytes: null,
    status: "ready",
    status_message: null,
    last_synced_at: null,
    created_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

describe("NewConversationPage", () => {
  beforeEach(() => {
    push.mockClear();
    createConversation.mockReset();
    listDatasets.mockReset();
    listDatasets.mockResolvedValue([]);
  });

  it("rejects submission with no title", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<NewConversationPage />);

    await user.click(screen.getByRole("button", { name: "Start conversation" }));

    expect(await screen.findByText("Required")).toBeInTheDocument();
    expect(createConversation).not.toHaveBeenCalled();
  });

  it("only offers ready datasets in the picker", async () => {
    listDatasets.mockResolvedValue([
      dataset({ id: "ds-1", name: "orders", status: "ready" }),
      dataset({ id: "ds-2", name: "still syncing", status: "processing" }),
    ]);

    renderWithQueryClient(<NewConversationPage />);

    expect(await screen.findByRole("option", { name: "orders" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "still syncing" })).not.toBeInTheDocument();
  });

  it("creates a conversation with no dataset and redirects to its thread", async () => {
    createConversation.mockResolvedValue({
      id: "conv-1",
      title: "Q3 revenue trends",
      dataset_id: null,
      status: "active",
      created_at: "2026-08-01T00:00:00Z",
    });
    const user = userEvent.setup();
    renderWithQueryClient(<NewConversationPage />);

    await user.type(screen.getByLabelText("Title"), "Q3 revenue trends");
    await user.click(screen.getByRole("button", { name: "Start conversation" }));

    await waitFor(() =>
      expect(createConversation).toHaveBeenCalledWith({ title: "Q3 revenue trends", dataset_id: null }),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/chat/conv-1"));
  });

  it("scopes the conversation to the selected dataset", async () => {
    listDatasets.mockResolvedValue([dataset({ id: "ds-1", name: "orders" })]);
    createConversation.mockResolvedValue({
      id: "conv-2",
      title: "Orders analysis",
      dataset_id: "ds-1",
      status: "active",
      created_at: "2026-08-01T00:00:00Z",
    });
    const user = userEvent.setup();
    renderWithQueryClient(<NewConversationPage />);

    await user.type(screen.getByLabelText("Title"), "Orders analysis");
    await screen.findByRole("option", { name: "orders" });
    await user.selectOptions(screen.getByLabelText(/Dataset/), "ds-1");
    await user.click(screen.getByRole("button", { name: "Start conversation" }));

    await waitFor(() =>
      expect(createConversation).toHaveBeenCalledWith({ title: "Orders analysis", dataset_id: "ds-1" }),
    );
  });

  it("shows the API's error message on failure", async () => {
    createConversation.mockRejectedValue(new ApiError("Title already used", 409));
    const user = userEvent.setup();
    renderWithQueryClient(<NewConversationPage />);

    await user.type(screen.getByLabelText("Title"), "Q3 revenue trends");
    await user.click(screen.getByRole("button", { name: "Start conversation" }));

    expect(await screen.findByText("Title already used")).toBeInTheDocument();
  });
});
