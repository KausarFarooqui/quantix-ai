"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { forecastsApi } from "@/features/forecasts/api";
import type { ForecastCreateRequest } from "@/types/api";

const forecastsKey = (datasetId?: string) => ["forecasts", datasetId ?? "all"] as const;
const forecastKey = (id: string) => ["forecasts", "detail", id] as const;

export function useForecasts(datasetId?: string) {
  return useQuery({
    queryKey: forecastsKey(datasetId),
    queryFn: () => forecastsApi.listForecasts(datasetId),
  });
}

export function useForecast(id: string) {
  return useQuery({
    queryKey: forecastKey(id),
    queryFn: () => forecastsApi.getForecast(id),
    enabled: Boolean(id),
  });
}

export function useCreateForecast() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ForecastCreateRequest) => forecastsApi.createForecast(body),
    onSuccess: (forecast) => {
      queryClient.invalidateQueries({ queryKey: forecastsKey() });
      queryClient.invalidateQueries({ queryKey: forecastsKey(forecast.dataset_id) });
    },
  });
}
