import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Layers } from "lucide-react";

import { NotConnectedPage } from "@/components/common/NotConnectedPage";

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

function DepartmentsPage() {
  return (
    <NotConnectedPage
      title="Departments"
      description="Service lines and their current workload."
      icon={Layers}
      what="Departments"
    />
  );
}
