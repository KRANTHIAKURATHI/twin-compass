import { createFileRoute } from "@tanstack/react-router";

import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { StatusChip } from "@/components/common/StatusChip";
import type { TrainingRun } from "@/types/models";
import { useResearchTrainingRuns } from "@/hooks/api";

export const Route = createFileRoute("/_research/research/training")({
  head: () => ({
    meta: [
      { title: "Training History — OncoTwin Research" },
      { name: "description", content: "Every training run with duration, epochs, final loss and completion status." },
      { property: "og:title", content: "Training History — OncoTwin Research" },
      { property: "og:description", content: "Every training run with duration, epochs, final loss and completion status." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(TrainingPage, { variant: "table" }),
});

type Row = TrainingRun;

const columns: Column<Row>[] = [
  { key: "id", header: "Run", cell: (r) => <span className="font-medium">{r.id}</span> },
  { key: "model", header: "Model", cell: (r) => r.model },
  { key: "started", header: "Started", cell: (r) => <span className="text-muted-foreground">{r.started}</span> },
  { key: "duration", header: "Duration", cell: (r) => r.duration },
  { key: "epochs", header: "Epochs", cell: (r) => r.epochs },
  { key: "loss", header: "Final loss", cell: (r) => r.loss },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusChip tone={r.status === "Completed" ? "success" : "risk"}>{r.status}</StatusChip>,
  },
];

function TrainingPage() {
  const { data = [], isLoading, isError, refetch } = useResearchTrainingRuns();
  return (
    <DataTablePage
      title="Training history"
      description="Training runs recorded on the server."
      columns={columns}
      rows={data}
      loading={isLoading}
      error={isError}
      onRetry={() => void refetch()}
      emptyTitle="No training runs recorded"
      emptyDescription="No model training runs have been recorded yet."
    />
  );
}
