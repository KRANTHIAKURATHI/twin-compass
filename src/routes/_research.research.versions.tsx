import { createFileRoute } from "@tanstack/react-router";

import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { StatusChip } from "@/components/common/StatusChip";
import { modelVersions } from "@/services/data";

export const Route = createFileRoute("/_research/research/versions")({
  head: () => ({
    meta: [
      { title: "Model Versions — OncoTwin Research" },
      { name: "description", content: "Release history of the digital twin model suite with AUC and change notes." },
      { property: "og:title", content: "Model Versions — OncoTwin Research" },
      { property: "og:description", content: "Release history of the digital twin model suite with AUC and change notes." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(VersionsPage, { variant: "table" }),
});

type Row = (typeof modelVersions)[number];

const columns: Column<Row>[] = [
  { key: "version", header: "Version", cell: (r) => <span className="font-medium">{r.version}</span> },
  { key: "released", header: "Released", cell: (r) => r.released },
  { key: "auc", header: "AUC", cell: (r) => r.auc.toFixed(2) },
  { key: "notes", header: "Change notes", cell: (r) => <span className="text-muted-foreground">{r.notes}</span> },
  {
    key: "stage",
    header: "Stage",
    cell: (r) => <StatusChip tone={r.stage === "Production" ? "success" : "neutral"}>{r.stage}</StatusChip>,
  },
];

function VersionsPage() {
  return (
    <DataTablePage
      title="Model versions"
      description="Release history for the progression twin."
      columns={columns}
      rows={modelVersions.map((v) => ({ ...v, id: v.version }))}
    />
  );
}
