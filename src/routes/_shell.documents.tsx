import { useEffect, useRef, useState } from "react";
import { PageErrorState, RouteErrorState, withPageStates } from "@/components/common/PageState";
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Timeline } from "@/components/common/Timeline";
import {
  useDocumentLinks,
  useDocuments,
  useDocumentTimeline,
  useDocumentVersions,
  useDownloadDocument,
  usePatients,
  usePreviewDocument,
  useUploadDocument,
} from "@/hooks/api";
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
  const [uploadOpen, setUploadOpen] = useState(false);

  const { data: allDocuments = [], isLoading, isError, refetch } = useDocuments(query);

  const rows = allDocuments.filter((d) => cat === "All" || d.category === cat);

  if (isLoading) return <Skeleton className="h-[600px] rounded-2xl" />;

  if (isError) {
    return (
      <PageErrorState
        title="Couldn't load documents"
        description="We could not reach the server to load the document library. Check your connection and try again."
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Document Center"
        description="Every imaging study, pathology report and lab document in one searchable library."
        crumbs={[{ label: "Home", to: "/" }, { label: "Documents" }]}
        actions={
          <Button onClick={() => setUploadOpen(true)}>
            <Upload className="size-4" aria-hidden="true" /> Upload document
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
            <DocumentCard key={d.id} doc={d} onPreview={() => setPreview(d)} onHistory={() => setHistory(d)} />
          ))}
        </div>
      )}

      <PreviewDialog doc={preview} onClose={() => setPreview(null)} />
      <VersionsDialog doc={history} onClose={() => setHistory(null)} />
      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />
    </div>
  );
}

