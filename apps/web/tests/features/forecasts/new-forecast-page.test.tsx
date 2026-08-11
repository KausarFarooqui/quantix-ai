import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import NewForecastPage from "@/app/(app)/forecasts/new/page";
import type { DatasetResponse } from "@/types/api";
import { renderWithQueryClient } from "../../test-utils";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}));

const listDatasets = vi.fn();
vi.mock("@/features/connectors/api", () => ({
  connectorsApi: {
    listDatasets: (...args: unknown[]) => listDatasets(...args),
  },
}));

const createForecast = vi.fn();
vi.mock("@/features/forecasts/api", () => ({
  forecastsApi: {
    createForecast: (...args: unknown[]) => createForecast(...args),
  },
}));

function dataset(overrides: Partial<DatasetResponse> = {}): DatasetResponse {
  return {
    id: "ds-1",
    data_source_id: "src-1",
    name: "Revenue",
    table_identifier: "revenue.csv",
    schema: [
      { name: "day", data_type: "date", nullable: false },
      { name: "revenue", data_type: "float", nullable: false },
      { name: "region", data_type: "string", nullable: true },
    ],
    row_count: 20,
    size_bytes: 1024,
    status: "ready",
    status_message: null,
    last_synced_at: null,
    created_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

describe("NewForecastPage", () => {
  beforeEach(() => {
    push.mockReset();
    listDatasets.mockReset();
    createForecast.mockReset();
  });

  it("only offers numeric columns as forecast targets", async () => {
    listDatasets.mockResolvedValue([dataset()]);
    const user = userEvent.setup();

    renderWithQueryClient(<NewForecastPage />);
    const datasetSelect = await screen.findByLabelText("Dataset");
    await screen.findByRole("option", { name: "Revenue" });
    await user.selectOptions(datasetSelect, "ds-1");

    const targetSelect = screen.getByLabelText("Column to forecast") as HTMLSelectElement;
    const optionLabels = Array.from(targetSelect.options).map((o) => o.value);

    expect(optionLabels).toContain("revenue");
    expect(optionLabels).not.toContain("region");
    expect(optionLabels).not.toContain("day");
  });

  it("submits the form and navigates to the new forecast", async () => {
    listDatasets.mockResolvedValue([dataset()]);
    createForecast.mockResolvedValue({
      id: "fc-1",
      dataset_id: "ds-1",
      conversation_id: null,
      target_column: "revenue",
      time_column: "day",
      method: "linear_trend",
      historical_points: 20,
      points: [],
      created_at: "2026-08-11T00:00:00Z",
    });
    const user = userEvent.setup();

    renderWithQueryClient(<NewForecastPage />);
    const datasetSelect = await screen.findByLabelText("Dataset");
    await screen.findByRole("option", { name: "Revenue" });
    await user.selectOptions(datasetSelect, "ds-1");
    await user.selectOptions(screen.getByLabelText("Column to forecast"), "revenue");
    await user.selectOptions(screen.getByLabelText(/Sort by column/), "day");

    await user.click(screen.getByRole("button", { name: "Generate forecast" }));

    await waitFor(() =>
      expect(createForecast).toHaveBeenCalledWith({
        dataset_id: "ds-1",
        target_column: "revenue",
        time_column: "day",
        periods: 5,
      }),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/forecasts/fc-1"));
  });

  it("disables submit until a dataset and target column are chosen", async () => {
    listDatasets.mockResolvedValue([dataset()]);

    renderWithQueryClient(<NewForecastPage />);
    await screen.findByLabelText("Dataset");

    expect(screen.getByRole("button", { name: "Generate forecast" })).toBeDisabled();
  });
});
