import { createFileRoute } from "@tanstack/react-router";

import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { StatusChip } from "@/components/common/StatusChip";
import { trainingRuns } from "@/lib/mock-extra";

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
  component: TrainingPage,
});

type Row = (typeof trainingRuns)[number];

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
  return <DataTablePage title="Training history" description="Runs executed on the research cluster." columns={columns} rows={trainingRuns} />;
}
