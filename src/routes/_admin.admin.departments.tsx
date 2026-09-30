import { createFileRoute } from "@tanstack/react-router";

import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { departments } from "@/services/data";

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
  component: withPageStates(DepartmentsPage, { variant: "table" }),
});

type Row = (typeof departments)[number];

const columns: Column<Row>[] = [
  { key: "name", header: "Department", cell: (r) => <span className="font-medium">{r.name}</span> },
  { key: "head", header: "Head of service", cell: (r) => r.head },
  { key: "staff", header: "Staff", cell: (r) => r.staff },
  { key: "cases", header: "Active cases", cell: (r) => r.activeCases },
];

function DepartmentsPage() {
  return (
    <DataTablePage
      title="Departments"
      description="Service lines and their current workload."
      columns={columns}
      rows={departments}
    />
  );
}
