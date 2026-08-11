import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";

import ForecastDetailPage from "@/app/(app)/forecasts/[id]/page";
import type { DatasetResponse, ForecastResponse } from "@/types/api";
import { renderWithQueryClient } from "../../test-utils";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "fc-1" }),
}));

const getForecast = vi.fn();
vi.mock("@/features/forecasts/api", () => ({
  forecastsApi: {
    getForecast: (...args: unknown[]) => getForecast(...args),
  },
}));

const getDataset = vi.fn();
vi.mock("@/features/connectors/api", () => ({
  connectorsApi: {
    getDataset: (...args: unknown[]) => getDataset(...args),
  },
}));

// The real chart renders to a canvas via echarts, which jsdom doesn't
// support — mocked away same as `DatasetPreviewGrid` is in the dataset
// detail page test, asserting the data reaches it rather than rendering it.
vi.mock("@/features/forecasts/forecast-chart", () => ({
  ForecastChart: ({ points }: { points: { period: number }[] }) => (
    <div data-testid="forecast-chart">{points.length} points</div>
  ),
}));

function forecast(overrides: Partial<ForecastResponse> = {}): ForecastResponse {
  return {
    id: "fc-1",
    dataset_id: "ds-1",
    conversation_id: null,
    target_column: "revenue",
    time_column: "day",
    method: "holt_winters",
    historical_points: 20,
    points: [
      { period: 1, value: 105.4, lower: 95.1, upper: 115.7 },
      { period: 2, value: 110.2, lower: 97.3, upper: 123.1 },
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

describe("ForecastDetailPage", () => {
  beforeEach(() => {
    getForecast.mockReset();
    getDataset.mockReset();
  });

  it("shows the forecast, method, and linked dataset", async () => {
    getForecast.mockResolvedValue(forecast());
    getDataset.mockResolvedValue(dataset());

    renderWithQueryClient(<ForecastDetailPage />);

    expect(await screen.findByText("revenue")).toBeInTheDocument();
    expect(screen.getByText("Holt-Winters")).toBeInTheDocument();
    expect(await screen.findByText("Revenue")).toBeInTheDocument();
    expect(screen.getByTestId("forecast-chart")).toHaveTextContent("2 points");
  });

  it("shows a heuristic-interval disclaimer for the linear-trend fallback", async () => {
    getForecast.mockResolvedValue(forecast({ method: "linear_trend" }));
    getDataset.mockResolvedValue(dataset());

    renderWithQueryClient(<ForecastDetailPage />);

    expect(await screen.findByText(/heuristic range/)).toBeInTheDocument();
  });

  it("renders the values table with period, forecast, and range", async () => {
    getForecast.mockResolvedValue(forecast());
    getDataset.mockResolvedValue(dataset());

    renderWithQueryClient(<ForecastDetailPage />);

    expect(await screen.findByText("+1")).toBeInTheDocument();
    expect(screen.getByText("105.40")).toBeInTheDocument();
    expect(screen.getByText("95.10 – 115.70")).toBeInTheDocument();
  });

  it("shows an error message when the forecast can't be loaded", async () => {
    getForecast.mockRejectedValue(new Error("nope"));

    renderWithQueryClient(<ForecastDetailPage />);

    expect(await screen.findByText("Couldn't load this forecast.")).toBeInTheDocument();
  });
});
