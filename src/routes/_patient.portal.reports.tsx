import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Download, Eye, FileText, Search } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { documents } from "@/lib/mock-extra";

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
  component: MyReports,
});

function MyReports() {
  const [q, setQ] = useState("");
  const rows = documents.filter((d) => `${d.name} ${d.category}`.toLowerCase().includes(q.toLowerCase()));

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
            <Card key={d.id}>
              <CardContent className="flex items-center gap-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                  <FileText className="size-5" aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{d.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {d.category} · {d.date} · {d.size} · v{d.version}
                  </p>
                </div>
                <StatusChip tone={d.status === "Verified" ? "success" : d.status === "Pending OCR" ? "warning" : "risk"}>{d.status}</StatusChip>
                <Button variant="ghost" size="icon" aria-label={`Preview ${d.name}`}>
                  <Eye className="size-4" aria-hidden="true" />
                </Button>
                <Button variant="ghost" size="icon" aria-label={`Download ${d.name}`}>
                  <Download className="size-4" aria-hidden="true" />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
