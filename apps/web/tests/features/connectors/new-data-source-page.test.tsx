import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import NewDataSourcePage from "@/app/(app)/data-sources/new/page";
import { ApiError } from "@/lib/api-client";
import { renderWithQueryClient } from "../../test-utils";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}));

const createDataSource = vi.fn();
vi.mock("@/features/connectors/api", () => ({
  connectorsApi: {
    createDataSource: (...args: unknown[]) => createDataSource(...args),
  },
}));

describe("NewDataSourcePage", () => {
  beforeEach(() => {
    push.mockClear();
    createDataSource.mockReset();
  });

  it("defaults to PostgreSQL fields", () => {
    renderWithQueryClient(<NewDataSourcePage />);

    expect(screen.getByLabelText("Host")).toBeInTheDocument();
    expect(screen.getByLabelText(/Port/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Username/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/)).toBeInTheDocument();
  });

  it("swaps the rendered fields when the source type changes, discarding prior values", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<NewDataSourcePage />);

    await user.type(screen.getByLabelText("Host"), "db.internal");
    await user.selectOptions(screen.getByLabelText("Type"), "bigquery");

    expect(screen.queryByLabelText("Host")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/GCP project ID/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Service account JSON/)).toBeInTheDocument();
  });

  it("rejects submission when a required field is missing", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<NewDataSourcePage />);

    await user.type(screen.getByLabelText("Name"), "Prod DB");
    // Host (required for postgresql) intentionally left blank.
    await user.click(screen.getByRole("button", { name: "Add data source" }));

    expect(await screen.findAllByText("Required")).not.toHaveLength(0);
    expect(createDataSource).not.toHaveBeenCalled();
  });

  it("splits config vs. secret fields correctly on submit", async () => {
    createDataSource.mockResolvedValue({
      id: "ds-1",
      name: "Prod DB",
      source_type: "postgresql",
      config: {},
      status: "pending",
      last_tested_at: null,
      last_test_error: null,
      created_at: "2026-08-01T00:00:00Z",
    });
    const user = userEvent.setup();
    renderWithQueryClient(<NewDataSourcePage />);

    await user.type(screen.getByLabelText("Name"), "Prod DB");
    await user.type(screen.getByLabelText("Host"), "db.internal");
    await user.type(screen.getByLabelText(/Port/), "5432");
    await user.type(screen.getByLabelText(/Username/), "app_user");
    await user.type(screen.getByLabelText(/Password/), "s3cret");
    await user.click(screen.getByRole("button", { name: "Add data source" }));

    await waitFor(() =>
      expect(createDataSource).toHaveBeenCalledWith({
        name: "Prod DB",
        source_type: "postgresql",
        config: { host: "db.internal", port: 5432 },
        secrets: { username: "app_user", password: "s3cret" },
      }),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/data-sources/ds-1"));
  });

  it("sends secrets as null when no secret fields are filled in", async () => {
    createDataSource.mockResolvedValue({
      id: "ds-2",
      name: "Local SQLite",
      source_type: "sqlite",
      config: {},
      status: "pending",
      last_tested_at: null,
      last_test_error: null,
      created_at: "2026-08-01T00:00:00Z",
    });
    const user = userEvent.setup();
    renderWithQueryClient(<NewDataSourcePage />);

    await user.type(screen.getByLabelText("Name"), "Local SQLite");
    await user.selectOptions(screen.getByLabelText("Type"), "sqlite");
    await user.type(screen.getByLabelText(/File path/), "/data/analytics.db");
    await user.click(screen.getByRole("button", { name: "Add data source" }));

    await waitFor(() =>
      expect(createDataSource).toHaveBeenCalledWith({
        name: "Local SQLite",
        source_type: "sqlite",
        config: { database: "/data/analytics.db" },
        secrets: null,
      }),
    );
  });

  it("shows the API's error message on failure", async () => {
    createDataSource.mockRejectedValue(new ApiError("A data source with that name already exists", 409));
    const user = userEvent.setup();
    renderWithQueryClient(<NewDataSourcePage />);

    await user.type(screen.getByLabelText("Name"), "Prod DB");
    await user.type(screen.getByLabelText("Host"), "db.internal");
    await user.click(screen.getByRole("button", { name: "Add data source" }));

    expect(await screen.findByText("A data source with that name already exists")).toBeInTheDocument();
  });
});
