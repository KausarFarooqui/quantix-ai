"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useDatasets, useDeleteDataset, useResyncDataset } from "@/features/connectors/hooks";
import { DatasetStatusBadge } from "@/features/connectors/status-badge";
import { ApiError } from "@/lib/api-client";
import type { DatasetResponse } from "@/types/api";

export default function DatasetsPage() {
  const datasets = useDatasets();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Datasets</h1>
          <p className="text-muted-foreground">Materialized, queryable tables.</p>
        </div>
        <Button asChild>
          <Link href="/datasets/upload">Upload a file</Link>
        </Button>
      </div>

      {datasets.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {datasets.isError && (
        <p className="text-sm text-destructive">
          {datasets.error instanceof ApiError ? datasets.error.message : "Couldn't load datasets."}
        </p>
      )}

      {datasets.data && datasets.data.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <p className="text-muted-foreground">No datasets yet.</p>
            <p className="text-sm text-muted-foreground">
              Upload a CSV/Excel/JSON/Parquet file, or{" "}
              <Link href="/data-sources" className="font-medium text-primary hover:underline">
                connect a data source
              </Link>{" "}
              and pull a table from it.
            </p>
            <Button asChild>
              <Link href="/datasets/upload">Upload a file</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {datasets.data && datasets.data.length > 0 && (
        <div className="flex flex-col divide-y divide-border rounded-lg border border-border">
          {datasets.data.map((dataset) => (
            <DatasetRow key={dataset.id} dataset={dataset} />
          ))}
        </div>
      )}
    </div>
  );
}

function DatasetRow({ dataset }: { dataset: DatasetResponse }) {
  const resync = useResyncDataset();
  const deleteDataset = useDeleteDataset();

  return (
    <div className="flex items-center justify-between gap-4 p-4">
      <div className="flex min-w-0 flex-col gap-1">
        <Link href={`/datasets/${dataset.id}`} className="truncate font-medium hover:underline">
          {dataset.name}
        </Link>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="truncate font-mono">{dataset.table_identifier}</span>
          <DatasetStatusBadge status={dataset.status} />
          {dataset.row_count !== null && <span>{dataset.row_count.toLocaleString()} rows</span>}
          {dataset.status_message && dataset.status === "failed" && (
            <span className="truncate text-destructive" title={dataset.status_message}>
              {dataset.status_message}
            </span>
          )}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => resync.mutate(dataset.id)} disabled={resync.isPending}>
          {resync.isPending ? "Syncing…" : "Resync"}
        </Button>
        <Button variant="outline" size="sm" asChild>
          <Link href={`/datasets/${dataset.id}`}>View</Link>
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            if (window.confirm(`Delete "${dataset.name}"?`)) {
              deleteDataset.mutate(dataset.id);
            }
          }}
          disabled={deleteDataset.isPending}
        >
          Delete
        </Button>
      </div>
    </div>
  );
}
