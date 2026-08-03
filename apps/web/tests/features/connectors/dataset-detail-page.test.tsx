import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DatasetDetailPage from "@/app/(app)/datasets/[id]/page";
import { renderWithQueryClient } from "../../test-utils";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
  useParams: () => ({ id: "ds-1" }),
}));

const getDataset = vi.fn();
const previewDataset = vi.fn();
const resyncDataset = vi.fn();
const deleteDataset = vi.fn();
vi.mock("@/features/connectors/api", () => ({
  connectorsApi: {
    getDataset: (...args: unknown[]) => getDataset(...args),
    previewDataset: (...args: unknown[]) => previewDataset(...args),
    resyncDataset: (...args: unknown[]) => resyncDataset(...args),
    deleteDataset: (...args: unknown[]) => deleteDataset(...args),
  },
}));

// ag-grid doesn't render meaningfully under jsdom (no layout engine) —
// swapped for a lightweight stand-in that proves the right rows/columns
// were handed down, which is what this page is actually responsible for.
vi.mock("@/features/connectors/dataset-preview-grid", () => ({
  DatasetPreviewGrid: ({ columns, rows }: { columns: unknown[]; rows: unknown[] }) => (
    <div data-testid="preview-grid">
      {columns.length} columns, {rows.length} rows
    </div>
  ),
}));

const readyDataset = {
  id: "ds-1",
  data_source_id: "src-1",
  name: "orders",
  table_identifier: "public.orders",
  schema: [
    { name: "id", data_type: "integer" as const, nullable: false },
    { name: "total", data_type: "float" as const, nullable: true },
  ],
  row_count: 2,
  size_bytes: 128,
  status: "ready" as const,
  status_message: null,
  last_synced_at: "2026-08-01T00:00:00Z",
  created_at: "2026-08-01T00:00:00Z",
};

describe("DatasetDetailPage", () => {
  beforeEach(() => {
    push.mockClear();
    getDataset.mockReset();
    previewDataset.mockReset();
    resyncDataset.mockReset();
    deleteDataset.mockReset();
  });

  it("renders the schema and preview grid for a ready dataset", async () => {
    getDataset.mockResolvedValue(readyDataset);
    previewDataset.mockResolvedValue({
      dataset: readyDataset,
      rows: [
        { id: 1, total: 9.99 },
        { id: 2, total: 19.99 },
      ],
    });

    renderWithQueryClient(<DatasetDetailPage />);

    expect(await screen.findByText("orders")).toBeInTheDocument();
    expect(screen.getByText("id")).toBeInTheDocument();
    expect(screen.getByText("total")).toBeInTheDocument();
    // The type column, not the name column — `total` is nullable, `id` isn't.
    expect(screen.getByText("float?")).toBeInTheDocument();
    expect(screen.getByText("integer")).toBeInTheDocument();
    expect(await screen.findByTestId("preview-grid")).toHaveTextContent("2 columns, 2 rows");
  });

  it("doesn't fetch a preview for a dataset that isn't ready", async () => {
    getDataset.mockResolvedValue({ ...readyDataset, status: "processing" });

    renderWithQueryClient(<DatasetDetailPage />);

    expect(
      await screen.findByText("This dataset isn't ready yet — preview becomes available once it finishes syncing."),
    ).toBeInTheDocument();
    expect(previewDataset).not.toHaveBeenCalled();
  });

  it("deletes the dataset and redirects after confirmation", async () => {
    getDataset.mockResolvedValue(readyDataset);
    previewDataset.mockResolvedValue({ dataset: readyDataset, rows: [] });
    deleteDataset.mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();

    renderWithQueryClient(<DatasetDetailPage />);
    await screen.findByText("orders");

    await user.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(deleteDataset).toHaveBeenCalledWith("ds-1"));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/datasets"));
  });
});
