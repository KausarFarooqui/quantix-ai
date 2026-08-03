"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useDataSources, useDeleteDataSource, useTestDataSource } from "@/features/connectors/hooks";
import { sourceTypeLabel } from "@/features/connectors/source-type-fields";
import { DataSourceStatusBadge } from "@/features/connectors/status-badge";
import { ApiError } from "@/lib/api-client";
import type { DataSourceResponse } from "@/types/api";

export default function DataSourcesPage() {
  const dataSources = useDataSources();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Data sources</h1>
          <p className="text-muted-foreground">Live connections datasets get pulled from.</p>
        </div>
        <Button asChild>
          <Link href="/data-sources/new">Add data source</Link>
        </Button>
      </div>

      {dataSources.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {dataSources.isError && (
        <p className="text-sm text-destructive">
          {dataSources.error instanceof ApiError
            ? dataSources.error.message
            : "Couldn't load data sources."}
        </p>
      )}

      {dataSources.data && dataSources.data.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <p className="text-muted-foreground">No data sources yet.</p>
            <p className="text-sm text-muted-foreground">
              Connect a database, BigQuery, or Google Sheets — or{" "}
              <Link href="/datasets/upload" className="font-medium text-primary hover:underline">
                upload a file
              </Link>{" "}
              to skip this step entirely.
            </p>
            <Button asChild>
              <Link href="/data-sources/new">Add data source</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {dataSources.data && dataSources.data.length > 0 && (
        <div className="flex flex-col divide-y divide-border rounded-lg border border-border">
          {dataSources.data.map((dataSource) => (
            <DataSourceRow key={dataSource.id} dataSource={dataSource} />
          ))}
        </div>
      )}
    </div>
  );
}

function DataSourceRow({ dataSource }: { dataSource: DataSourceResponse }) {
  const testConnection = useTestDataSource(dataSource.id);
  const deleteDataSource = useDeleteDataSource();

  return (
    <div className="flex items-center justify-between gap-4 p-4">
      <div className="flex min-w-0 flex-col gap-1">
        <Link href={`/data-sources/${dataSource.id}`} className="truncate font-medium hover:underline">
          {dataSource.name}
        </Link>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{sourceTypeLabel(dataSource.source_type)}</span>
          <DataSourceStatusBadge status={dataSource.status} />
          {dataSource.last_test_error && (
            <span className="truncate text-destructive" title={dataSource.last_test_error}>
              {dataSource.last_test_error}
            </span>
          )}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => testConnection.mutate()}
          disabled={testConnection.isPending}
        >
          {testConnection.isPending ? "Testing…" : "Test"}
        </Button>
        <Button variant="outline" size="sm" asChild>
          <Link href={`/data-sources/${dataSource.id}`}>View</Link>
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            if (window.confirm(`Delete "${dataSource.name}"? This also deletes every dataset pulled from it.`)) {
              deleteDataSource.mutate(dataSource.id);
            }
          }}
          disabled={deleteDataSource.isPending}
        >
          Delete
        </Button>
      </div>
    </div>
  );
}
