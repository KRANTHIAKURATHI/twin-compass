import { useState } from "react";
import { PageErrorState, PageSkeleton, RouteErrorState, withPageStates } from "@/components/common/PageState";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Download, Eye, FileText, History, Search, Upload } from "lucide-react";

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
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Timeline } from "@/components/common/Timeline";
import { useDocumentTimeline, useDocumentVersions, useDocuments } from "@/hooks/api";
import { documentLinks } from "@/services/data";
import type { DocumentRecord } from "@/types/models";


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
  errorComponent: RouteErrorState,
  component: withPageStates(DocumentCenter, { variant: "list" }),
});

const categories = ["All", "MRI", "CT", "PET", "Biopsy", "Blood"] as const;

function DocumentCenter() {
  const [query, setQuery] = useState("");
  const [cat, setCat] = useState<string>("All");
  const [preview, setPreview] = useState<DocumentRecord | null>(null);
  const [history, setHistory] = useState<DocumentRecord | null>(null);

  const { data: documents = [], isLoading, isError, refetch } = useDocuments(query);

  const rows = documents.filter((d) => cat === "All" || d.category === cat);

  if (isLoading) return <PageSkeleton variant="list" />;
  if (isError)
    return (
      <div className="mx-auto max-w-[900px] pt-4">
        <PageErrorState onRetry={() => refetch()} />
      </div>
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
                  <span title="File storage not yet configured — metadata only">
                    <Button size="sm" variant="ghost" disabled>
                      <Download className="size-4" aria-hidden="true" /> Download
                    </Button>
                  </span>
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
          <div className="rounded-xl border border-border bg-surface p-5">
            <p className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <FileText className="size-4" aria-hidden="true" /> Document metadata
            </p>
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              {preview &&
                (
                  [
                    ["Category", preview.category],
                    ["Patient", preview.patient],
                    ["Date", preview.date],
                    ["Size", preview.size],
                    ["Version", `v${preview.version}`],
                    ["Status", preview.status],
                  ] as const
                ).map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-xs text-muted-foreground">{k}</dt>
                    <dd className="mt-0.5 text-sm font-medium">{v}</dd>
                  </div>
                ))}
            </dl>
            <p className="mt-4 text-xs text-muted-foreground">
              File storage is not yet configured for this environment — only document metadata is available, so no
              in-browser preview can be rendered.
            </p>
          </div>
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Linked records</p>
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" variant="outline" asChild>
                <Link to="/patients">Patient {preview?.patient}</Link>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <Link to="/digital-twins">Twin {documentLinks.twinVersion}</Link>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <Link to="/predictions">Prediction {documentLinks.prediction}</Link>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <Link to="/reports">Report {documentLinks.report}</Link>
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!history} onOpenChange={(o) => !o && setHistory(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Version history</DialogTitle>
            <DialogDescription>{history?.name}</DialogDescription>
          </DialogHeader>
          <HistoryDialogBody documentId={history?.id ?? ""} />
        </DialogContent>
      </Dialog>
    </div>
  );
}

function HistoryDialogBody({ documentId }: { documentId: string }) {
  const { data: versions = [], isLoading: versionsLoading } = useDocumentVersions(documentId);
  const { data: timeline = [], isLoading: timelineLoading } = useDocumentTimeline(documentId);

  return (
    <>
      {versionsLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full rounded-xl" />
          <Skeleton className="h-12 w-full rounded-xl" />
        </div>
      ) : (
        <ul className="space-y-3">
          {versions.map((v) => (
            <li key={v.version} className="flex gap-3 rounded-xl border border-border p-3">
              <StatusChip tone={v.version === versions[0]?.version ? "success" : "neutral"}>v{v.version}</StatusChip>
              <div>
                <p className="text-sm font-medium">{v.note}</p>
                <p className="text-xs text-muted-foreground">
                  {v.author} · {v.date}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
      <div>
        <p className="mb-3 mt-4 text-xs font-medium uppercase tracking-wide text-muted-foreground">Document timeline</p>
        {timelineLoading ? <Skeleton className="h-24 w-full rounded-xl" /> : <Timeline items={timeline} />}
      </div>
    </>
  );
}
