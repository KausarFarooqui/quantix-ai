import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DataSourceDetailPage from "@/app/(app)/data-sources/[id]/page";
import { renderWithQueryClient } from "../../test-utils";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
  useParams: () => ({ id: "src-1" }),
}));

const getDataSource = vi.fn();
const testDataSource = vi.fn();
const discoverDataSource = vi.fn();
const syncDatasetFromSource = vi.fn();
const deleteDataSource = vi.fn();
vi.mock("@/features/connectors/api", () => ({
  connectorsApi: {
    getDataSource: (...args: unknown[]) => getDataSource(...args),
    testDataSource: (...args: unknown[]) => testDataSource(...args),
    discoverDataSource: (...args: unknown[]) => discoverDataSource(...args),
    syncDatasetFromSource: (...args: unknown[]) => syncDatasetFromSource(...args),
    deleteDataSource: (...args: unknown[]) => deleteDataSource(...args),
  },
}));

const dataSource = {
  id: "src-1",
  name: "Production Postgres",
  source_type: "postgresql" as const,
  config: { host: "db.internal" },
  status: "active" as const,
  last_tested_at: "2026-08-01T00:00:00Z",
  last_test_error: null,
  created_at: "2026-08-01T00:00:00Z",
};

describe("DataSourceDetailPage", () => {
  beforeEach(() => {
    push.mockClear();
    getDataSource.mockReset();
    testDataSource.mockReset();
    discoverDataSource.mockReset();
    syncDatasetFromSource.mockReset();
    deleteDataSource.mockReset();
  });

  it("renders the data source's name, type, and status", async () => {
    getDataSource.mockResolvedValue(dataSource);

    renderWithQueryClient(<DataSourceDetailPage />);

    expect(await screen.findByText("Production Postgres")).toBeInTheDocument();
    expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("discovers tables on request and pulls one into a dataset", async () => {
    getDataSource.mockResolvedValue(dataSource);
    discoverDataSource.mockResolvedValue([
      { identifier: "public.orders", columns: [], row_count_estimate: 500 },
    ]);
    syncDatasetFromSource.mockResolvedValue({
      id: "dataset-1",
      data_source_id: "src-1",
      name: "orders",
      table_identifier: "public.orders",
      schema: [],
      row_count: null,
      size_bytes: null,
      status: "pending",
      status_message: null,
      last_synced_at: null,
      created_at: "2026-08-01T00:00:00Z",
    });
    const user = userEvent.setup();

    renderWithQueryClient(<DataSourceDetailPage />);
    await screen.findByText("Production Postgres");

    await user.click(screen.getByRole("button", { name: "Discover tables" }));

    expect(await screen.findByText("public.orders")).toBeInTheDocument();
    expect(screen.getByText("~500 rows", { exact: false })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Pull as dataset" }));

    await waitFor(() =>
      expect(syncDatasetFromSource).toHaveBeenCalledWith("src-1", {
        table_identifier: "public.orders",
        dataset_name: undefined,
      }),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/datasets/dataset-1"));
  });

  it("deletes the data source and redirects after confirmation", async () => {
    getDataSource.mockResolvedValue(dataSource);
    deleteDataSource.mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();

    renderWithQueryClient(<DataSourceDetailPage />);
    await screen.findByText("Production Postgres");

    await user.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(deleteDataSource).toHaveBeenCalledWith("src-1"));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/data-sources"));
  });
});
