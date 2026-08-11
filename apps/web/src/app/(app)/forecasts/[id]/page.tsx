"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDataset } from "@/features/connectors/hooks";
import { ForecastChart } from "@/features/forecasts/forecast-chart";
import { useForecast } from "@/features/forecasts/hooks";
import { ApiError } from "@/lib/api-client";

const METHOD_LABEL: Record<string, string> = {
  holt_winters: "Holt-Winters",
  linear_trend: "Linear trend",
};

export default function ForecastDetailPage() {
  const { id } = useParams<{ id: string }>();
  const forecast = useForecast(id);
  const dataset = useDataset(forecast.data?.dataset_id ?? "");

  if (forecast.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  if (forecast.isError || !forecast.data) {
    return (
      <p className="text-sm text-destructive">
        {forecast.error instanceof ApiError ? forecast.error.message : "Couldn't load this forecast."}
      </p>
    );
  }

  const f = forecast.data;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold tracking-tight">{f.target_column}</h1>
          <Badge variant="secondary">{METHOD_LABEL[f.method] ?? f.method}</Badge>
        </div>
        <p className="text-muted-foreground">
          {dataset.data ? (
            <Link href={`/datasets/${dataset.data.id}`} className="hover:underline">
              {dataset.data.name}
            </Link>
          ) : (
            "…"
          )}
          {f.time_column && <> · sorted by {f.time_column}</>} · {f.historical_points} historical
          points · generated {new Date(f.created_at).toLocaleString()}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {f.points.length} period{f.points.length === 1 ? "" : "s"} ahead
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ForecastChart points={f.points} />
          <p className="mt-2 text-xs text-muted-foreground">
            {f.method === "holt_winters"
              ? "Shaded band is a 90% prediction interval from the Holt-Winters model."
              : "Shaded band is a heuristic range, not a statistically rigorous interval — " +
                "there wasn't enough history for the Holt-Winters model to fit."}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Values</CardTitle>
        </CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="py-1.5 font-medium">Period</th>
                <th className="py-1.5 font-medium">Forecast</th>
                <th className="py-1.5 font-medium">Range</th>
              </tr>
            </thead>
            <tbody>
              {f.points.map((point) => (
                <tr key={point.period} className="border-b border-border last:border-0">
                  <td className="py-1.5">+{point.period}</td>
                  <td className="py-1.5">{point.value.toFixed(2)}</td>
                  <td className="py-1.5 text-muted-foreground">
                    {point.lower.toFixed(2)} – {point.upper.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
