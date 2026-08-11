/**
 * Shared response/request types mirroring the backend's Pydantic schemas.
 * Kept hand-written for milestone 1; a later milestone will generate these
 * from the OpenAPI schema (`openapi-typescript`) to prevent drift.
 */

export interface ComponentStatus {
  name: string;
  healthy: boolean;
  detail?: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  environment: string;
  components: ComponentStatus[];
}

// --- Auth (mirrors apps/api/.../interface/api/v1/schemas/auth.py) ---

export type UserRole = "owner" | "admin" | "analyst" | "viewer";

export interface RegisterRequest {
  organization_name: string;
  email: string;
  password: string;
  full_name: string;
}

export interface LoginRequest {
  tenant_slug: string;
  email: string;
  password: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface LogoutRequest {
  refresh_token: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserPublic {
  id: string;
  tenant_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  is_email_verified: boolean;
}

// --- Data sources & datasets (mirrors .../schemas/connectors.py and
// domain/entities/{data_source,dataset}.py) ---

export type SourceType =
  | "csv"
  | "excel"
  | "json"
  | "parquet"
  | "postgresql"
  | "mysql"
  | "sql_server"
  | "sqlite"
  | "snowflake"
  | "bigquery"
  | "google_sheets";

/** Source types created via `POST /data-sources` + the connection-config
 * form. File types (csv/excel/json/parquet) are deliberately excluded —
 * they're only ever created by `POST /datasets/upload`, which infers the
 * type from the uploaded filename and self-creates the DataSource (see
 * `upload_file_dataset.py`); there's no config to fill in for them.
 */
export type ConnectableSourceType = Exclude<SourceType, "csv" | "excel" | "json" | "parquet">;

export type DataSourceStatus = "pending" | "active" | "error";
export type DatasetStatus = "pending" | "processing" | "ready" | "failed";
export type DatasetColumnType =
  | "string"
  | "integer"
  | "float"
  | "boolean"
  | "date"
  | "datetime"
  | "json";

export interface DataSourceCreateRequest {
  name: string;
  source_type: SourceType;
  config: Record<string, unknown>;
  secrets?: Record<string, unknown> | null;
}

export interface DataSourceResponse {
  id: string;
  name: string;
  source_type: SourceType;
  config: Record<string, unknown>;
  status: DataSourceStatus;
  last_tested_at: string | null;
  last_test_error: string | null;
  created_at: string;
}

export interface ConnectionTestResponse {
  success: boolean;
  error?: string | null;
}

export interface DatasetColumnResponse {
  name: string;
  data_type: DatasetColumnType;
  nullable: boolean;
}

export interface DatasetResponse {
  id: string;
  data_source_id: string;
  name: string;
  table_identifier: string;
  schema: DatasetColumnResponse[];
  row_count: number | null;
  size_bytes: number | null;
  status: DatasetStatus;
  status_message: string | null;
  last_synced_at: string | null;
  created_at: string;
}

export interface DatasetSyncRequest {
  table_identifier: string;
  dataset_name?: string | null;
  run_async?: boolean;
}

export interface DatasetPreviewResponse {
  dataset: DatasetResponse;
  rows: Record<string, unknown>[];
}

export interface TableSchemaResponse {
  identifier: string;
  columns: DatasetColumnResponse[];
  row_count_estimate: number | null;
}

// --- Conversations, messages, agent runs (mirrors .../schemas/agents.py and
// domain/entities/{conversation,message,agent_run}.py) ---

export type ConversationStatus = "active" | "archived";
export type MessageRole = "user" | "assistant" | "system";

/** Twelve specialist agents plus the supervisor that routes to them. The
 * supervisor's own runs are recorded for observability but never
 * user-facing (see its docstring in the backend enum) — UI that lists
 * "which agents worked on this" should filter it out. */
export type AgentType =
  | "supervisor"
  | "data_ingestion"
  | "data_profiling"
  | "data_cleaning"
  | "sql_generation"
  | "python_analysis"
  | "visualization"
  | "forecasting"
  | "automl"
  | "recommendation"
  | "executive_report"
  | "dashboard_builder"
  | "explainable_ai";

export type AgentRunStatus = "running" | "succeeded" | "failed";

export interface ConversationCreateRequest {
  title: string;
  dataset_id?: string | null;
}

export interface ConversationResponse {
  id: string;
  title: string;
  dataset_id: string | null;
  status: ConversationStatus;
  created_at: string;
}

export interface MessageCreateRequest {
  content: string;
}

export interface MessageResponse {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  agent_type: AgentType | null;
  created_at: string;
}

export interface AgentRunResponse {
  id: string;
  agent_type: AgentType;
  status: AgentRunStatus;
  output_summary: string | null;
  tool_calls: Record<string, unknown>[];
  prompt_tokens: number | null;
  completion_tokens: number | null;
  latency_ms: number | null;
  error_message: string | null;
  created_at: string;
}

/** Response of `POST /conversations/{id}/messages` — the backend runs the
 * full LangGraph turn synchronously (see ADR-0004: no SSE streaming yet)
 * and returns once it's done, so this always carries the assistant's
 * finished reply plus every specialist invocation from that turn. */
export interface SendMessageResponse {
  message: MessageResponse;
  agent_runs: AgentRunResponse[];
}

// --- Forecasts (mirrors apps/api/.../interface/api/v1/schemas/forecasts.py) ---

export type ForecastMethod = "holt_winters" | "linear_trend";

export interface ForecastCreateRequest {
  dataset_id: string;
  target_column: string;
  time_column?: string;
  periods?: number;
}

export interface ForecastPointResponse {
  period: number;
  value: number;
  lower: number;
  upper: number;
}

/** `points` covers only the forecasted horizon (`period` 1..N steps past
 * the last historical point) — the historical series itself isn't
 * returned here, only its count, so a forecast detail view can show the
 * projection and its interval but not a continuous historical+future
 * chart without a separate dataset preview call. */
export interface ForecastResponse {
  id: string;
  dataset_id: string;
  conversation_id: string | null;
  target_column: string;
  time_column: string | null;
  method: ForecastMethod;
  historical_points: number;
  points: ForecastPointResponse[];
  created_at: string;
}

