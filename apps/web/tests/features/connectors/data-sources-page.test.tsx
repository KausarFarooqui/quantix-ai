import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DataSourcesPage from "@/app/(app)/data-sources/page";
import type { DataSourceResponse } from "@/types/api";
import { renderWithQueryClient } from "../../test-utils";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const listDataSources = vi.fn();
const testDataSource = vi.fn();
const deleteDataSource = vi.fn();
vi.mock("@/features/connectors/api", () => ({
  connectorsApi: {
    listDataSources: (...args: unknown[]) => listDataSources(...args),
    testDataSource: (...args: unknown[]) => testDataSource(...args),
    deleteDataSource: (...args: unknown[]) => deleteDataSource(...args),
  },
}));

function dataSource(overrides: Partial<DataSourceResponse> = {}): DataSourceResponse {
  return {
    id: "ds-1",
    name: "Production Postgres",
    source_type: "postgresql",
    config: { host: "db.internal" },
    status: "active",
    last_tested_at: "2026-08-01T00:00:00Z",
    last_test_error: null,
    created_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

describe("DataSourcesPage", () => {
  beforeEach(() => {
    listDataSources.mockReset();
    testDataSource.mockReset();
    deleteDataSource.mockReset();
  });

  it("shows an empty state when there are no data sources", async () => {
    listDataSources.mockResolvedValue([]);

    renderWithQueryClient(<DataSourcesPage />);

    expect(await screen.findByText("No data sources yet.")).toBeInTheDocument();
  });

  it("shows an error message when loading fails", async () => {
    listDataSources.mockRejectedValue(new Error("network down"));

    renderWithQueryClient(<DataSourcesPage />);

    expect(await screen.findByText("Couldn't load data sources.")).toBeInTheDocument();
  });

  it("lists data sources with their type and status", async () => {
    listDataSources.mockResolvedValue([dataSource()]);

    renderWithQueryClient(<DataSourcesPage />);

    expect(await screen.findByText("Production Postgres")).toBeInTheDocument();
    expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("triggers a connection test", async () => {
    listDataSources.mockResolvedValue([dataSource()]);
    testDataSource.mockResolvedValue({ success: true });
    const user = userEvent.setup();

    renderWithQueryClient(<DataSourcesPage />);
    await screen.findByText("Production Postgres");

    await user.click(screen.getByRole("button", { name: "Test" }));

    await waitFor(() => expect(testDataSource).toHaveBeenCalledWith("ds-1"));
  });

  it("deletes a data source after confirmation", async () => {
    listDataSources.mockResolvedValue([dataSource()]);
    deleteDataSource.mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();

    renderWithQueryClient(<DataSourcesPage />);
    await screen.findByText("Production Postgres");

    await user.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(deleteDataSource).toHaveBeenCalledWith("ds-1"));
  });

  it("does not delete when the confirmation is dismissed", async () => {
    listDataSources.mockResolvedValue([dataSource()]);
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();

    renderWithQueryClient(<DataSourcesPage />);
    await screen.findByText("Production Postgres");

    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(deleteDataSource).not.toHaveBeenCalled();
  });
});
