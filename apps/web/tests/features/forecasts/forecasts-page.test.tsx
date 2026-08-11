import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";

import ForecastsPage from "@/app/(app)/forecasts/page";
import type { DatasetResponse, ForecastResponse } from "@/types/api";
import { renderWithQueryClient } from "../../test-utils";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const listForecasts = vi.fn();
vi.mock("@/features/forecasts/api", () => ({
  forecastsApi: {
    listForecasts: (...args: unknown[]) => listForecasts(...args),
  },
}));

const listDatasets = vi.fn();
vi.mock("@/features/connectors/api", () => ({
  connectorsApi: {
    listDatasets: (...args: unknown[]) => listDatasets(...args),
  },
}));

function forecast(overrides: Partial<ForecastResponse> = {}): ForecastResponse {
  return {
    id: "fc-1",
    dataset_id: "ds-1",
    conversation_id: null,
    target_column: "revenue",
    time_column: null,
    method: "holt_winters",
    historical_points: 20,
    points: [
      { period: 1, value: 105, lower: 95, upper: 115 },
      { period: 2, value: 110, lower: 97, upper: 123 },
    ],
    created_at: "2026-08-11T00:00:00Z",
    ...overrides,
  };
}

function dataset(overrides: Partial<DatasetResponse> = {}): DatasetResponse {
  return {
    id: "ds-1",
    data_source_id: "src-1",
    name: "Revenue",
    table_identifier: "revenue.csv",
    schema: [],
    row_count: 20,
    size_bytes: 1024,
    status: "ready",
    status_message: null,
    last_synced_at: null,
    created_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

describe("ForecastsPage", () => {
  beforeEach(() => {
    listForecasts.mockReset();
    listDatasets.mockReset();
    listDatasets.mockResolvedValue([dataset()]);
  });

  it("shows an empty state when there are no forecasts", async () => {
    listForecasts.mockResolvedValue([]);

    renderWithQueryClient(<ForecastsPage />);

    expect(await screen.findByText("No forecasts yet.")).toBeInTheDocument();
  });

  it("lists forecasts with method, dataset name, and horizon", async () => {
    listForecasts.mockResolvedValue([forecast()]);

    renderWithQueryClient(<ForecastsPage />);

    expect(await screen.findByText("revenue")).toBeInTheDocument();
    expect(screen.getByText("Holt-Winters")).toBeInTheDocument();
    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("2 periods ahead")).toBeInTheDocument();
  });

  it("shows the sort column when one was used", async () => {
    listForecasts.mockResolvedValue([forecast({ time_column: "day" })]);

    renderWithQueryClient(<ForecastsPage />);

    expect(await screen.findByText("by day")).toBeInTheDocument();
  });
});
