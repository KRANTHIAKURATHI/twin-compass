import { createFileRoute } from "@tanstack/react-router";

import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { StatusChip } from "@/components/common/StatusChip";
import type { Dataset } from "@/types/models";
import { useResearchDatasets } from "@/hooks/api";

export const Route = createFileRoute("/_research/research/datasets")({
  head: () => ({
    meta: [
      { title: "Datasets — OncoTwin Research" },
      { name: "description", content: "Training cohorts and public datasets used to fit and validate the twin models." },
      { property: "og:title", content: "Datasets — OncoTwin Research" },
      { property: "og:description", content: "Training cohorts and public datasets used to fit and validate the twin models." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(DatasetsPage, { variant: "table" }),
});

type Row = Dataset;

const columns: Column<Row>[] = [
  { key: "name", header: "Dataset", cell: (r) => <span className="font-medium">{r.name}</span> },
  { key: "records", header: "Records", cell: (r) => Number(r.records).toLocaleString() },
  { key: "modalities", header: "Modalities", cell: (r) => <StatusChip tone="neutral">{r.modalities}</StatusChip> },
  { key: "updated", header: "Last updated", cell: (r) => r.updated },
];

function DatasetsPage() {
  const { data = [], isLoading, isError, refetch } = useResearchDatasets();
  return (
    <DataTablePage
      title="Datasets"
      description="Cohorts available for training and validation."
      columns={columns}
      rows={data}
      loading={isLoading}
      error={isError}
      onRetry={() => void refetch()}
      emptyTitle="No datasets recorded"
      emptyDescription="No research datasets are registered on the server yet."
    />
  );
}
