import { authFetch } from "@/lib/api-client";
import type {
  ConnectionTestResponse,
  DataSourceCreateRequest,
  DataSourceResponse,
  DatasetPreviewResponse,
  DatasetResponse,
  DatasetSyncRequest,
  TableSchemaResponse,
} from "@/types/api";

/** Typed calls against `/data-sources/*` and `/datasets/*`. Every call
 * goes through `authFetch` — none of this is reachable without a session.
 */
export const connectorsApi = {
  listDataSources: () => authFetch<DataSourceResponse[]>("/data-sources"),

  getDataSource: (id: string) => authFetch<DataSourceResponse>(`/data-sources/${id}`),

  createDataSource: (body: DataSourceCreateRequest) =>
    authFetch<DataSourceResponse>("/data-sources", { method: "POST", body }),

  testDataSource: (id: string) =>
    authFetch<ConnectionTestResponse>(`/data-sources/${id}/test`, { method: "POST" }),

  discoverDataSource: (id: string) =>
    authFetch<TableSchemaResponse[]>(`/data-sources/${id}/discover`),

  syncDatasetFromSource: (id: string, body: DatasetSyncRequest) =>
    authFetch<DatasetResponse>(`/data-sources/${id}/datasets`, { method: "POST", body }),

  deleteDataSource: (id: string) => authFetch<void>(`/data-sources/${id}`, { method: "DELETE" }),

  listDatasets: () => authFetch<DatasetResponse[]>("/datasets"),

  getDataset: (id: string) => authFetch<DatasetResponse>(`/datasets/${id}`),

  uploadFileDataset: ({ file, datasetName }: { file: File; datasetName?: string }) => {
    const form = new FormData();
    form.append("file", file);
    if (datasetName) {
      form.append("dataset_name", datasetName);
    }
    // `apiFetch` special-cases a `FormData` body (see its docstring) —
    // sent as multipart with a browser-generated boundary, not JSON.
    return authFetch<DatasetResponse>("/datasets/upload", { method: "POST", body: form });
  },

  previewDataset: (id: string, limit = 100) =>
    authFetch<DatasetPreviewResponse>(`/datasets/${id}/preview?limit=${limit}`),

  resyncDataset: (id: string) => authFetch<DatasetResponse>(`/datasets/${id}/resync`, { method: "POST" }),

  deleteDataset: (id: string) => authFetch<void>(`/datasets/${id}`, { method: "DELETE" }),
};
