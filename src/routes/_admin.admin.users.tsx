import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { UserPlus } from "lucide-react";
import { toast } from "sonner";

import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { platformUsers } from "@/services/data";

export const Route = createFileRoute("/_admin/admin/users")({
  head: () => ({
    meta: [
      { title: "Users — OncoTwin Admin" },
      { name: "description", content: "All platform accounts — doctors, patients, technicians and service identities." },
      { property: "og:title", content: "Users — OncoTwin Admin" },
      { property: "og:description", content: "All platform accounts — doctors, patients, technicians and service identities." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(UsersPage, { variant: "table" }),
});

type Row = (typeof platformUsers)[number];

const columns: Column<Row>[] = [
  { key: "name", header: "User", cell: (r) => <span className="font-medium">{r.name}</span> },
  { key: "email", header: "Email", cell: (r) => <span className="text-muted-foreground">{r.email}</span> },
  { key: "role", header: "Role", cell: (r) => <StatusChip tone="neutral">{r.role}</StatusChip> },
  { key: "last", header: "Last active", cell: (r) => r.lastActive },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusChip tone={r.status === "Active" ? "success" : "risk"}>{r.status}</StatusChip>,
  },
];

function UsersPage() {
  return (
    <DataTablePage
      title="Users"
      description="Every account with access to the platform."
      columns={columns}
      rows={platformUsers}
      actions={
        <Button onClick={() => toast.success("User invited", { description: "TODO: wire POST /api/admin/users" })}>
          <UserPlus className="size-4" aria-hidden="true" /> Add user
        </Button>
      }
    />
  );
}
