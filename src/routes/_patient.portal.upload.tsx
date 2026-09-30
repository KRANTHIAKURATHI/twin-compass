import { useRef, useState } from "react";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, FileUp, Loader2, UploadCloud } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/components/auth/AuthProvider";
import { useUploadDocument } from "@/hooks/api";

export const Route = createFileRoute("/_patient/portal/upload")({
  head: () => ({
    meta: [
      { title: "Upload Reports — OncoTwin Patient Portal" },
      { name: "description", content: "Securely upload scans, lab results and pathology reports for your care team." },
      { property: "og:title", content: "Upload Reports — OncoTwin Patient Portal" },
      { property: "og:description", content: "Securely upload scans, lab results and pathology reports for your care team." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(UploadReports, { variant: "list" }),
});

function UploadReports() {
  const { user } = useAuth();
  const upload = useUploadDocument();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState("MRI");
  const [note, setNote] = useState("");
  const [done, setDone] = useState<string[]>([]);

  // Documents are scoped to a `patients` row today; there is no link from a
  // patient-role account to one, so this always fails authorization until
  // that linkage exists (see Phase 6 report) — surfaced honestly below
  // rather than faked as a success.
  const patientId = user?.id ?? "";

  const handleSubmit = () => {
    if (!file) return;
    upload.mutate(
      { file, patientId, category },
      {
        onSuccess: (result) => {
          setDone((d) => [result.data?.name ?? file.name, ...d]);
          setFile(null);
          setNote("");
          if (fileRef.current) fileRef.current.value = "";
        },
      },
    );
  };

  return (
    <div className="mx-auto max-w-[900px]">
      <PageHeader title="Upload Reports" description="Add scans, lab results or pathology documents. Files are encrypted and reviewed by your doctor." />

      <Card>
        <CardHeader>
          <CardTitle>New upload</CardTitle>
          <CardDescription>PDF, JPG or PNG up to 25 MB</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={upload.isPending}
            className="flex w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border p-10 text-center transition-colors hover:border-primary hover:bg-primary-soft/40"
          >
            {upload.isPending ? (
              <Loader2 className="size-8 animate-spin text-primary" aria-hidden="true" />
            ) : (
              <UploadCloud className="size-8 text-primary" aria-hidden="true" />
            )}
            <span className="mt-3 text-sm font-medium">
              {upload.isPending ? "Uploading…" : file ? file.name : "Click to select a file"}
            </span>
            <span className="text-xs text-muted-foreground">or drag and drop it here</span>
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,image/jpeg,image/png"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="doc-type">Document type</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger id="doc-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {["MRI", "CT", "PET", "Biopsy", "Blood", "Other"].map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="doc-note">Note for your doctor</Label>
              <Textarea
                id="doc-note"
                rows={2}
                placeholder="Anything we should know about this report?"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>
          </div>

          <Button onClick={handleSubmit} disabled={!file || upload.isPending}>
            <FileUp className="size-4" aria-hidden="true" /> Submit report
          </Button>
        </CardContent>
      </Card>

      {done.length > 0 && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="text-base">Uploaded this session</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {done.map((f) => (
              <div key={f} className="flex items-center gap-3 rounded-xl border border-border p-3">
                <CheckCircle2 className="size-4 text-success" aria-hidden="true" />
                <span className="min-w-0 flex-1 truncate text-sm">{f}</span>
                <StatusChip tone="warning">Pending OCR</StatusChip>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
