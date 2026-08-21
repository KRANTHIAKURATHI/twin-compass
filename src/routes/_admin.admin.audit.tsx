import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState } from "@/components/common/PageState";
import { Download } from "lucide-react";
import { toast } from "sonner";

import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { useAuditLogs } from "@/hooks/api";
import type { AuditLogEntry } from "@/types/models";

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
  component: AuditPage,
});

type Row = AuditLogEntry;

const columns: Column<Row>[] = [
  { key: "time", header: "Time", cell: (r) => <span className="text-muted-foreground">{r.time}</span> },
  {
    key: "actor",
    header: "Actor",
    cell: (r) => (
      <span className="font-medium">
        {r.actor}
        {r.actorRole && <span className="ml-1.5 text-xs font-normal text-muted-foreground">({r.actorRole})</span>}
      </span>
    ),
  },
  { key: "action", header: "Action", cell: (r) => r.action },
  { key: "target", header: "Target", cell: (r) => <StatusChip tone="neutral">{r.target}</StatusChip> },
  { key: "ip", header: "Source", cell: (r) => <span className="text-muted-foreground">{r.ip}</span> },
];

function AuditPage() {
  const { data, isLoading, isError, refetch } = useAuditLogs();

  return (
    <DataTablePage
      title="Audit logs"
      description="Append-only trail retained for seven years."
      columns={columns}
      rows={data ?? []}
      loading={isLoading}
      error={isError}
      onRetry={() => refetch()}
      actions={
        <Button
          variant="outline"
          onClick={() =>
            toast.info("Not yet available", { description: "There is no backend endpoint to export the audit log yet." })
          }
        >
          <Download className="size-4" aria-hidden="true" /> Export CSV
        </Button>
      }
    />
  );
}
