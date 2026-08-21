import { useEffect, useState } from "react";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, FileText, RefreshCw, Sparkles, Upload, XCircle } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { StateNotice } from "@/components/common/StateNotice";
import { cn } from "@/lib/utils";
import { useApproveOcr, useExtractOcr, useOcrFields, useRejectOcr, useUploadDocument } from "@/hooks/api";


export const Route = createFileRoute("/_shell/ocr")({
  head: () => ({
    meta: [
      { title: "OCR Verification — OncoTwin" },
      { name: "description", content: "Upload a report, review AI-extracted clinical fields, verify them and update the digital twin." },
      { property: "og:title", content: "OCR Verification — OncoTwin" },
      { property: "og:description", content: "Upload a report, review AI-extracted clinical fields, verify them and update the digital twin." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(OcrPage, { variant: "detail" }),
});

type Step = "upload" | "extracting" | "verify" | "approved";

const steps: { key: Step; label: string }[] = [
  { key: "upload", label: "Upload PDF" },
  { key: "extracting", label: "AI extraction" },
  { key: "verify", label: "Doctor verification" },
  { key: "approved", label: "Twin updated" },
];

function formatBytes(bytes: number) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function OcrPage() {
  const [step, setStep] = useState<Step>("upload");
  const [documentId, setDocumentId] = useState("");
  const [fileName, setFileName] = useState("");
  const [fileSize, setFileSize] = useState(0);
  const [values, setValues] = useState<Record<string, string>>({});
  const [confirmed, setConfirmed] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const index = steps.findIndex((s) => s.key === step);

  const uploadMutation = useUploadDocument();
  const extractMutation = useExtractOcr();
  const approveMutation = useApproveOcr();
  const rejectMutation = useRejectOcr();

  const {
    data: ocrFields = [],
    isLoading: fieldsLoading,
    isError: fieldsError,
    refetch: refetchFields,
  } = useOcrFields(documentId);

  const allConfirmed = ocrFields.length > 0 && confirmed.length === ocrFields.length;

  // Seed editable values whenever a fresh set of extracted fields arrives.
  useEffect(() => {
    if (ocrFields.length) {
      setValues(Object.fromEntries(ocrFields.map((f) => [f.field, f.value])));
      setConfirmed([]);
    }
  }, [ocrFields]);

  // Purely cosmetic progress animation while the real extraction request is in flight.
  useEffect(() => {
    if (!extractMutation.isPending) return;
    setProgress(8);
    const timer = window.setInterval(() => {
      setProgress((p) => (p >= 96 ? 96 : p + 11));
    }, 180);
    return () => window.clearInterval(timer);
  }, [extractMutation.isPending]);

  const reset = () => {
    setStep("upload");
    setDocumentId("");
    setFileName("");
    setFileSize(0);
    setValues({});
    setConfirmed([]);
    setProgress(0);
  };

  const startExtraction = (file?: File) => {
    if (!file) return;
    setFileName(file.name);
    setFileSize(file.size);
    uploadMutation.mutate(
      { name: file.name, size: file.size },
      {
        onSuccess: (result) => {
          const id = result.data?.id;
          if (!id) {
            toast.error("Upload succeeded but no document id was returned");
            return;
          }
          setDocumentId(String(id));
          setStep("extracting");
          extractMutation.mutate(String(id), {
            onSuccess: () => {
              setProgress(100);
              setStep("verify");
            },
            onError: () => setStep("upload"),
          });
        },
        onError: () => reset(),
      },
    );
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    startExtraction(e.dataTransfer.files?.[0]);
  };

  const approve = () => {
    if (!allConfirmed) {
      toast.error("Confirm every field before approving");
      return;
    }
    const fields = ocrFields.map((f) => ({ ...f, value: values[f.field] ?? f.value }));
    approveMutation.mutate(
      { documentId, fields },
      { onSuccess: () => setStep("approved") },
    );
  };

  const reject = () => {
    rejectMutation.mutate(
      { documentId, reason: "Rejected by clinician during verification" },
      { onSuccess: () => reset() },
    );
  };

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="OCR Verification"
        description="Every extracted value is doctor-verified before it reaches the digital twin."
        crumbs={[{ label: "Home", to: "/" }, { label: "OCR Verification" }]}
        actions={
          step !== "upload" && (
            <Button variant="outline" onClick={reset}>
              <RefreshCw className="size-4" aria-hidden="true" /> Start over
            </Button>
          )
        }
      />

      <Card className="mb-4">
        <CardContent className="pb-4 pt-6">
          <ol className="flex flex-wrap items-center gap-x-3 gap-y-2">
            {steps.map((s, i) => (
              <li key={s.key} className="flex items-center gap-3">
                <span
                  className={`flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold leading-none ${
                    i <= index ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                  }`}
                >
                  {i < index ? <CheckCircle2 className="size-4" aria-hidden="true" /> : i + 1}
                </span>
                <span className={i <= index ? "text-sm font-medium leading-none" : "text-sm leading-none text-muted-foreground"}>
                  {s.label}
                </span>
                {i < steps.length - 1 && <span className="hidden h-px w-8 shrink-0 bg-border sm:block" aria-hidden="true" />}
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <div className="grid items-stretch gap-4 lg:grid-cols-2">
        <Card className="h-full">

          <CardHeader>
            <CardTitle>Source document</CardTitle>
            <CardDescription>Document upload &amp; metadata</CardDescription>
          </CardHeader>
          <CardContent>
            {step === "upload" ? (
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={cn(
                  "flex flex-col items-center justify-center rounded-xl border border-dashed p-10 text-center transition-colors",
                  dragging ? "border-primary bg-primary-soft/50" : "border-border bg-surface",
                )}
              >
                <span className="flex size-12 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                  <Upload className="size-6" aria-hidden="true" />
                </span>
                <p className="mt-4 text-sm font-medium">
                  {uploadMutation.isPending
                    ? "Uploading…"
                    : dragging
                      ? "Release to upload"
                      : "Drag & drop a pathology, imaging or lab PDF"}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">PDF, PNG or JPG up to 25 MB</p>
                <label className="mt-5 inline-flex cursor-pointer items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 aria-disabled:pointer-events-none aria-disabled:opacity-50">
                  Select file
                  <input
                    type="file"
                    className="sr-only"
                    accept=".pdf,.png,.jpg,.jpeg"
                    disabled={uploadMutation.isPending}
                    onChange={(e) => startExtraction(e.target.files?.[0])}
                  />
                </label>
                <p className="mt-2 text-xs text-muted-foreground">
                  Creates a document metadata record — file bytes are not stored by this backend yet.
                </p>
              </div>

            ) : (
              <div className="space-y-3">
                <div className="flex items-center gap-3 rounded-xl border border-border p-3">
                  <FileText className="size-5 text-primary" aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{fileName}</p>
                    <p className="text-xs text-muted-foreground">{formatBytes(fileSize)} · document id {documentId || "—"}</p>
                  </div>
                  <StatusChip tone="success">Uploaded</StatusChip>
                </div>
                <div className="flex h-72 flex-col items-center justify-center rounded-xl border border-border bg-surface p-6 text-center">
                  <FileText className="size-10 text-muted-foreground" aria-hidden="true" />
                  <p className="mt-3 text-sm font-medium">No in-browser file preview available</p>
                  <p className="mt-1 max-w-sm text-xs text-muted-foreground">
                    File storage is not yet configured for this environment — only extracted metadata is available.
                    Review the AI-extracted fields on the right.
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="flex h-full flex-col">

          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="size-4 text-primary" aria-hidden="true" /> AI-extracted fields
            </CardTitle>
            <CardDescription>Low-confidence fields are highlighted for review</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col space-y-3">
            {step === "upload" && (
              <p className="flex flex-1 items-center justify-center py-10 text-center text-sm text-muted-foreground">
                Upload a document to begin extraction.
              </p>
            )}


            {step === "extracting" && (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">Running OCR field extractor… {progress}%</p>
                <Progress value={progress} className="h-2" />
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full rounded-xl" />
                ))}
              </div>
            )}

            {step === "verify" && fieldsLoading && (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full rounded-xl" />
                ))}
              </div>
            )}

            {step === "verify" && fieldsError && (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 py-10 text-center">
                <p className="text-sm text-muted-foreground">Could not load extracted fields.</p>
                <Button variant="outline" size="sm" onClick={() => refetchFields()}>
                  <RefreshCw className="size-4" aria-hidden="true" /> Retry
                </Button>
              </div>
            )}

            {step === "verify" && !fieldsLoading && !fieldsError && !allConfirmed && <StateNotice state="waiting-verification" />}

            {(step === "verify" || step === "approved") && !fieldsLoading && !fieldsError && (
              <>
                {ocrFields.map((f) => {
                  const low = f.confidence < 0.8;
                  const ok = confirmed.includes(f.field);
                  const empty = !String(values[f.field] ?? "").trim();
                  return (
                    <div
                      key={f.field}
                      className={cn(
                        "rounded-xl border p-3",
                        empty
                          ? "border-destructive/50 bg-destructive/5"
                          : ok
                            ? "border-success/40 bg-success/5"
                            : low
                              ? "border-warning/40 bg-warning/5"
                              : "border-border",
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs text-muted-foreground">{f.field}</p>
                        <div className="flex items-center gap-2">
                          {ok && <StatusChip tone="success">Verified</StatusChip>}
                          <StatusChip tone={f.confidence >= 0.9 ? "success" : low ? "warning" : "primary"}>
                            {Math.round(f.confidence * 100)}% confidence
                          </StatusChip>
                        </div>
                      </div>
                      <div className="mt-2 flex items-center gap-2">
                        <Input
                          value={values[f.field] ?? ""}
                          onChange={(e) => setValues((v) => ({ ...v, [f.field]: e.target.value }))}
                          aria-label={f.field}
                          aria-invalid={empty}
                          aria-describedby={empty ? `${f.field}-error` : undefined}
                          disabled={step === "approved"}
                        />
                        <Button
                          size="icon"
                          variant={ok ? "default" : "outline"}
                          aria-label={`Confirm ${f.field}`}
                          disabled={step === "approved" || empty}
                          onClick={() => setConfirmed((c) => (c.includes(f.field) ? c.filter((x) => x !== f.field) : [...c, f.field]))}
                        >
                          <CheckCircle2 className="size-4" aria-hidden="true" />
                        </Button>
                      </div>
                      {empty && (
                        <p id={`${f.field}-error`} className="mt-1.5 text-xs text-destructive">
                          This field cannot be empty.
                        </p>
                      )}
                    </div>
                  );
                })}


                {step === "verify" ? (
                  <div className="flex flex-wrap items-center gap-2 pt-2">
                    <Button onClick={approve} disabled={!allConfirmed || approveMutation.isPending}>
                      <CheckCircle2 className="size-4" aria-hidden="true" /> Approve & update digital twin
                    </Button>
                    <Button variant="outline" onClick={() => setConfirmed(ocrFields.map((f) => f.field))}>
                      Confirm all
                    </Button>
                    <Button variant="ghost" className="text-destructive hover:text-destructive" onClick={reject} disabled={rejectMutation.isPending}>
                      <XCircle className="size-4" aria-hidden="true" /> Reject extraction
                    </Button>
                    <span className="text-xs text-muted-foreground">
                      {confirmed.length}/{ocrFields.length} fields confirmed
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center gap-3 rounded-xl border border-success/30 bg-success/10 p-4">
                    <CheckCircle2 className="size-5 text-success" aria-hidden="true" />
                    <div>
                      <p className="text-sm font-medium">Approved — digital twin updated</p>
                      <p className="text-xs text-muted-foreground">Predictions re-computed with the verified values.</p>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
