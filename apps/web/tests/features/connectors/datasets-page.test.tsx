import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DatasetsPage from "@/app/(app)/datasets/page";
import type { DatasetResponse } from "@/types/api";
import { renderWithQueryClient } from "../../test-utils";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const listDatasets = vi.fn();
const resyncDataset = vi.fn();
const deleteDataset = vi.fn();
vi.mock("@/features/connectors/api", () => ({
  connectorsApi: {
    listDatasets: (...args: unknown[]) => listDatasets(...args),
    resyncDataset: (...args: unknown[]) => resyncDataset(...args),
    deleteDataset: (...args: unknown[]) => deleteDataset(...args),
  },
}));

function dataset(overrides: Partial<DatasetResponse> = {}): DatasetResponse {
  return {
    id: "ds-1",
    data_source_id: "src-1",
    name: "orders",
    table_identifier: "public.orders",
    schema: [],
    row_count: 1200,
    size_bytes: 4096,
    status: "ready",
    status_message: null,
    last_synced_at: "2026-08-01T00:00:00Z",
    created_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

describe("DatasetsPage", () => {
  beforeEach(() => {
    listDatasets.mockReset();
    resyncDataset.mockReset();
    deleteDataset.mockReset();
  });

  it("shows an empty state when there are no datasets", async () => {
    listDatasets.mockResolvedValue([]);

    renderWithQueryClient(<DatasetsPage />);

    expect(await screen.findByText("No datasets yet.")).toBeInTheDocument();
  });

  it("lists datasets with status and row count", async () => {
    listDatasets.mockResolvedValue([dataset()]);

    renderWithQueryClient(<DatasetsPage />);

    expect(await screen.findByText("orders")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("1,200 rows")).toBeInTheDocument();
  });

  it("shows the failure message for a failed dataset", async () => {
    listDatasets.mockResolvedValue([
      dataset({ status: "failed", status_message: "Column type mismatch" }),
    ]);

    renderWithQueryClient(<DatasetsPage />);

    expect(await screen.findByText("Column type mismatch")).toBeInTheDocument();
  });

  it("triggers a resync", async () => {
    listDatasets.mockResolvedValue([dataset()]);
    resyncDataset.mockResolvedValue(dataset());
    const user = userEvent.setup();

    renderWithQueryClient(<DatasetsPage />);
    await screen.findByText("orders");

    await user.click(screen.getByRole("button", { name: "Resync" }));

    await waitFor(() => expect(resyncDataset).toHaveBeenCalledWith("ds-1"));
  });

  it("deletes a dataset after confirmation", async () => {
    listDatasets.mockResolvedValue([dataset()]);
    deleteDataset.mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();

    renderWithQueryClient(<DatasetsPage />);
    await screen.findByText("orders");

    await user.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(deleteDataset).toHaveBeenCalledWith("ds-1"));
  });
});
