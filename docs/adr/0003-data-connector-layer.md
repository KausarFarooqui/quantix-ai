# ADR-0003: Data connector layer — sources, datasets, and ingestion

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Quantix AI engineering

## Context

Milestone 3 needed to bring external data into Quantix: file uploads
(CSV/Excel/JSON/Parquet) and live connections (Postgres, MySQL, SQL
Server, SQLite, Snowflake, BigQuery, Google Sheets) — eleven source types
in total, with more expected later. Two design questions shaped the
milestone: how do that many source types stay maintainable behind one
abstraction, and how does credential handling, schema inference, and
async ingestion fit into the existing Clean Architecture layering without
leaking infrastructure concerns upward.

## Decisions

**DataSource and Dataset are separate entities.** A `DataSource` is a
reusable connection or upload (config + encrypted secrets); a `Dataset`
is one materialized, queryable table pulled from it. This mirrors how
Power BI and Tableau separate a data source from an extract: one Postgres
`DataSource` can back many `Dataset`s (one per table synced), and
re-syncing a `Dataset` doesn't require re-entering credentials. File
uploads are modeled as a `DataSource` too (`SourceType.CSV`/etc. whose
`config` points at the stored file) rather than as a `Dataset`-only
shortcut, so a re-parse of the original bytes is always possible without
asking the user to re-upload.

**One `Connector` Protocol, four real implementations, eleven source
types.** `test_connection() / discover() / extract()` is the entire
surface every source type must satisfy. Rather than one class per source
type, dialect/format variation is handled inside a small number of
classes: `SqlDatabaseConnector` covers Postgres/MySQL/SQL
Server/SQLite/Snowflake by parameterizing SQLAlchemy's dialect and URL
construction; `FileConnector` covers CSV/Excel/JSON/Parquet by
dispatching on file extension internally. `BigQueryConnector` and
`GoogleSheetsConnector` stand alone since their APIs don't fit the
SQLAlchemy or pandas-file shape. Adding a twelfth source type is meant to
be a small, localized change: a new `SourceType` member, a connector
class (or a case inside an existing one, if it fits), and one entry in
`ConnectorRegistry`.

**`pyarrow.Table` is the lingua franca between connector and storage.**
Every connector's `extract()` returns a `pa.Table` regardless of source
(SQL result set, parsed CSV, BigQuery response, Sheets values) so the
ingestion pipeline, schema-inference, and storage layer only need to
understand one data structure. This required one deliberate, documented
exception to the "application layer never imports infrastructure/real
runtime libraries" rule: `application/interfaces/connector.py` imports
`pyarrow` directly, because pyarrow *is* the port's contract, not an
implementation detail — the alternative (an abstract application-layer
tabular type that every connector converts to/from) would add a
translation layer with no behavioral payoff.

**Credentials are encrypted at rest with a key independent of the JWT
signing key.** `DataSource.encrypted_secrets` is a Fernet ciphertext
(`FernetCredentialCipher`), keyed off a dedicated
`credential_encryption_key` setting — deliberately not `secret_key` (used
for JWTs), so the two can be rotated independently and a JWT key leak
doesn't also expose stored database passwords. Non-secret connection
parameters (host, port, database name, project ID) live in `config` as
plain JSON; only credentials go through the cipher.

**Ingestion has both a synchronous and an async (Celery) path, sharing
one code path underneath.** File uploads and small/first-time database
syncs run inline (`SyncDatasetUseCase.execute`): create the `Dataset` row
and ingest in the same request. Larger or explicitly-deferred syncs go
through `SyncDatasetUseCase.create_pending` (returns a `PENDING` dataset
immediately) followed by a Celery task that calls
`SyncDatasetUseCase.resync`. Both `execute` and `resync` funnel into the
same private `_run()`, which itself calls the shared
`ingest_into_dataset()` helper — so there's exactly one place that knows
how to go from a connector to a stored, schema-annotated `Dataset`,
regardless of which path triggered it. (This split fixed a real bug
caught in review: an earlier version had the async route call
`execute()` — which both creates *and* ingests — and *then* dispatch a
Celery task with the same parameters, silently producing two dataset rows
per "async" upload.)

