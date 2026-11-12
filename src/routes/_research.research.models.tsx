import { createFileRoute } from "@tanstack/react-router";

import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { StatusChip } from "@/components/common/StatusChip";
import type { MLModel } from "@/types/models";
import { useResearchModels } from "@/hooks/api";

export const Route = createFileRoute("/_research/research/models")({
  head: () => ({
    meta: [
      { title: "Models — OncoTwin Research" },
      { name: "description", content: "Registry of research / prototype models (not clinically validated)." },
      { property: "og:title", content: "Models — OncoTwin Research" },
      { property: "og:description", content: "Registry of research / prototype models (not clinically validated)." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(ModelsPage, { variant: "table" }),
});

type Row = MLModel;

const columns: Column<Row>[] = [
  { key: "name", header: "Model", cell: (r) => <span className="font-medium">{r.name}</span> },
  { key: "version", header: "Version", cell: (r) => <StatusChip tone="neutral">{r.version}</StatusChip> },
  { key: "task", header: "Task", cell: (r) => r.task },
  { key: "auc", header: "AUC", cell: (r) => r.auc == null ? "—" : Number(r.auc).toFixed(2) },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusChip tone={r.status === "Production" ? "success" : "primary"}>{r.status}</StatusChip>,
  },
];

function ModelsPage() {
  const { data = [], isLoading, isError, refetch } = useResearchModels();
  return (
    <DataTablePage
      title="Models"
      description="Model registry. Entries are research / prototype models and are not clinically validated, whatever status is listed."
      columns={columns}
      rows={data}
      loading={isLoading}
      error={isError}
      onRetry={() => void refetch()}
      emptyTitle="No models registered"
      emptyDescription="No models are registered on the server yet."
    />
  );
}
