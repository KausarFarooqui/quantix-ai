"""Tools offered to specialized agents — bound to a specific dataset via
``AgentRunContext`` so each agent's tool loop only ever sees the data
its conversation is scoped to.

Every handler returns a plain string: the model reads tool results as
text, so structured data (schema, query rows) is JSON-serialized before
being handed back. Handlers are async so they can offload blocking
pandas/DuckDB work via ``anyio.to_thread.run_sync`` without stalling the
event loop, matching the pattern established for connector I/O in
milestone 3.
"""

from __future__ import annotations

import builtins
import contextlib
import io
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import anyio
import numpy as np

from quantix_api.application.interfaces.agent_graph import AgentRunContext
from quantix_api.application.interfaces.llm_client import ToolSpec
from quantix_api.domain.entities.dataset import Dataset
from quantix_api.domain.exceptions.forecasting import ForecastingError

MAX_QUERY_ROWS = 200
MAX_PYTHON_SAMPLE_ROWS = 5000

# Deliberately small, explicit allowlist — not a true security sandbox
# (see ADR-0004's "known limitations" section for why exec() can't fully
# be one), but it does stop the obvious things: no filesystem, network,
# process, or import access from agent-generated code.
_SAFE_BUILTINS: dict[str, Any] = {
    name: getattr(builtins, name)
    for name in (
        "len",
        "range",
        "sum",
        "min",
        "max",
        "abs",
        "round",
        "sorted",
        "list",
        "dict",
        "set",
        "tuple",
        "float",
        "int",
        "str",
        "bool",
        "enumerate",
        "zip",
        "map",
        "filter",
        "print",
        "isinstance",
    )
}


@dataclass(frozen=True, slots=True)
class ToolHandler:
    spec: ToolSpec
    call: Callable[[dict[str, Any]], Awaitable[str]]


def build_dataset_tools(context: AgentRunContext) -> list[ToolHandler]:
    """Tools available whenever the conversation is scoped to a ready
    dataset. Returns an empty list otherwise — agents fall back to asking
    the user to attach/sync a dataset first (see the agent system prompts
    in ``configs.py``).
    """
    dataset = context.dataset
    if dataset is None or not dataset.storage_uri:
        return []

    return [
        _schema_tool(dataset),
        _query_tool(context),
        _python_tool(context),
        _forecast_tool(context),
    ]


def _schema_tool(dataset: Dataset) -> ToolHandler:
    async def call(_arguments: dict[str, Any]) -> str:
        columns = [
            {"name": c.name, "type": c.data_type.value, "nullable": c.nullable}
            for c in dataset.schema
        ]
        return json.dumps({"table": "dataset", "row_count": dataset.row_count, "columns": columns})

    return ToolHandler(
        spec=ToolSpec(
            name="get_dataset_schema",
            description="Return the column names/types and row count of the dataset this "
            "conversation is scoped to. Call this before writing SQL or Python against it.",
            parameters={"type": "object", "properties": {}},
        ),
        call=call,
    )


def _query_tool(context: AgentRunContext) -> ToolHandler:
    dataset = context.dataset

    async def call(arguments: dict[str, Any]) -> str:
        sql = arguments.get("sql", "")
        try:
            table = await anyio.to_thread.run_sync(
                lambda: context.dataset_storage.query(
                    storage_uri=dataset.storage_uri, sql=sql, limit=MAX_QUERY_ROWS
                )
            )
        except Exception as exc:  # noqa: BLE001 — surfaced to the model as a tool error, not raised
            return f"Query failed: {exc}"
        rows = table.to_pylist()
        return json.dumps({"row_count": len(rows), "rows": rows}, default=str)

    return ToolHandler(
        spec=ToolSpec(
            name="query_dataset",
            description="Run a single read-only SELECT statement against the dataset, addressed "
            f"as the table `dataset` (e.g. `SELECT * FROM dataset LIMIT 10`). Capped at "
            f"{MAX_QUERY_ROWS} returned rows.",
            parameters={
                "type": "object",
                "properties": {"sql": {"type": "string", "description": "A SELECT statement."}},
                "required": ["sql"],
            },
        ),
        call=call,
    )


