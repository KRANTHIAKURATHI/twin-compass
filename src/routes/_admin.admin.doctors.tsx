import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { doctorsDirectory } from "@/services/data";

export const Route = createFileRoute("/_admin/admin/doctors")({
  head: () => ({
    meta: [
      { title: "Doctors Directory — OncoTwin Admin" },
      { name: "description", content: "Clinician accounts, departments and caseloads across every connected hospital." },
      { property: "og:title", content: "Doctors Directory — OncoTwin Admin" },
      { property: "og:description", content: "Clinician accounts, departments and caseloads across every connected hospital." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(DoctorsPage, { variant: "table" }),
});

type Row = (typeof doctorsDirectory)[number];

const columns: Column<Row>[] = [
  { key: "id", header: "ID", cell: (r) => <span className="text-muted-foreground">{r.id}</span> },
  { key: "name", header: "Doctor", cell: (r) => <span className="font-medium">{r.name}</span> },
  { key: "dept", header: "Department", cell: (r) => r.dept },
  { key: "hospital", header: "Hospital", cell: (r) => r.hospital },
  { key: "patients", header: "Patients", cell: (r) => r.patients },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusChip tone={r.status === "Active" ? "success" : "warning"}>{r.status}</StatusChip>,
  },
];

function DoctorsPage() {
  return (
    <DataTablePage
      title="Doctors"
      description="Clinician accounts across the network."
      columns={columns}
      rows={doctorsDirectory}
      actions={
        <Button onClick={() => toast.success("Invitation sent", { description: "TODO: wire POST /api/admin/doctors" })}>
          <Plus className="size-4" aria-hidden="true" /> Invite doctor
        </Button>
      }
    />
  );
}
