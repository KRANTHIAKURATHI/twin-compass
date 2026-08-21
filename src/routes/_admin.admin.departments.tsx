import { createFileRoute } from "@tanstack/react-router";

import { RouteErrorState } from "@/components/common/PageState";
import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { useDepartments } from "@/hooks/api";
import type { Department } from "@/types/models";

export const Route = createFileRoute("/_admin/admin/departments")({
  head: () => ({
    meta: [
      { title: "Departments — OncoTwin Admin" },
      { name: "description", content: "Departmental structure, heads of service, staffing levels and active caseloads." },
      { property: "og:title", content: "Departments — OncoTwin Admin" },
      { property: "og:description", content: "Departmental structure, heads of service, staffing levels and active caseloads." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: DepartmentsPage,
});

type Row = Department;

const columns: Column<Row>[] = [
  { key: "name", header: "Department", cell: (r) => <span className="font-medium">{r.name}</span> },
  { key: "head", header: "Head of service", cell: (r) => r.head },
  { key: "staff", header: "Staff", cell: (r) => r.staff },
  { key: "cases", header: "Active cases", cell: (r) => r.activeCases },
];

function DepartmentsPage() {
  const { data, isLoading, isError, refetch } = useDepartments();

  return (
    <DataTablePage
      title="Departments"
      description="Service lines and their current workload."
      columns={columns}
      rows={data ?? []}
      loading={isLoading}
      error={isError}
      onRetry={() => refetch()}
    />
  );
}
