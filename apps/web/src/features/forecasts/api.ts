import { authFetch } from "@/lib/api-client";
import type { ForecastCreateRequest, ForecastResponse } from "@/types/api";

/** Typed calls against `/forecasts/*`. */
export const forecastsApi = {
  listForecasts: (datasetId?: string) =>
    authFetch<ForecastResponse[]>(
      datasetId ? `/forecasts?dataset_id=${datasetId}` : "/forecasts",
    ),

  getForecast: (id: string) => authFetch<ForecastResponse>(`/forecasts/${id}`),

  createForecast: (body: ForecastCreateRequest) =>
    authFetch<ForecastResponse>("/forecasts", { method: "POST", body }),
};
