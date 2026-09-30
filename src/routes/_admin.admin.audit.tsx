import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Download } from "lucide-react";
import { toast } from "sonner";

import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { auditLogs } from "@/services/data";

export const Route = createFileRoute("/_admin/admin/audit")({
  head: () => ({
    meta: [
      { title: "Audit Logs — OncoTwin Admin" },
      { name: "description", content: "Immutable record of every clinical and administrative action on the platform." },
      { property: "og:title", content: "Audit Logs — OncoTwin Admin" },
      { property: "og:description", content: "Immutable record of every clinical and administrative action on the platform." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(AuditPage, { variant: "table" }),
});

type Row = (typeof auditLogs)[number];

const columns: Column<Row>[] = [
  { key: "time", header: "Time", cell: (r) => <span className="text-muted-foreground">{r.time}</span> },
  { key: "actor", header: "Actor", cell: (r) => <span className="font-medium">{r.actor}</span> },
  { key: "action", header: "Action", cell: (r) => r.action },
  { key: "target", header: "Target", cell: (r) => <StatusChip tone="neutral">{r.target}</StatusChip> },
  { key: "ip", header: "Source", cell: (r) => <span className="text-muted-foreground">{r.ip}</span> },
];

function AuditPage() {
  return (
    <DataTablePage
      title="Audit logs"
      description="Append-only trail retained for seven years."
      columns={columns}
      rows={auditLogs}
      actions={
        <Button variant="outline" onClick={() => toast.success("Export queued", { description: "TODO: wire GET /api/admin/audit/export" })}>
          <Download className="size-4" aria-hidden="true" /> Export CSV
        </Button>
      }
    />
  );
}
