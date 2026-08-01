import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Download, Eye, FileText, History, Search, Upload } from "lucide-react";
import { toast } from "sonner";

import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { documents } from "@/lib/mock-extra";

export const Route = createFileRoute("/_shell/documents")({
  head: () => ({
    meta: [
      { title: "Document Center — OncoTwin" },
      { name: "description", content: "Search, preview and version-track MRI, CT, PET, biopsy and blood reports across your patients." },
      { property: "og:title", content: "Document Center — OncoTwin" },
      { property: "og:description", content: "Search, preview and version-track MRI, CT, PET, biopsy and blood reports across your patients." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: DocumentCenter,
});

const categories = ["All", "MRI", "CT", "PET", "Biopsy", "Blood"] as const;

const versionHistory = [
  { v: 3, date: "2026-06-20", by: "Dr. Sarah Whitmore", note: "Approved OCR extraction" },
  { v: 2, date: "2026-06-20", by: "OCR Pipeline v2.4", note: "Re-parsed with improved model" },
  { v: 1, date: "2026-06-19", by: "Rui Mensah", note: "Original upload" },
];

function DocumentCenter() {
  const [query, setQuery] = useState("");
  const [cat, setCat] = useState<string>("All");
  const [preview, setPreview] = useState<(typeof documents)[number] | null>(null);
  const [history, setHistory] = useState<(typeof documents)[number] | null>(null);

  const rows = documents.filter(
    (d) =>
      (cat === "All" || d.category === cat) &&
      (d.name.toLowerCase().includes(query.toLowerCase()) || d.patient.toLowerCase().includes(query.toLowerCase())),
  );

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Document Center"
        description="Every imaging study, pathology report and lab document in one searchable library."
        crumbs={[{ label: "Home", to: "/" }, { label: "Documents" }]}
        actions={
          <Button asChild>
            <Link to="/ocr">
              <Upload className="size-4" aria-hidden="true" /> Upload & verify
            </Link>
          </Button>
        }
      />

      <Card className="mb-4">
        <CardContent className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search documents or patients…"
              aria-label="Search documents"
              className="pl-9"
            />
          </div>
          <Tabs value={cat} onValueChange={setCat}>
            <TabsList>
              {categories.map((c) => (
                <TabsTrigger key={c} value={c}>
                  {c}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </CardContent>
      </Card>

      {rows.length === 0 ? (
        <EmptyState icon={FileText} title="No documents found" description="Try another search term or category filter." />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((d) => (
            <Card key={d.id} className="hover-lift flex h-full flex-col">
              <CardContent className="flex flex-1 flex-col gap-4 px-5 pb-5 pt-6">
                <div className="flex items-start gap-3">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                    <FileText className="size-5" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{d.name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {d.patient} · {d.date} · {d.size}
                    </p>
                  </div>
                </div>
                <div className="flex min-h-7 flex-wrap items-center gap-2">
                  <StatusChip tone="neutral">{d.category}</StatusChip>
                  <StatusChip tone={d.status === "Verified" ? "success" : d.status === "Pending OCR" ? "primary" : "warning"}>
                    {d.status}
                  </StatusChip>
                  <StatusChip tone="neutral">v{d.version}</StatusChip>
                </div>
                <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
                  <Button size="sm" variant="outline" onClick={() => setPreview(d)}>
                    <Eye className="size-4" aria-hidden="true" /> Preview
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setHistory(d)}>
                    <History className="size-4" aria-hidden="true" /> Versions
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => toast.success("Download started", { description: "TODO: wire GET /api/documents/{id}/file" })}
                  >
                    <Download className="size-4" aria-hidden="true" /> Download
                  </Button>
                </div>

              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{preview?.name}</DialogTitle>
            <DialogDescription>
              {preview?.category} · {preview?.patient} · {preview?.date}
            </DialogDescription>
          </DialogHeader>
          <div className="flex h-80 flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface text-center">
            <FileText className="size-10 text-muted-foreground" aria-hidden="true" />
            <p className="mt-3 text-sm font-medium">PDF preview placeholder</p>
            <p className="text-xs text-muted-foreground">TODO: render document via GET /api/documents/{"{id}"}/preview</p>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!history} onOpenChange={(o) => !o && setHistory(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Version history</DialogTitle>
            <DialogDescription>{history?.name}</DialogDescription>
          </DialogHeader>
          <ul className="space-y-3">
            {versionHistory.map((v) => (
              <li key={v.v} className="flex gap-3 rounded-xl border border-border p-3">
                <StatusChip tone={v.v === versionHistory[0].v ? "success" : "neutral"}>v{v.v}</StatusChip>
                <div>
                  <p className="text-sm font-medium">{v.note}</p>
                  <p className="text-xs text-muted-foreground">
                    {v.by} · {v.date}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </DialogContent>
      </Dialog>
    </div>
  );
}
