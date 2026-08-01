import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, FileText, RefreshCw, Sparkles, Upload } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { ocrFields } from "@/lib/mock-extra";

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
  component: OcrPage,
});

type Step = "upload" | "extracting" | "verify" | "approved";

const steps: { key: Step; label: string }[] = [
  { key: "upload", label: "Upload PDF" },
  { key: "extracting", label: "AI extraction" },
  { key: "verify", label: "Doctor verification" },
  { key: "approved", label: "Twin updated" },
];

function OcrPage() {
  const [step, setStep] = useState<Step>("upload");
  const [values, setValues] = useState(() => Object.fromEntries(ocrFields.map((f) => [f.field, f.value])));
  const [confirmed, setConfirmed] = useState<string[]>([]);
  const index = steps.findIndex((s) => s.key === step);

  const startExtraction = () => {
    setStep("extracting");
    setTimeout(() => setStep("verify"), 1600);
  };

  const approve = () => {
    setStep("approved");
    toast.success("Verified & twin updated", { description: "TODO: wire POST /api/ocr/{docId}/approve" });
  };

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="OCR Verification"
        description="Every extracted value is doctor-verified before it reaches the digital twin."
        crumbs={[{ label: "Home", to: "/" }, { label: "OCR Verification" }]}
        actions={
          step !== "upload" && (
            <Button
              variant="outline"
              onClick={() => {
                setStep("upload");
                setConfirmed([]);
              }}
            >
              <RefreshCw className="size-4" aria-hidden="true" /> Start over
            </Button>
          )
        }
      />

      <Card className="mb-4">
        <CardContent>
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
            <CardDescription>PDF upload and preview</CardDescription>
          </CardHeader>
          <CardContent>
            {step === "upload" ? (
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface p-10 text-center">
                <span className="flex size-12 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                  <Upload className="size-6" aria-hidden="true" />
                </span>
                <p className="mt-4 text-sm font-medium">Drop a pathology, imaging or lab PDF</p>
                <p className="mt-1 text-xs text-muted-foreground">PDF, PNG or JPG up to 25 MB</p>
                <Button className="mt-5" onClick={startExtraction}>
                  Select file
                </Button>
                <p className="mt-2 text-xs text-muted-foreground">TODO: wire POST /api/documents/upload</p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center gap-3 rounded-xl border border-border p-3">
                  <FileText className="size-5 text-primary" aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">MRI_Breast_2026_06.pdf</p>
                    <p className="text-xs text-muted-foreground">8.2 MB · 4 pages · uploaded just now</p>
                  </div>
                  <StatusChip tone="success">Uploaded</StatusChip>
                </div>
                <div className="flex h-72 flex-col items-center justify-center rounded-xl border border-border bg-surface text-center">
                  <FileText className="size-10 text-muted-foreground" aria-hidden="true" />
                  <p className="mt-3 text-sm font-medium">Page 1 preview</p>
                  <p className="text-xs text-muted-foreground">TODO: render PDF pages</p>
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
                <p className="text-sm text-muted-foreground">Running OCR field extractor v2.4…</p>
                <Progress value={62} className="h-2" />
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full rounded-xl" />
                ))}
              </div>
            )}

            {(step === "verify" || step === "approved") && (
              <>
                {ocrFields.map((f) => {
                  const low = f.confidence < 0.8;
                  const ok = confirmed.includes(f.field);
                  return (
                    <div
                      key={f.field}
                      className={`rounded-xl border p-3 ${low && !ok ? "border-warning/40 bg-warning/5" : "border-border"}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs text-muted-foreground">{f.field}</p>
                        <StatusChip tone={f.confidence >= 0.9 ? "success" : low ? "warning" : "primary"}>
                          {Math.round(f.confidence * 100)}% confidence
                        </StatusChip>
                      </div>
                      <div className="mt-2 flex items-center gap-2">
                        <Input
                          value={values[f.field]}
                          onChange={(e) => setValues((v) => ({ ...v, [f.field]: e.target.value }))}
                          aria-label={f.field}
                          disabled={step === "approved"}
                        />
                        <Button
                          size="icon"
                          variant={ok ? "default" : "outline"}
                          aria-label={`Confirm ${f.field}`}
                          disabled={step === "approved"}
                          onClick={() => setConfirmed((c) => (c.includes(f.field) ? c.filter((x) => x !== f.field) : [...c, f.field]))}
                        >
                          <CheckCircle2 className="size-4" aria-hidden="true" />
                        </Button>
                      </div>
                    </div>
                  );
                })}

                {step === "verify" ? (
                  <div className="flex flex-wrap items-center gap-2 pt-2">
                    <Button onClick={approve}>
                      <CheckCircle2 className="size-4" aria-hidden="true" /> Approve & update digital twin
                    </Button>
                    <Button variant="outline" onClick={() => setConfirmed(ocrFields.map((f) => f.field))}>
                      Confirm all
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
