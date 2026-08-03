"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  useDataSource,
  useDeleteDataSource,
  useDiscoverDataSource,
  useSyncDatasetFromSource,
  useTestDataSource,
} from "@/features/connectors/hooks";
import { sourceTypeLabel } from "@/features/connectors/source-type-fields";
import { DataSourceStatusBadge } from "@/features/connectors/status-badge";
import { ApiError } from "@/lib/api-client";
import type { TableSchemaResponse } from "@/types/api";

export default function DataSourceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const dataSource = useDataSource(id);
  const testConnection = useTestDataSource(id);
  const deleteDataSource = useDeleteDataSource();
  const [discoverEnabled, setDiscoverEnabled] = React.useState(false);
  const discover = useDiscoverDataSource(id, { enabled: discoverEnabled });

  if (dataSource.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  if (dataSource.isError || !dataSource.data) {
    return (
      <p className="text-sm text-destructive">
        {dataSource.error instanceof ApiError ? dataSource.error.message : "Couldn't load this data source."}
      </p>
    );
  }

  const source = dataSource.data;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{source.name}</h1>
          <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            <span>{sourceTypeLabel(source.source_type)}</span>
            <DataSourceStatusBadge status={source.status} />
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="outline" onClick={() => testConnection.mutate()} disabled={testConnection.isPending}>
            {testConnection.isPending ? "Testing…" : "Test connection"}
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              if (
                window.confirm(`Delete "${source.name}"? This also deletes every dataset pulled from it.`)
              ) {
                deleteDataSource.mutate(source.id, { onSuccess: () => router.push("/data-sources") });
              }
            }}
            disabled={deleteDataSource.isPending}
          >
            Delete
          </Button>
        </div>
      </div>

      {testConnection.data && !testConnection.data.success && (
        <p className="text-sm text-destructive">{testConnection.data.error}</p>
      )}
      {source.last_test_error && !testConnection.data && (
        <p className="text-sm text-destructive">{source.last_test_error}</p>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Tables</CardTitle>
          <CardDescription>Pick a table, sheet, or write a query to pull into a dataset.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {!discoverEnabled && (
            <Button variant="outline" onClick={() => setDiscoverEnabled(true)} className="self-start">
              Discover tables
            </Button>
          )}

          {discoverEnabled && discover.isLoading && (
            <p className="text-sm text-muted-foreground">Discovering…</p>
          )}

          {discoverEnabled && discover.isError && (
            <p className="text-sm text-destructive">
              {discover.error instanceof ApiError ? discover.error.message : "Couldn't discover tables."}
            </p>
          )}

          {discoverEnabled && discover.data && discover.data.length === 0 && (
            <p className="text-sm text-muted-foreground">No tables found.</p>
          )}

          {discoverEnabled && discover.data && discover.data.length > 0 && (
            <div className="flex flex-col divide-y divide-border">
              {discover.data.map((table) => (
                <TableRow key={table.identifier} dataSourceId={source.id} table={table} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function TableRow({ dataSourceId, table }: { dataSourceId: string; table: TableSchemaResponse }) {
  const router = useRouter();
  const [datasetName, setDatasetName] = React.useState("");
  const syncDataset = useSyncDatasetFromSource(dataSourceId);

  return (
    <div className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="truncate font-mono text-sm">{table.identifier}</p>
        <p className="text-xs text-muted-foreground">
          {table.columns.length} columns
          {table.row_count_estimate !== null ? ` · ~${table.row_count_estimate} rows` : ""}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Input
          value={datasetName}
          onChange={(event) => setDatasetName(event.target.value)}
          placeholder={table.identifier}
          className="h-9 w-40"
        />
        <Button
          size="sm"
          disabled={syncDataset.isPending}
          onClick={() =>
            syncDataset.mutate(
              { table_identifier: table.identifier, dataset_name: datasetName.trim() || undefined },
              { onSuccess: (dataset) => router.push(`/datasets/${dataset.id}`) },
            )
          }
        >
          {syncDataset.isPending ? "Pulling…" : "Pull as dataset"}
        </Button>
      </div>
      {syncDataset.isError && (
        <p className="text-sm text-destructive">
          {syncDataset.error instanceof ApiError ? syncDataset.error.message : "Couldn't pull that table."}
        </p>
      )}
    </div>
  );
}