def _python_tool(context: AgentRunContext) -> ToolHandler:
    dataset = context.dataset

    async def call(arguments: dict[str, Any]) -> str:
        code = arguments.get("code", "")
        try:
            table = await anyio.to_thread.run_sync(
                lambda: context.dataset_storage.read_preview(
                    storage_uri=dataset.storage_uri, limit=MAX_PYTHON_SAMPLE_ROWS
                )
            )
            dataframe = table.to_pandas()
            output = await anyio.to_thread.run_sync(lambda: _exec_python(code, dataframe))
        except Exception as exc:  # noqa: BLE001 — a bad exec() should degrade, not crash the turn
            return f"Execution failed: {exc}"
        return output

    return ToolHandler(
        spec=ToolSpec(
            name="run_python_analysis",
            description="Execute pandas/numpy code against the dataset, available as `df` (a "
            f"sample of up to {MAX_PYTHON_SAMPLE_ROWS} rows) with `pd` and `np` pre-imported. "
            "Assign your answer to a variable named `result` and/or use print() — both are "
            "returned. No file, network, or import access is available.",
            parameters={
                "type": "object",
                "properties": {"code": {"type": "string", "description": "Python source to run."}},
                "required": ["code"],
            },
        ),
        call=call,
    )


def _exec_python(code: str, dataframe: Any) -> str:
    import pandas as pd

    namespace: dict[str, Any] = {
        "__builtins__": _SAFE_BUILTINS,
        "pd": pd,
        "np": np,
        "df": dataframe,
    }
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exec(code, namespace)  # noqa: S102 — see module docstring: best-effort, not a hard boundary
    printed = stdout.getvalue()
    result = namespace.get("result")
    parts = [
        p for p in (printed.strip(), f"result = {result!r}" if result is not None else "") if p
    ]
    return "\n".join(parts) or "(no output — assign to `result` or use print())"


def _forecast_tool(context: AgentRunContext) -> ToolHandler:
    dataset = context.dataset

    async def call(arguments: dict[str, Any]) -> str:
        column = arguments.get("column", "")
        periods = int(arguments.get("periods", 5))
        time_column = arguments.get("time_column") or None

        try:
            forecast = await context.generate_forecast_use_case.execute(
                tenant_id=context.tenant_id,
                actor_user_id=context.actor_user_id,
                conversation_id=context.conversation_id,
                dataset_id=dataset.id,
                target_column=column,
                periods=periods,
                time_column=time_column,
            )
        except ForecastingError as exc:
            return str(exc)
        except Exception as exc:  # noqa: BLE001 — surfaced to the model as a tool result, not raised
            return f"Could not forecast column '{column}': {exc}"

        return json.dumps(
            {
                "forecast_id": str(forecast.id),
                "method": forecast.method.value,
                "historical_points": forecast.historical_points,
                "forecast": [
                    {"period": p.period, "value": p.value, "lower": p.lower, "upper": p.upper}
                    for p in forecast.points
                ],
            }
        )

    return ToolHandler(
        spec=ToolSpec(
            name="forecast_series",
            description="Forecast the next N values of a numeric dataset column and persist the "
            "result. Uses Holt-Winters exponential smoothing (with a real prediction interval) "
            "when there's enough history, falling back to a simpler linear-trend extrapolation "
            "for short series — the response's 'method' field says which one was actually used.",
            parameters={
                "type": "object",
                "properties": {
                    "column": {"type": "string"},
                    "periods": {"type": "integer", "default": 5},
                    "time_column": {
                        "type": "string",
                        "description": "Optional column to sort by first, if the dataset's row "
                        "order doesn't already reflect chronological order.",
                    },
                },
                "required": ["column"],
            },
        ),
        call=call,
    )
