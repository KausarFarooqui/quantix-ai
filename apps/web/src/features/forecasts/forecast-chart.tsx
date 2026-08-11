"use client";

import ReactECharts from "echarts-for-react";

import type { ForecastPointResponse } from "@/types/api";

/**
 * Renders the forecasted horizon only — `points` is `period` 1..N steps
 * past the last historical point (see `ForecastResponse`'s docstring in
 * `types/api.ts`); there's no historical series to chart alongside it,
 * since the backend doesn't return raw row-level data through this
 * endpoint. The interval is shown as a shaded band using ECharts'
 * standard stacked-invisible-area technique: an invisible series at
 * `lower`, with a visible translucent area stacked on top sized to
 * `upper - lower`, so the band's top edge lands exactly at `upper`.
 */
export function ForecastChart({ points }: { points: ForecastPointResponse[] }) {
  const periods = points.map((p) => `+${p.period}`);
  const lower = points.map((p) => p.lower);
  const band = points.map((p) => p.upper - p.lower);
  const value = points.map((p) => p.value);

  const option = {
    backgroundColor: "transparent",
    grid: { left: 48, right: 24, top: 24, bottom: 32 },
    xAxis: {
      type: "category",
      data: periods,
      axisLine: { lineStyle: { color: "#52525b" } },
      axisLabel: { color: "#a1a1aa" },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      splitLine: { lineStyle: { color: "#27272a" } },
      axisLabel: { color: "#a1a1aa" },
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#18181b",
      borderColor: "#3f3f46",
      textStyle: { color: "#e4e4e7" },
      formatter: (params: { dataIndex: number }[]) => {
        const point = points[params[0]?.dataIndex ?? 0];
        if (!point) return "";
        return (
          `Period +${point.period}<br/>` +
          `Forecast: ${point.value.toFixed(2)}<br/>` +
          `Range: ${point.lower.toFixed(2)} – ${point.upper.toFixed(2)}`
        );
      },
    },
    series: [
      {
        name: "Lower bound",
        type: "line",
        data: lower,
        stack: "confidence-band",
        symbol: "none",
        lineStyle: { opacity: 0 },
        silent: true,
      },
      {
        name: "Range",
        type: "line",
        data: band,
        stack: "confidence-band",
        symbol: "none",
        lineStyle: { opacity: 0 },
        areaStyle: { color: "#6366f1", opacity: 0.15 },
        silent: true,
      },
      {
        name: "Forecast",
        type: "line",
        data: value,
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { color: "#818cf8", width: 2 },
        itemStyle: { color: "#818cf8" },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: 320, width: "100%" }} notMerge />;
}
