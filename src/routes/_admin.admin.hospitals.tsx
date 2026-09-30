import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Building2, Plus } from "lucide-react";
import { toast } from "sonner";

import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { StatCard } from "@/components/common/StatCard";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { hospitals } from "@/services/data";

export const Route = createFileRoute("/_admin/admin/hospitals")({
  head: () => ({
    meta: [
      { title: "Hospital Management — OncoTwin Admin" },
      { name: "description", content: "Manage hospital tenants, capacity and onboarding status across the OncoTwin network." },
      { property: "og:title", content: "Hospital Management — OncoTwin Admin" },
      { property: "og:description", content: "Manage hospital tenants, capacity and onboarding status across the OncoTwin network." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(HospitalsPage, { variant: "table" }),
});

type Row = (typeof hospitals)[number];

const columns: Column<Row>[] = [
  { key: "name", header: "Hospital", cell: (r) => <span className="font-medium">{r.name}</span> },
  { key: "city", header: "Location", cell: (r) => r.city },
  { key: "beds", header: "Beds", cell: (r) => r.beds },
  { key: "doctors", header: "Doctors", cell: (r) => r.doctors },
  { key: "patients", header: "Patients", cell: (r) => r.patients },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusChip tone={r.status === "Active" ? "success" : "warning"}>{r.status}</StatusChip>,
  },
];

function HospitalsPage() {
  return (
    <DataTablePage
      title="Hospital management"
      description="Tenants connected to the OncoTwin platform."
      columns={columns}
      rows={hospitals}
      actions={
        <Button onClick={() => toast.success("Hospital invited", { description: "TODO: wire POST /api/admin/hospitals" })}>
          <Plus className="size-4" aria-hidden="true" /> Add hospital
        </Button>
      }
    >
      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        <StatCard icon={Building2} label="Hospitals" value={String(hospitals.length)} />
        <StatCard icon={Building2} label="Total doctors" value={String(hospitals.reduce((a, h) => a + h.doctors, 0))} />
        <StatCard icon={Building2} label="Total patients" value={String(hospitals.reduce((a, h) => a + h.patients, 0))} />
      </div>
    </DataTablePage>
  );
}
