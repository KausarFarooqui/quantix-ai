import type { ConnectableSourceType, SourceType } from "@/types/api";

export interface ConnectorField {
  key: string;
  label: string;
  /** Which half of `DataSourceCreateRequest` this value belongs in —
   * `config` is stored and returned as-is by the API, `secret` is
   * Fernet-encrypted server-side and never sent back (see ADR-0003).
   */
  kind: "config" | "secret";
  inputType: "text" | "number" | "password" | "textarea";
  required?: boolean;
  placeholder?: string;
  helpText?: string;
}

/**
 * What `POST /data-sources` needs per connectable source type, driving
 * both the rendered form fields and submit-time validation on
 * `app/(app)/data-sources/new/page.tsx`. Mirrors the config/secret keys
 * each connector actually reads:
 * `infrastructure/connectors/sql_connector.py` (`_build_url`/
 * `_build_snowflake_url`), `bigquery_connector.py`, and
 * `google_sheets_connector.py`.
 *
 * File types (csv/excel/json/parquet) have no entry here — see
 * `ConnectableSourceType`'s docstring in `types/api.ts`.
 */
export const CONNECTOR_FIELDS: Record<ConnectableSourceType, ConnectorField[]> = {
  postgresql: [
    { key: "host", label: "Host", kind: "config", inputType: "text", required: true },
    { key: "port", label: "Port", kind: "config", inputType: "number", placeholder: "5432" },
    { key: "database", label: "Database", kind: "config", inputType: "text" },
    { key: "username", label: "Username", kind: "secret", inputType: "text" },
    { key: "password", label: "Password", kind: "secret", inputType: "password" },
  ],
  mysql: [
    { key: "host", label: "Host", kind: "config", inputType: "text", required: true },
    { key: "port", label: "Port", kind: "config", inputType: "number", placeholder: "3306" },
    { key: "database", label: "Database", kind: "config", inputType: "text" },
    { key: "username", label: "Username", kind: "secret", inputType: "text" },
    { key: "password", label: "Password", kind: "secret", inputType: "password" },
  ],
  sql_server: [
    { key: "host", label: "Host", kind: "config", inputType: "text", required: true },
    { key: "port", label: "Port", kind: "config", inputType: "number", placeholder: "1433" },
    { key: "database", label: "Database", kind: "config", inputType: "text" },
    { key: "username", label: "Username", kind: "secret", inputType: "text" },
    { key: "password", label: "Password", kind: "secret", inputType: "password" },
  ],
  sqlite: [
    {
      key: "database",
      label: "File path",
      kind: "config",
      inputType: "text",
      required: true,
      helpText: "A path reachable from the API server, e.g. /data/analytics.db",
    },
  ],
  snowflake: [
    { key: "account", label: "Account identifier", kind: "config", inputType: "text", required: true },
    { key: "database", label: "Database", kind: "config", inputType: "text" },
    { key: "schema", label: "Schema", kind: "config", inputType: "text" },
    { key: "warehouse", label: "Warehouse", kind: "config", inputType: "text" },
    { key: "role", label: "Role", kind: "config", inputType: "text" },
    { key: "username", label: "Username", kind: "secret", inputType: "text" },
    { key: "password", label: "Password", kind: "secret", inputType: "password" },
  ],
  bigquery: [
    { key: "project_id", label: "GCP project ID", kind: "config", inputType: "text", required: true },
    { key: "dataset", label: "BigQuery dataset", kind: "config", inputType: "text" },
    {
      key: "service_account_json",
      label: "Service account JSON",
      kind: "secret",
      inputType: "textarea",
      helpText: "Leave blank to use Application Default Credentials on the API server.",
    },
  ],
  google_sheets: [
    { key: "spreadsheet_id", label: "Spreadsheet ID", kind: "config", inputType: "text", required: true },
    {
      key: "service_account_json",
      label: "Service account JSON",
      kind: "secret",
      inputType: "textarea",
      required: true,
    },
  ],
};

export const CONNECTABLE_SOURCE_TYPE_LABELS: Record<ConnectableSourceType, string> = {
  postgresql: "PostgreSQL",
  mysql: "MySQL",
  sql_server: "SQL Server",
  sqlite: "SQLite",
  snowflake: "Snowflake",
  bigquery: "BigQuery",
  google_sheets: "Google Sheets",
};

const FILE_SOURCE_TYPE_LABELS: Record<"csv" | "excel" | "json" | "parquet", string> = {
  csv: "CSV",
  excel: "Excel",
  json: "JSON",
  parquet: "Parquet",
};

const ALL_SOURCE_TYPE_LABELS: Record<SourceType, string> = {
  ...FILE_SOURCE_TYPE_LABELS,
  ...CONNECTABLE_SOURCE_TYPE_LABELS,
};

/** Human-readable label for any `SourceType`, connectable or file-based. */
export function sourceTypeLabel(sourceType: SourceType): string {
  return ALL_SOURCE_TYPE_LABELS[sourceType];
}
