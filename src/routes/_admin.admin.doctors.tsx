import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState } from "@/components/common/PageState";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { useDoctors } from "@/hooks/api";
import type { DoctorProfile } from "@/types/models";

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
  component: DoctorsPage,
});

type Row = DoctorProfile;

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
  const { data, isLoading, isError, refetch } = useDoctors();

  return (
    <DataTablePage
      title="Doctors"
      description="Clinician accounts across the network."
      columns={columns}
      rows={data ?? []}
      loading={isLoading}
      error={isError}
      onRetry={() => refetch()}
      actions={
        <Button
          onClick={() =>
            toast.info("Not yet available", { description: "There is no backend endpoint to invite a doctor yet." })
          }
        >
          <Plus className="size-4" aria-hidden="true" /> Invite doctor
        </Button>
      }
    />
  );
}
