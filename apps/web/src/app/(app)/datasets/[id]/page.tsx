"use client";

import { useParams, useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DatasetPreviewGrid } from "@/features/connectors/dataset-preview-grid";
import { useDataset, useDatasetPreview, useDeleteDataset, useResyncDataset } from "@/features/connectors/hooks";
import { DatasetStatusBadge } from "@/features/connectors/status-badge";
import { ApiError } from "@/lib/api-client";

export default function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const dataset = useDataset(id);
  const resync = useResyncDataset();
  const deleteDataset = useDeleteDataset();
  // Hooks must run unconditionally every render, so readiness is derived
  // straight from the query cache rather than the `ds`/`isReady` locals
  // defined below (those only exist after the loading/error early returns).
  const preview = useDatasetPreview(id, 100, { enabled: dataset.data?.status === "ready" });

  if (dataset.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  if (dataset.isError || !dataset.data) {
    return (
      <p className="text-sm text-destructive">
        {dataset.error instanceof ApiError ? dataset.error.message : "Couldn't load this dataset."}
      </p>
    );
  }

  const ds = dataset.data;
  const isReady = ds.status === "ready";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{ds.name}</h1>
          <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            <span className="font-mono">{ds.table_identifier}</span>
            <DatasetStatusBadge status={ds.status} />
            {ds.row_count !== null && <span>{ds.row_count.toLocaleString()} rows</span>}
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="outline" onClick={() => resync.mutate(ds.id)} disabled={resync.isPending}>
            {resync.isPending ? "Syncing…" : "Resync"}
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              if (window.confirm(`Delete "${ds.name}"?`)) {
                deleteDataset.mutate(ds.id, { onSuccess: () => router.push("/datasets") });
              }
            }}
            disabled={deleteDataset.isPending}
          >
            Delete
          </Button>
        </div>
      </div>

      {ds.status === "failed" && ds.status_message && (
        <p className="text-sm text-destructive">{ds.status_message}</p>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Schema</CardTitle>
        </CardHeader>
        <CardContent>
          {ds.schema.length === 0 ? (
            <p className="text-sm text-muted-foreground">No schema recorded yet.</p>
          ) : (
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
              {ds.schema.map((column) => (
                <div key={column.name} className="flex items-center justify-between gap-2 border-b border-border py-1">
                  <span className="truncate font-mono">{column.name}</span>
                  <span className="shrink-0 text-muted-foreground">
                    {column.data_type}
                    {column.nullable ? "?" : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Preview</CardTitle>
        </CardHeader>
        <CardContent>
          {!isReady && (
            <p className="text-sm text-muted-foreground">
              This dataset isn&apos;t ready yet — preview becomes available once it finishes syncing.
            </p>
          )}
          {isReady && preview.isLoading && <p className="text-sm text-muted-foreground">Loading preview…</p>}
          {isReady && preview.isError && (
            <p className="text-sm text-destructive">
              {preview.error instanceof ApiError ? preview.error.message : "Couldn't load the preview."}
            </p>
          )}
          {isReady && preview.data && (
            <DatasetPreviewGrid columns={preview.data.dataset.schema} rows={preview.data.rows} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