**Blocking connector I/O runs via `anyio.to_thread.run_sync`, not a
separate async driver per source type.** `SqlDatabaseConnector` uses
synchronous SQLAlchemy/pandas calls (`pandas.read_sql`, blocking DB-API
drivers) because async drivers don't exist or aren't mature for several
of the five dialects it supports (pymssql, snowflake-sqlalchemy). Rather
than special-case each one, every connector call in the ingestion path is
offloaded to a thread via `anyio.to_thread.run_sync`, which works
identically whether the caller is a FastAPI async request handler or a
Celery task's own `asyncio.run()` loop.

**Celery tasks own a short-lived engine/session, not the API's.** Celery
workers are separate OS processes and can't share the FastAPI app's
request-scoped `AsyncSession`. `dataset_sync.py`'s task builds its own
engine and session factory per invocation (`asyncio.run()` wrapping an
async `_run()` helper), constructs its own `SyncDatasetUseCase` from
scratch, and disposes the engine when done — the use case itself has no
opinion about who calls it or what session it's handed, which is what
makes both call sites (route handler, Celery task) possible without the
use case importing anything Celery-specific.

**Datasets are stored as Parquet, queried through DuckDB.**
`DuckDBDatasetStorage.write()` persists the extracted `pa.Table` as a
Parquet file; `read_preview()` reads it back via
`duckdb.connect().execute("SELECT * FROM read_parquet(?) LIMIT ?", ...)`.
DuckDB was chosen over loading previews through pandas/pyarrow directly
because it can push the `LIMIT` down into the Parquet read rather than
materializing the whole file, and because it's the natural next step for
milestone-4-and-beyond query/analytics work over the same files.

## Alternatives considered

- **One connector class per source type (11 classes)** — rejected: most
  of the variation between SQL dialects and file formats is parametric
  (a URL scheme, a pandas reader function), not behavioral; 11 thin
  classes would mean 11 places to fix the same bug rather than one.
- **A DataSource-only model (no separate Dataset)** — rejected: collapses
  "where does this come from" and "this specific pulled table," making
  it impossible to sync multiple tables from one connection without
  duplicating credentials, and impossible to distinguish "connection is
  fine" from "this particular table's last pull failed."
- **An application-layer abstract tabular type instead of importing
  pyarrow directly in the port** — rejected: added an isomorphic
  translation layer (convert pyarrow → abstract type → pyarrow again for
  storage) for no behavioral benefit; documented as an explicit, narrow
  exception to the layering rule instead of worked around.
- **Async DB drivers per dialect (asyncpg, aiomysql, ...) instead of
  thread-offloaded sync drivers** — rejected: Snowflake and SQL Server
  don't have mature async SQLAlchemy support, which would have forced an
  inconsistent connector implementation strategy; `anyio.to_thread` gets
  non-blocking behavior uniformly across all five SQL dialects with one
  mechanism.
- **S3/GCS-backed storage from day one instead of local filesystem/DuckDB
  files** — rejected for this milestone: `FileStorage`/`DatasetStorage`
  are already ports with a single local implementation each
  (`LocalFileStorage`, `DuckDBDatasetStorage`); swapping in a
  cloud-backed implementation later is additive, not a rework, and doing
  it now would add deployment complexity (bucket provisioning, IAM)
  before it's needed for local development or single-instance deploys.

## Consequences

**Positive:** a new source type is a small, contained change; credential
compromise via the JWT key alone isn't possible; the ingestion code path
is identical whether triggered inline or from Celery, so it only needs
testing once; DuckDB-backed Parquet storage sets up milestone-4 query
work without a storage migration.

**Negative:** local filesystem storage (`LocalFileStorage`,
`DuckDBDatasetStorage`) doesn't work across multiple API replicas or
Celery workers on different hosts — acceptable for single-instance
deployment today, but tracked as a follow-up before horizontal scaling.
Thread-offloaded synchronous DB drivers mean a single blocking connector
call still consumes a worker thread for its duration; under heavy
concurrent sync load this is a coarser resource model than true async
drivers would give the two dialects (Postgres, MySQL) that do have them.
BigQuery and Google Sheets, as one-off connector implementations rather
than instances of the SQL/file pattern, will need individual attention if
their APIs change — there's no shared abstraction absorbing that the way
there is for the five SQL dialects.

**Follow-ups tracked for later milestones:** S3/GCS-backed
`FileStorage`/`DatasetStorage` implementations for multi-instance
deployment; incremental sync (currently every resync re-pulls the full
table); connector-level rate limiting and retry/backoff policies (BigQuery
and Sheets both have API quotas this milestone doesn't yet respect);
surfacing partial-schema-discovery errors (today `discover()` fails all-
or-nothing per data source) on a per-table basis instead.
