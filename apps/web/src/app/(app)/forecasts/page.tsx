"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useDatasets } from "@/features/connectors/hooks";
import { useForecasts } from "@/features/forecasts/hooks";
import { ApiError } from "@/lib/api-client";
import type { ForecastResponse } from "@/types/api";

const METHOD_LABEL: Record<ForecastResponse["method"], string> = {
  holt_winters: "Holt-Winters",
  linear_trend: "Linear trend",
};

export default function ForecastsPage() {
  const forecasts = useForecasts();
  const datasets = useDatasets();
  const datasetNameById = new Map((datasets.data ?? []).map((d) => [d.id, d.name]));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Forecasts</h1>
          <p className="text-muted-foreground">
            Real projections of a numeric dataset column, with a prediction interval.
          </p>
        </div>
        <Button asChild>
          <Link href="/forecasts/new">New forecast</Link>
        </Button>
      </div>

      {forecasts.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {forecasts.isError && (
        <p className="text-sm text-destructive">
          {forecasts.error instanceof ApiError ? forecasts.error.message : "Couldn't load forecasts."}
        </p>
      )}

      {forecasts.data && forecasts.data.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <p className="text-muted-foreground">No forecasts yet.</p>
            <p className="text-sm text-muted-foreground">
              Pick a dataset and a numeric column to project it forward.
            </p>
            <Button asChild>
              <Link href="/forecasts/new">New forecast</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {forecasts.data && forecasts.data.length > 0 && (
        <div className="flex flex-col divide-y divide-border rounded-lg border border-border">
          {forecasts.data.map((forecast) => (
            <Link
              key={forecast.id}
              href={`/forecasts/${forecast.id}`}
              className="flex items-center justify-between gap-4 p-4 hover:bg-accent"
            >
              <div className="flex min-w-0 flex-col gap-1">
                <span className="truncate font-medium">
                  {forecast.target_column}
                  {forecast.time_column && (
                    <span className="text-muted-foreground"> by {forecast.time_column}</span>
                  )}
                </span>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="truncate">
                    {datasetNameById.get(forecast.dataset_id) ?? forecast.dataset_id}
                  </span>
                  <span>·</span>
                  <span>{METHOD_LABEL[forecast.method]}</span>
                  <span>·</span>
                  <span>{forecast.points.length} periods ahead</span>
                </div>
              </div>
              <span className="shrink-0 text-xs text-muted-foreground">
                {new Date(forecast.created_at).toLocaleString()}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
