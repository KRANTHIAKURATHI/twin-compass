import { useRef, useState } from "react";
import { RouteErrorState } from "@/components/common/PageState";
import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, FileUp, Loader2, UploadCloud } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useUploadDocument, usePatients } from "@/hooks/api";

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
  component: UploadReports,
});

function UploadReports() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [done, setDone] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadDocument = useUploadDocument();
  const patientsQuery = usePatients();
  const me = patientsQuery.data?.[0];

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    setSelectedFile(file ?? null);
  };

  const handleSubmit = () => {
    if (!selectedFile) {
      fileInputRef.current?.click();
      return;
    }
    uploadDocument.mutate(
      { name: selectedFile.name, size: selectedFile.size, patientId: me?.id },
      {
        onSuccess: () => {
          setDone((d) => [selectedFile.name, ...d]);
          setSelectedFile(null);
          if (fileInputRef.current) fileInputRef.current.value = "";
        },
      },
    );
  };

  const uploading = uploadDocument.isPending;

  return (
    <div className="mx-auto max-w-[900px]">
      <PageHeader title="Upload Reports" description="Add scans, lab results or pathology documents. Files are encrypted and reviewed by your doctor." />

      <Card>
        <CardHeader>
          <CardTitle>New upload</CardTitle>
          <CardDescription>PDF, JPG or PNG up to 20 MB</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <input ref={fileInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden" onChange={handleFileChange} />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border p-10 text-center transition-colors hover:border-primary hover:bg-primary-soft/40"
          >
            {uploading ? (
              <Loader2 className="size-8 animate-spin text-primary" aria-hidden="true" />
            ) : (
              <UploadCloud className="size-8 text-primary" aria-hidden="true" />
            )}
            <span className="mt-3 text-sm font-medium">
              {uploading ? "Uploading…" : selectedFile ? selectedFile.name : "Click to select a file"}
            </span>
            <span className="text-xs text-muted-foreground">
              {selectedFile ? `${(selectedFile.size / 1024).toFixed(0)} KB selected` : "or drag and drop it here"}
            </span>
          </button>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="doc-type">Document type</Label>
              <Select defaultValue="MRI">
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
              <Textarea id="doc-note" rows={2} placeholder="Anything we should know about this report?" />
            </div>
          </div>

          <Button onClick={handleSubmit} disabled={uploading || !selectedFile}>
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
            {done.map((f, i) => (
              <div key={`${f}-${i}`} className="flex items-center gap-3 rounded-xl border border-border p-3">
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
