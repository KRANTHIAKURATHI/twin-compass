import { useState } from "react";
import { PageErrorState, PageSkeleton, RouteErrorState } from "@/components/common/PageState";
import { createFileRoute } from "@tanstack/react-router";
import { Download, Eye, FileText, Search } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useReports } from "@/hooks/api";

export const Route = createFileRoute("/_patient/portal/reports")({
  head: () => ({
    meta: [
      { title: "My Reports — OncoTwin Patient Portal" },
      { name: "description", content: "Browse, preview and download every medical report shared with your care team." },
      { property: "og:title", content: "My Reports — OncoTwin Patient Portal" },
      { property: "og:description", content: "Browse, preview and download every medical report shared with your care team." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: MyReports,
});

function MyReports() {
  const [q, setQ] = useState("");
  const reportsQuery = useReports();

  if (reportsQuery.isLoading) return <PageSkeleton variant="list" />;
  if (reportsQuery.isError) {
    return (
      <div className="mx-auto max-w-[900px] pt-4">
        <PageErrorState onRetry={() => reportsQuery.refetch()} />
      </div>
    );
  }

  const reports = reportsQuery.data ?? [];
  const rows = reports.filter((d) => `${d.title} ${d.type}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader title="My Reports" description="All documents you uploaded or that your care team shared with you." />

      <div className="relative mb-4 max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search reports…" className="pl-9" aria-label="Search reports" />
      </div>

      {rows.length === 0 ? (
        <EmptyState icon={FileText} title="No reports found" description="Try a different search term or upload a new report." />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {rows.map((d) => (
            <Card key={d.id} className="h-full">
              <CardContent className="flex h-full items-center gap-4 py-5">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                  <FileText className="size-5" aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium leading-tight">{d.title}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {d.type} · {d.created} · v{d.version}
                  </p>
                </div>
                <div className="ml-auto flex shrink-0 items-center gap-1">
                  <span className="hidden w-[112px] justify-start sm:flex">
                    <StatusChip tone={d.status === "Final" ? "success" : d.status === "Draft" ? "warning" : "risk"}>
                      {d.status}
                    </StatusChip>
                  </span>

                  <Button variant="ghost" size="icon" aria-label={`Preview ${d.title}`}>
                    <Eye className="size-4" aria-hidden="true" />
                  </Button>
                  <Button variant="ghost" size="icon" aria-label={`Download ${d.title}`}>
                    <Download className="size-4" aria-hidden="true" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