function DocumentCard({
  doc,
  onPreview,
  onHistory,
}: {
  doc: DocumentRecord;
  onPreview: () => void;
  onHistory: () => void;
}) {
  const download = useDownloadDocument();

  const handleDownload = async () => {
    const result = await download.mutateAsync(doc.id);
    // Signed URL — short-lived, private bucket. Opening it directly (rather
    // than fetching + blob) keeps the browser's own download handling intact.
    window.open(result.url, "_blank", "noopener,noreferrer");
  };

  return (
    <Card className="hover-lift flex h-full flex-col">
      <CardContent className="flex flex-1 flex-col gap-4 px-5 pb-5 pt-6">
        <div className="flex items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
            <FileText className="size-5" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{doc.name}</p>
            <p className="truncate text-xs text-muted-foreground">
              {doc.patient} · {doc.date} · {doc.size}
            </p>
          </div>
        </div>
        <div className="flex min-h-7 flex-wrap items-center gap-2">
          <StatusChip tone="neutral">{doc.category}</StatusChip>
          <StatusChip tone={doc.status === "Verified" ? "success" : doc.status === "Pending OCR" ? "primary" : "warning"}>
            {doc.status}
          </StatusChip>
          <StatusChip tone="neutral">v{doc.version}</StatusChip>
        </div>
        <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
          <Button size="sm" variant="outline" onClick={onPreview}>
            <Eye className="size-4" aria-hidden="true" /> Preview
          </Button>
          <Button size="sm" variant="ghost" onClick={onHistory}>
            <History className="size-4" aria-hidden="true" /> Versions
          </Button>
          <Button size="sm" variant="ghost" onClick={handleDownload} disabled={download.isPending}>
            <Download className="size-4" aria-hidden="true" /> {download.isPending ? "Preparing…" : "Download"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function PreviewDialog({ doc, onClose }: { doc: DocumentRecord | null; onClose: () => void }) {
  const { data: links } = useDocumentLinks(doc?.id ?? "");
  const previewMutation = usePreviewDocument();
  const [result, setResult] = useState<{ available: boolean; mimeType: string; url: string | null } | null>(null);

  const docId = doc?.id;
  useEffect(() => {
    if (!docId) return;
    setResult(null);
    previewMutation.mutate(docId, { onSuccess: (data) => setResult(data) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docId]);

  const handleClose = () => {
    setResult(null);
    previewMutation.reset();
    onClose();
  };

  return (
    <Dialog open={!!doc} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{doc?.name}</DialogTitle>
          <DialogDescription>
            {doc?.category} · {doc?.patient} · {doc?.date}
          </DialogDescription>
        </DialogHeader>
        <div className="flex h-72 flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface text-center">
          {previewMutation.isPending ? (
            <Skeleton className="size-full rounded-xl" />
          ) : result?.available && result.url && result.mimeType === "application/pdf" ? (
            <iframe src={result.url} title={doc?.name} className="size-full rounded-xl" />
          ) : result?.available && result.url ? (
            <img src={result.url} alt={doc?.name} className="max-h-full max-w-full rounded-xl object-contain" />
          ) : (
            <>
              <FileText className="size-10 text-muted-foreground" aria-hidden="true" />
              <p className="mt-3 text-sm font-medium">Preview unavailable</p>
              <p className="text-xs text-muted-foreground">
                {result?.mimeType ? `Files of type "${result.mimeType}" cannot be previewed here.` : "This file type cannot be previewed here."}
              </p>
            </>
          )}
        </div>
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Linked records</p>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="outline" asChild>
              <Link to="/patients">Patient {links?.patient ?? doc?.patient ?? "—"}</Link>
            </Button>
            {links?.twinVersion && (
              <Button size="sm" variant="outline" asChild>
                <Link to="/digital-twins">Twin {links.twinVersion}</Link>
              </Button>
            )}
            {links?.prediction && (
              <Button size="sm" variant="outline" asChild>
                <Link to="/predictions">Prediction {links.prediction}</Link>
              </Button>
            )}
            {links?.report && (
              <Button size="sm" variant="outline" asChild>
                <Link to="/reports">Report {links.report}</Link>
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function VersionsDialog({ doc, onClose }: { doc: DocumentRecord | null; onClose: () => void }) {
  const { data: versions = [], isLoading: versionsLoading, isError: versionsError } = useDocumentVersions(doc?.id ?? "");
  const { data: timeline = [] } = useDocumentTimeline(doc?.id ?? "");

  return (
    <Dialog open={!!doc} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Version history</DialogTitle>
          <DialogDescription>{doc?.name}</DialogDescription>
        </DialogHeader>
        {versionsLoading ? (
          <Skeleton className="h-40 rounded-xl" />
        ) : versionsError ? (
          <p className="py-8 text-center text-sm text-destructive">Couldn't load version history. Try again.</p>
        ) : versions.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">No versions recorded.</p>
        ) : (
          <ul className="space-y-3">
            {versions.map((v) => (
              <li key={v.version} className="flex gap-3 rounded-xl border border-border p-3">
                <StatusChip tone={v.version === versions[0].version ? "success" : "neutral"}>v{v.version}</StatusChip>
                <div>
                  <p className="text-sm font-medium">{v.note || "—"}</p>
                  <p className="text-xs text-muted-foreground">
                    {v.author} · {v.date}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
        {timeline.length > 0 && (
          <div>
            <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Document timeline</p>
            <Timeline items={timeline} />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function UploadDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { data: patients = [] } = usePatients();
  const upload = useUploadDocument();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [patientId, setPatientId] = useState("");
  const [category, setCategory] = useState("");

  const reset = () => {
    setFile(null);
    setPatientId("");
    setCategory("");
    if (fileRef.current) fileRef.current.value = "";
  };

  const handleSubmit = () => {
    if (!file || !patientId) return;
    upload.mutate(
      { file, patientId, category: category || undefined },
      {
        onSuccess: () => {
          reset();
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) reset();
        onOpenChange(o);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload document</DialogTitle>
          <DialogDescription>Attach an MRI, CT, PET, biopsy or lab report to a patient record.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="doc-patient">Patient</Label>
            <select
              id="doc-patient"
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">Select a patient…</option>
              {patients.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.id})
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="doc-category">Category (optional)</Label>
            <select
              id="doc-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">Unspecified</option>
              {categories.filter((c) => c !== "All").map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="doc-file">File</Label>
            <Input
              id="doc-file"
              ref={fileRef}
              type="file"
              accept="application/pdf,image/jpeg,image/png"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <p className="text-xs text-muted-foreground">PDF, JPEG or PNG. Max 25 MB.</p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!file || !patientId || upload.isPending}>
            {upload.isPending ? "Uploading…" : "Upload"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
