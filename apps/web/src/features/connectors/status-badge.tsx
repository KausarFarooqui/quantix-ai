import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { DataSourceStatus, DatasetStatus } from "@/types/api";

const DATA_SOURCE_STATUS: Record<DataSourceStatus, { label: string; variant: BadgeProps["variant"] }> = {
  pending: { label: "Untested", variant: "secondary" },
  active: { label: "Active", variant: "success" },
  error: { label: "Error", variant: "destructive" },
};

const DATASET_STATUS: Record<DatasetStatus, { label: string; variant: BadgeProps["variant"] }> = {
  pending: { label: "Pending", variant: "secondary" },
  processing: { label: "Processing", variant: "warning" },
  ready: { label: "Ready", variant: "success" },
  failed: { label: "Failed", variant: "destructive" },
};

export function DataSourceStatusBadge({ status }: { status: DataSourceStatus }) {
  const { label, variant } = DATA_SOURCE_STATUS[status];
  return <Badge variant={variant}>{label}</Badge>;
}

export function DatasetStatusBadge({ status }: { status: DatasetStatus }) {
  const { label, variant } = DATASET_STATUS[status];
  return <Badge variant={variant}>{label}</Badge>;
}
