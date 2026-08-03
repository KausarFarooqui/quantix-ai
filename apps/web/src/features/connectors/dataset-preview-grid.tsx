"use client";

import * as React from "react";
import { AgGridReact } from "ag-grid-react";
import { ClientSideRowModelModule, ModuleRegistry, type ColDef } from "ag-grid-community";

import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";

import type { DatasetColumnResponse } from "@/types/api";

// ag-grid 32's modular packaging requires registering the row-model
// module it uses — otherwise even the default client-side (in-memory)
// grid throws at render time. Registered once at module scope rather
// than per-render.
ModuleRegistry.registerModules([ClientSideRowModelModule]);

/**
 * Thin wrapper around `ag-grid-react` (already a scaffolded dependency —
 * see `package.json`) for dataset previews: sortable/resizable columns and
 * row virtualization matter here since a preview can still be a hundred
 * rows wide-ish, and a plain `<table>` doesn't give either for free.
 */
export function DatasetPreviewGrid({
  columns,
  rows,
}: {
  columns: DatasetColumnResponse[];
  rows: Record<string, unknown>[];
}) {
  const columnDefs = React.useMemo<ColDef[]>(
    () => columns.map((column) => ({ field: column.name, headerName: column.name, sortable: true, resizable: true })),
    [columns],
  );

  return (
    <div className="ag-theme-quartz h-[420px] w-full">
      <AgGridReact rowData={rows} columnDefs={columnDefs} defaultColDef={{ minWidth: 120 }} animateRows={false} />
    </div>
  );
}
