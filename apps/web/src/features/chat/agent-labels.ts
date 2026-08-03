import type { AgentType } from "@/types/api";

export const AGENT_TYPE_LABELS: Record<AgentType, string> = {
  supervisor: "Supervisor",
  data_ingestion: "Data ingestion",
  data_profiling: "Data profiling",
  data_cleaning: "Data cleaning",
  sql_generation: "SQL generation",
  python_analysis: "Python analysis",
  visualization: "Visualization",
  forecasting: "Forecasting",
  automl: "AutoML",
  recommendation: "Recommendation",
  executive_report: "Executive report",
  dashboard_builder: "Dashboard builder",
  explainable_ai: "Explainable AI",
};

export function agentTypeLabel(type: AgentType): string {
  return AGENT_TYPE_LABELS[type] ?? type;
}
