import { useEffect, useMemo, useState } from "react";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { createFileRoute } from "@tanstack/react-router";
import { AlertTriangle, CheckCircle2, FileText, RefreshCw, Sparkles, XCircle } from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useApproveOcr, useDocuments, useExtractOcr, useOcrFields, useRejectOcr } from "@/hooks/api";
import type { OcrField } from "@/types/models";

export const Route = createFileRoute("/_shell/ocr")({
  head: () => ({
    meta: [
      { title: "OCR Verification — OncoTwin" },
      { name: "description", content: "Extract clinical fields from an uploaded document and verify them before they update the digital twin." },
      { property: "og:title", content: "OCR Verification — OncoTwin" },
      { property: "og:description", content: "Extract clinical fields from an uploaded document and verify them before they update the digital twin." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(OcrPage, { variant: "detail" }),
});

// Fields OCR is allowed to write onto a patient (see backend
// `routers/ocr.py` FIELD_CATALOG) — the only ones with an approve checkbox.
// Anything else (patient name, study date, modality...) is shown for context
// but is never applied to the patient record.
const APPROVABLE_FIELDS = new Set([
  "tumor_size_mm",
  "er_status",
  "pr_status",
  "her2_status",
  "ki67",
  "grade",
  "nodes_involved",
  "stage",
  "diagnosed_on",
]);

function OcrPage() {
  const { hasAnyRole } = useAuth();
  const canReview = hasAnyRole(["doctor", "admin"]);

  const { data: documents = [], isLoading: documentsLoading } = useDocuments();
  const [documentId, setDocumentId] = useState("");

  const extraction = useOcrFields(documentId);
  const extract = useExtractOcr();
  const approve = useApproveOcr();
  const reject = useRejectOcr();

  const [edits, setEdits] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [rejectReason, setRejectReason] = useState("");
  const [rejecting, setRejecting] = useState(false);

  const fields = extraction.data?.fields ?? [];
  const status = extraction.data?.status;

  useEffect(() => {
    // Reset review state whenever the extraction result changes underneath us.
    setEdits(Object.fromEntries(fields.map((f) => [f.field, f.value ?? ""])));
    setChecked(new Set());
    setRejecting(false);
    setRejectReason("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extraction.data?.extractedAt, extraction.data?.status]);

  const selectedDocument = useMemo(() => documents.find((d) => d.id === documentId), [documents, documentId]);

  const approvableFields = fields.filter((f) => APPROVABLE_FIELDS.has(f.field));
  const anyChecked = checked.size > 0;

  const toggleField = (field: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(field)) next.delete(field);
      else next.add(field);
      return next;
    });
  };

  const handleApprove = () => {
    const approvedFields: OcrField[] = approvableFields
      .filter((f) => checked.has(f.field))
      .map((f) => ({ field: f.field, value: edits[f.field] ?? "", confidence: f.confidence ?? null }));
    approve.mutate({ documentId, fields: approvedFields });
  };

  const handleReject = () => {
    reject.mutate({ documentId, reason: rejectReason || undefined });
  };

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="OCR Verification"
        description="Every extracted value requires clinician verification before it reaches the digital twin."
        crumbs={[{ label: "Home", to: "/" }, { label: "OCR Verification" }]}
        actions={
          documentId && (
            <Button variant="outline" onClick={() => setDocumentId("")}>
              <RefreshCw className="size-4" aria-hidden="true" /> Choose another document
            </Button>
          )
        }
      />

      <Card className="mb-4">
        <CardContent className="pt-6">
          <div className="space-y-1.5">
            <Label htmlFor="ocr-document">Source document</Label>
            {documentsLoading ? (
              <Skeleton className="h-10 w-full rounded-md" />
            ) : (
              <select
                id="ocr-document"
                value={documentId}
                onChange={(e) => setDocumentId(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">Select an uploaded document…</option>
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} — {d.patient} ({d.date})
                  </option>
                ))}
              </select>
            )}
            <p className="text-xs text-muted-foreground">
              Upload documents from the Document Center first, then run OCR extraction here.
            </p>
          </div>
        </CardContent>
      </Card>

      {!documentId ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <FileText className="size-10 text-muted-foreground" aria-hidden="true" />
            <p className="mt-3 text-sm font-medium">Select a document to begin</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid items-start gap-4 lg:grid-cols-2">
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Source document</CardTitle>
              <CardDescription>{selectedDocument?.category ?? "Document"}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3 rounded-xl border border-border p-3">
                <FileText className="size-5 text-primary" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{selectedDocument?.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {selectedDocument?.patient} · {selectedDocument?.size} · v{selectedDocument?.version}
                  </p>
                </div>
                <StatusChip tone="neutral">{selectedDocument?.status}</StatusChip>
              </div>

              {!extraction.data && !extraction.isFetching && (
                <div className="mt-4 flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface py-10 text-center">
                  <Sparkles className="size-8 text-primary" aria-hidden="true" />
                  <p className="mt-3 text-sm font-medium">No extraction yet</p>
                  <p className="mt-1 text-xs text-muted-foreground">Run OCR to propose clinical fields for review.</p>
                  {canReview && (
                    <Button className="mt-4" onClick={() => extract.mutate(documentId)} disabled={extract.isPending}>
                      {extract.isPending ? "Extracting…" : "Extract fields"}
                    </Button>
                  )}
                </div>
              )}

              {extract.isError && (
                <div className="mt-4 flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <span>{extract.error?.message ?? "Extraction failed."}</span>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="flex h-full flex-col">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="size-4 text-primary" aria-hidden="true" /> Extracted fields
              </CardTitle>
              <CardDescription>
                {status === "Approved"
                  ? "Clinician verified — applied to the patient record."
                  : status === "Rejected"
                    ? "Rejected — the patient record was not changed."
                    : "Requires verification before it can update the patient."}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-1 flex-col space-y-3">
              {extraction.isFetching && (
                <div className="space-y-3">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-14 w-full rounded-xl" />
                  ))}
                </div>
              )}

              {!extraction.isFetching && extraction.data && (
                <>
                  {fields.map((f) => {
                    const approvable = APPROVABLE_FIELDS.has(f.field);
                    const isChecked = checked.has(f.field);
                    const noValue = !String(f.value ?? "").trim();
                    return (
                      <div
                        key={f.field}
                        className={cn(
                          "rounded-xl border p-3",
                          isChecked ? "border-success/40 bg-success/5" : "border-border",
                        )}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs text-muted-foreground">{f.label ?? f.field}</p>
                          <div className="flex items-center gap-2">
                            {f.status === "approved" && <StatusChip tone="success">Approved</StatusChip>}
                            {f.status === "rejected" && <StatusChip tone="neutral">Rejected</StatusChip>}
                            <StatusChip tone={f.confidence == null ? "neutral" : f.confidence >= 0.85 ? "success" : "warning"}>
                              {f.confidence == null ? "Confidence unavailable" : `${Math.round(f.confidence * 100)}% confidence`}
                            </StatusChip>
                          </div>
                        </div>
                        <div className="mt-2 flex items-center gap-2">
                          {approvable && canReview && status === "Extracted" ? (
                            <Checkbox
                              checked={isChecked}
                              onCheckedChange={() => toggleField(f.field)}
                              aria-label={`Approve ${f.label ?? f.field}`}
                              disabled={noValue}
                            />
                          ) : null}
                          <Input
                            value={edits[f.field] ?? ""}
                            onChange={(e) => setEdits((v) => ({ ...v, [f.field]: e.target.value }))}
                            aria-label={f.label ?? f.field}
                            disabled={!approvable || !canReview || status !== "Extracted"}
                          />
                        </div>
                        {!approvable && (
                          <p className="mt-1.5 text-xs text-muted-foreground">Informational — not applied to the patient record.</p>
                        )}
                      </div>
                    );
                  })}

                  {canReview && status === "Extracted" && (
                    <div className="space-y-3 pt-2">
                      {rejecting && (
                        <div className="space-y-1.5">
                          <Label htmlFor="reject-reason">Rejection reason (optional)</Label>
                          <Input
                            id="reject-reason"
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            placeholder="Why is this extraction being rejected?"
                          />
                        </div>
                      )}
                      <div className="flex flex-wrap items-center gap-2">
                        <Button onClick={handleApprove} disabled={!anyChecked || approve.isPending}>
                          <CheckCircle2 className="size-4" aria-hidden="true" />
                          {approve.isPending ? "Approving…" : "Approve & update digital twin"}
                        </Button>
                        {!rejecting ? (
                          <Button variant="outline" onClick={() => setRejecting(true)}>
                            <XCircle className="size-4" aria-hidden="true" /> Reject
                          </Button>
                        ) : (
                          <Button variant="destructive" onClick={handleReject} disabled={reject.isPending}>
                            {reject.isPending ? "Rejecting…" : "Confirm rejection"}
                          </Button>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {checked.size}/{approvableFields.length} fields selected for approval
                        </span>
                      </div>
                    </div>
                  )}

                  {status === "Approved" && (
                    <div className="flex items-center gap-3 rounded-xl border border-success/30 bg-success/10 p-4">
                      <CheckCircle2 className="size-5 text-success" aria-hidden="true" />
                      <div>
                        <p className="text-sm font-medium">Clinician verified — digital twin resynced</p>
                        <p className="text-xs text-muted-foreground">
                          Reviewed by {extraction.data.reviewedBy ?? "—"} at {extraction.data.reviewedAt ?? "—"}.
                        </p>
                      </div>
                    </div>
                  )}

                  {status === "Rejected" && (
                    <div className="flex items-center gap-3 rounded-xl border border-border bg-surface p-4">
                      <XCircle className="size-5 text-muted-foreground" aria-hidden="true" />
                      <div>
                        <p className="text-sm font-medium">Extraction rejected</p>
                        <p className="text-xs text-muted-foreground">{extraction.data.rejectReason || "No reason recorded."}</p>
                      </div>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
