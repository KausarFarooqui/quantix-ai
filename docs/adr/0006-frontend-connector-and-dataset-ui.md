# ADR-0006: Data source & dataset management UI

- **Status:** Accepted
- **Date:** 2026-08-03
- **Deciders:** Quantix AI engineering

## Context

Milestone 6 gives the frontend UI for everything milestone 3's backend
already supports: registering a live data source (Postgres, MySQL, SQL
Server, SQLite, Snowflake, BigQuery, Google Sheets), testing its
connection, discovering its tables, pulling a table into a Dataset,
uploading a file directly as a Dataset, and previewing/resyncing/deleting
datasets. The interesting design problem is the connection-config form:
seven connectable source types each want a different, non-overlapping set
of fields (a host/port/database/credentials shape for the five SQL
dialects, an account identifier for Snowflake, a project ID for BigQuery,
a spreadsheet ID for Google Sheets), all funneling into the same
`POST /data-sources` request body (`{ name, source_type, config, secrets
}`).

## Decisions

**A per-source-type field spec drives the form, not per-type React
components.** `features/connectors/source-type-fields.ts` maps each
`ConnectableSourceType` to a small declarative list (`key`, `label`,
`kind: "config" | "secret"`, `inputType`, `required`) mirrored from what
each connector's constructor actually reads
(`infrastructure/connectors/sql_connector.py`'s `_build_url`/
`_build_snowflake_url`, `bigquery_connector.py`, `google_sheets_connector.py`).
`app/(app)/data-sources/new/page.tsx` renders whatever list the selected
type points at, splits submitted values into `config` vs. `secrets` by
each field's `kind`, and validates required fields against the same list
— one form, seven shapes, no per-type branching in the component itself.
Adding an eighth connectable source type is a new entry in that map, not a
new form.

**That form uses plain React state, not `react-hook-form`.** Every other
form in this app (`/login`, `/register`) uses `react-hook-form` + `zod`
because their fields are fixed and known at compile time. This form's
field *set* changes at runtime based on a select input, which fits
`react-hook-form`'s typed, schema-driven API poorly — forcing it through a
zod discriminated union keyed on `source_type` would add real complexity
for a form that's fundamentally "loop over a list of strings and render an
input for each." Plain `useState<Record<string, string>>` plus a manual
required-fields check on submit is simpler and easier to follow for this
one dynamic case. Every other form in the app should still default to
`react-hook-form` + `zod`.

**File types never appear in that form.** `csv`/`excel`/`json`/`parquet`
are excluded from `ConnectableSourceType` entirely — `POST
/datasets/upload` infers the type from the uploaded filename and
self-creates the `DataSource` server-side
(`upload_file_dataset.py`), so there's no config to collect for them.
The "add a data source" form points users at `/datasets/upload` instead
for anything file-shaped, rather than pretending those types belong on
this form with zero fields.

**Dataset previews use `ag-grid-react`, already a scaffolded dependency.**
A plain HTML `<table>` doesn't give sortable/resizable columns or row
virtualization for free, both of which matter once a preview is a few
hundred rows. `ag-grid-community`/`ag-grid-react` were already in
`package.json` from the milestone-1 scaffold specifically for this;
milestone 6 is the first thing that actually uses them. ag-grid 32's
modular packaging requires registering `ClientSideRowModelModule` (done
once, at module scope, in `dataset-preview-grid.tsx`) — easy to miss and
the grid silently fails to render without it.

**Destructive actions use `window.confirm`, not a confirmation dialog
component.** Deleting a data source or dataset asks via the browser's
native `confirm()` rather than a styled modal. This app has no `Dialog`
primitive yet (see ADR-0005 — the same reasoning that skipped it for
milestone 5 applies here); building one just for a yes/no confirmation
isn't worth it yet. Revisit once a real modal need shows up (e.g. the
connection-config form as a dialog instead of a full page) and build the
primitive once, for every future caller.

**Query keys and cache invalidation live in `features/connectors/hooks.ts`,
one hook per operation.** Testing a connection, discovering tables, and
resyncing a dataset all invalidate the relevant list *and* detail query
keys rather than trying to hand-patch the cache — these responses don't
carry enough information to safely merge (e.g. `test_data_source`'s
response is just `{success, error}`, not the updated `DataSourceResponse`),
so refetching is both simpler and correct.

## Alternatives considered

- **Generate the config form from the backend's `DataSourceCreateRequest`
  JSON Schema via OpenAPI** — rejected for now: the backend's `config`/
  `secrets` fields are typed as `dict[str, Any]` (deliberately loose, since
  their shape depends on `source_type` in a way Pydantic doesn't model as
  a discriminated union today). There's no schema to generate *from* yet;
  revisit if the backend ever tightens this to per-type Pydantic models.
- **One page/component per source type** (`NewPostgresDataSourcePage`,
  `NewSnowflakeDataSourcePage`, ...) — rejected: seven near-identical pages
  differing only in which inputs they render is exactly the kind of
  duplication the milestone-3 connector registry pattern (ADR-0003)
  already rejected on the backend for the same reason.
- **A generic JSON textarea for `config`/`secrets` instead of a generated
  form** — rejected: technically simpler to build, but asks the user to
  hand-write JSON and know each connector's exact key names, which is a
  worse experience than the backend's own error messages already provide
  today (a whole point of building this UI at all).

## Consequences

**Positive:** adding a new connectable source type touches one file
(`source-type-fields.ts`) plus its backend connector — no new form
component. The preview grid is real infrastructure (sort/resize/virtualize)
rather than a placeholder table that would need replacing later.

**Negative:** the create-data-source form's manual validation (vs.
`zod`) means its error messages and required-field logic live outside the
pattern every other form in the app follows — a contributor skimming
`/login` first and then opening this file will notice the shift. Commented
in the ADR and in the file itself rather than left silent.
`window.confirm` blocks the JS event loop and can't be styled — acceptable
for now, tracked as the same "build a real `Dialog` primitive" follow-up
ADR-0005 already flagged.

**Follow-ups tracked for later milestones:** a `Dialog` primitive
(confirmations, the connection-config form as a modal instead of a full
page); surfacing the Celery-backed async sync path (`run_async: true` on
`DatasetSyncRequest`) in the UI — today the "pull as dataset" action
always runs inline; a "job in progress" indicator for datasets stuck in
`processing` (the UI shows the status but doesn't poll for completion).
