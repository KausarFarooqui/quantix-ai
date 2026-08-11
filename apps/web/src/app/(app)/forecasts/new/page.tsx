"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useDatasets } from "@/features/connectors/hooks";
import { useCreateForecast } from "@/features/forecasts/hooks";
import { ApiError } from "@/lib/api-client";

const NUMERIC_TYPES = new Set(["integer", "float"]);
const DEFAULT_PERIODS = 5;

export default function NewForecastPage() {
  const router = useRouter();
  const datasets = useDatasets();
  const createForecast = useCreateForecast();

  const readyDatasets = (datasets.data ?? []).filter((d) => d.status === "ready");

  const [datasetId, setDatasetId] = React.useState("");
  const [targetColumn, setTargetColumn] = React.useState("");
  const [timeColumn, setTimeColumn] = React.useState("");
  const [periods, setPeriods] = React.useState(String(DEFAULT_PERIODS));

  const selectedDataset = readyDatasets.find((d) => d.id === datasetId);
  const numericColumns = (selectedDataset?.schema ?? []).filter((c) =>
    NUMERIC_TYPES.has(c.data_type),
  );

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!datasetId || !targetColumn) return;

    createForecast.mutate(
      {
        dataset_id: datasetId,
        target_column: targetColumn,
        time_column: timeColumn || undefined,
        periods: Number(periods) || DEFAULT_PERIODS,
      },
      { onSuccess: (forecast) => router.push(`/forecasts/${forecast.id}`) },
    );
  }

  const errorMessage =
    createForecast.error instanceof ApiError
      ? createForecast.error.message
      : createForecast.error
        ? "Something went wrong — please try again."
        : null;

  return (
    <div className="mx-auto max-w-lg">
      <Card>
        <CardHeader>
          <CardTitle>New forecast</CardTitle>
          <CardDescription>
            Project a numeric column forward — Holt-Winters with a real prediction interval when
            there's enough history, a simpler linear-trend fallback otherwise.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit} noValidate>
          <CardContent className="flex flex-col gap-4">
            {errorMessage && (
              <Alert variant="destructive">
                <AlertDescription>{errorMessage}</AlertDescription>
              </Alert>
            )}

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="dataset">Dataset</Label>
              <Select
                id="dataset"
                value={datasetId}
                onChange={(event) => {
                  setDatasetId(event.target.value);
                  setTargetColumn("");
                  setTimeColumn("");
                }}
              >
                <option value="">Select a dataset…</option>
                {readyDatasets.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.name}
                  </option>
                ))}
              </Select>
              {datasets.data && readyDatasets.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No ready datasets yet — upload one first.
                </p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="targetColumn">Column to forecast</Label>
              <Select
                id="targetColumn"
                value={targetColumn}
                onChange={(event) => setTargetColumn(event.target.value)}
                disabled={!selectedDataset}
              >
                <option value="">Select a numeric column…</option>
                {numericColumns.map((column) => (
                  <option key={column.name} value={column.name}>
                    {column.name}
                  </option>
                ))}
              </Select>
              {selectedDataset && numericColumns.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  This dataset has no numeric columns to forecast.
                </p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="timeColumn">
                Sort by column <span className="text-muted-foreground">(optional)</span>
              </Label>
              <Select
                id="timeColumn"
                value={timeColumn}
                onChange={(event) => setTimeColumn(event.target.value)}
                disabled={!selectedDataset}
              >
                <option value="">Row order is already chronological</option>
                {(selectedDataset?.schema ?? [])
                  .filter((c) => c.name !== targetColumn)
                  .map((column) => (
                    <option key={column.name} value={column.name}>
                      {column.name}
                    </option>
                  ))}
              </Select>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="periods">Periods ahead</Label>
              <Input
                id="periods"
                type="number"
                min={1}
                max={52}
                value={periods}
                onChange={(event) => setPeriods(event.target.value)}
              />
            </div>

            <Button
              type="submit"
              disabled={createForecast.isPending || !datasetId || !targetColumn}
              className="mt-2"
            >
              {createForecast.isPending ? "Generating…" : "Generate forecast"}
            </Button>
          </CardContent>
        </form>
        <CardFooter className="justify-center text-sm text-muted-foreground">
          Uses up to the first 5,000 rows of the dataset.
        </CardFooter>
      </Card>
    </div>
  );
}
