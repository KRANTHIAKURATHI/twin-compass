import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, FileUp, Loader2, UploadCloud } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

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
  component: UploadReports,
});

function UploadReports() {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState<string[]>([]);

  const simulateUpload = () => {
    // TODO(backend): POST /api/documents (multipart) → OCR queue
    setUploading(true);
    setProgress(0);
    const timer = setInterval(() => {
      setProgress((p) => {
        if (p >= 100) {
          clearInterval(timer);
          setUploading(false);
          setDone((d) => [`Report_${new Date().toISOString().slice(0, 10)}_${d.length + 1}.pdf`, ...d]);
          toast.success("Report uploaded", { description: "Your care team will review it after OCR extraction." });
          return 100;
        }
        return p + 20;
      });
    }, 220);
  };

  return (
    <div className="mx-auto max-w-[900px]">
      <PageHeader title="Upload Reports" description="Add scans, lab results or pathology documents. Files are encrypted and reviewed by your doctor." />

      <Card>
        <CardHeader>
          <CardTitle>New upload</CardTitle>
          <CardDescription>PDF, JPG or PNG up to 20 MB</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <button
            type="button"
            onClick={simulateUpload}
            disabled={uploading}
            className="flex w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border p-10 text-center transition-colors hover:border-primary hover:bg-primary-soft/40"
          >
            {uploading ? (
              <Loader2 className="size-8 animate-spin text-primary" aria-hidden="true" />
            ) : (
              <UploadCloud className="size-8 text-primary" aria-hidden="true" />
            )}
            <span className="mt-3 text-sm font-medium">{uploading ? "Uploading…" : "Click to select a file"}</span>
            <span className="text-xs text-muted-foreground">or drag and drop it here</span>
          </button>

          {uploading && <Progress value={progress} className="h-2" />}

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

          <Button onClick={simulateUpload} disabled={uploading}>
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
