"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { connectorsApi } from "@/features/connectors/api";
import type { DataSourceCreateRequest, DatasetSyncRequest } from "@/types/api";

const dataSourcesKey = ["data-sources"] as const;
const dataSourceKey = (id: string) => ["data-sources", id] as const;
const discoverKey = (id: string) => ["data-sources", id, "discover"] as const;
const datasetsKey = ["datasets"] as const;
const datasetKey = (id: string) => ["datasets", id] as const;
const datasetPreviewKey = (id: string, limit: number) => ["datasets", id, "preview", limit] as const;

// --- Data sources ---

export function useDataSources() {
  return useQuery({ queryKey: dataSourcesKey, queryFn: connectorsApi.listDataSources });
}

export function useDataSource(id: string) {
  return useQuery({
    queryKey: dataSourceKey(id),
    queryFn: () => connectorsApi.getDataSource(id),
    enabled: Boolean(id),
  });
}

export function useCreateDataSource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: DataSourceCreateRequest) => connectorsApi.createDataSource(body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: dataSourcesKey }),
  });
}

export function useTestDataSource(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => connectorsApi.testDataSource(id),
    // Testing updates the data source's `status`/`last_tested_at` server
    // side even though this call's own response is just a pass/fail —
    // refetch rather than trying to patch the cache by hand.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dataSourcesKey });
      queryClient.invalidateQueries({ queryKey: dataSourceKey(id) });
    },
  });
}

export function useDiscoverDataSource(id: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: discoverKey(id),
    queryFn: () => connectorsApi.discoverDataSource(id),
    enabled: Boolean(id) && (options.enabled ?? true),
    staleTime: 60_000,
  });
}

export function useDeleteDataSource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => connectorsApi.deleteDataSource(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dataSourcesKey });
      queryClient.invalidateQueries({ queryKey: datasetsKey }); // deleting cascades to its datasets
    },
  });
}

export function useSyncDatasetFromSource(dataSourceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: DatasetSyncRequest) => connectorsApi.syncDatasetFromSource(dataSourceId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: datasetsKey }),
  });
}

// --- Datasets ---

export function useDatasets() {
  return useQuery({ queryKey: datasetsKey, queryFn: connectorsApi.listDatasets });
}

export function useDataset(id: string) {
  return useQuery({
    queryKey: datasetKey(id),
    queryFn: () => connectorsApi.getDataset(id),
    enabled: Boolean(id),
  });
}

export function useUploadFileDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    // Wrapped rather than passed directly: TanStack Query calls
    // `mutationFn(variables, context)` internally (`context` carries the
    // query client, mutation key, etc.) — passing `connectorsApi
    // .uploadFileDataset` as the mutationFn reference would silently
    // forward that second argument straight through to it.
    mutationFn: (variables: { file: File; datasetName?: string }) =>
      connectorsApi.uploadFileDataset(variables),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: datasetsKey }),
  });
}

export function useDatasetPreview(id: string, limit = 100, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: datasetPreviewKey(id, limit),
    queryFn: () => connectorsApi.previewDataset(id, limit),
    // Callers should pass `enabled: dataset.status === "ready"` — a
    // pending/processing/failed dataset has nothing to preview yet, and
    // `GET /datasets/{id}/preview` 4xxs for anything but a ready one.
    enabled: Boolean(id) && (options.enabled ?? true),
  });
}

export function useResyncDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => connectorsApi.resyncDataset(id),
    onSuccess: (dataset) => {
      queryClient.invalidateQueries({ queryKey: datasetsKey });
      queryClient.invalidateQueries({ queryKey: datasetKey(dataset.id) });
    },
  });
}

export function useDeleteDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => connectorsApi.deleteDataset(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: datasetsKey }),
  });
}
