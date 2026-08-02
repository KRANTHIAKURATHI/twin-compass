import { createFileRoute } from "@tanstack/react-router";

import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { StatusChip } from "@/components/common/StatusChip";
import { models } from "@/lib/mock-extra";

export const Route = createFileRoute("/_research/research/models")({
  head: () => ({
    meta: [
      { title: "Models — OncoTwin Research" },
      { name: "description", content: "Production and staging models powering progression, survival, response and OCR extraction." },
      { property: "og:title", content: "Models — OncoTwin Research" },
      { property: "og:description", content: "Production and staging models powering progression, survival, response and OCR extraction." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(ModelsPage, { variant: "table" }),
});

type Row = (typeof models)[number];

const columns: Column<Row>[] = [
  { key: "name", header: "Model", cell: (r) => <span className="font-medium">{r.name}</span> },
  { key: "version", header: "Version", cell: (r) => <StatusChip tone="neutral">{r.version}</StatusChip> },
  { key: "task", header: "Task", cell: (r) => r.task },
  { key: "auc", header: "AUC", cell: (r) => r.auc.toFixed(2) },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusChip tone={r.status === "Production" ? "success" : "primary"}>{r.status}</StatusChip>,
  },
];

function ModelsPage() {
  return <DataTablePage title="Models" description="The model suite behind every twin and prediction." columns={columns} rows={models} />;
}
