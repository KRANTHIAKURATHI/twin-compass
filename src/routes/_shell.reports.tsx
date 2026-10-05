import { useEffect, useMemo, useState } from "react";
import { PageErrorState, RouteErrorState, withPageStates } from "@/components/common/PageState";
import { createFileRoute } from "@tanstack/react-router";
import { Download, FileSpreadsheet, FileText, Printer, Sparkles } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { RiskChip, StatusChip } from "@/components/common/StatusChip";
import { Timeline } from "@/components/common/Timeline";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useDownloadHistory,
  useExportReport,
  useGenerateReport,
  usePatients,
  useReport,
  useReports,
  useReportVersions,
} from "@/hooks/api";
import type { ReportDetail, RiskLevel } from "@/types/models";

export const Route = createFileRoute("/_shell/reports")({
  head: () => ({
    meta: [
      { title: "Clinical Reports — OncoTwin" },
      { name: "description", content: "Generate patient, digital twin, prediction and treatment comparison reports." },
      { property: "og:title", content: "Clinical Reports — OncoTwin" },
      { property: "og:description", content: "Generate patient, digital twin, prediction and treatment comparison reports." },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(ReportsPage, { variant: "list" }),
});

const REPORT_TYPES = ["Clinical summary", "Tumor board packet", "Model audit", "Cohort summary"] as const;

function reportToCsv(report: ReportDetail): string {
  const c = report.content;
  const lines: string[] = [];
  lines.push(`Report,${report.title}`);
  lines.push(`Version,${report.version}`);
  lines.push(`Generated,${report.created}`);
  lines.push("");
  lines.push("Section,Field,Value");
  lines.push(`Patient,Name,${c.patient.name}`);
  lines.push(`Patient,Patient ID,${c.patient.patientId}`);
  lines.push(`Patient,Stage,${c.patient.stage ?? ""}`);
  lines.push(`Patient,Tumor size (mm),${c.patient.tumorSizeMm ?? ""}`);
  lines.push(`Patient,Treatment,${c.patient.currentTreatment ?? ""}`);
  if (c.digitalTwin) {
    lines.push(`Digital twin,Version,${c.digitalTwin.version}`);
    lines.push(`Digital twin,Status,${c.digitalTwin.status}`);
    lines.push(`Digital twin,Survival,${c.digitalTwin.survival ?? ""}`);
    lines.push(`Digital twin,Risk,${c.digitalTwin.risk ?? ""}`);
  }
  if (c.prediction.basis === "measured") {
    lines.push(`Prediction,Survival estimate (heuristic; not validated),${c.prediction.survival ?? ""}`);
    lines.push(`Prediction,Recurrence estimate (heuristic; not validated),${c.prediction.recurrence ?? ""}`);
    lines.push(`Prediction,Classifier confidence (RF malignancy probability),${c.prediction.confidence ?? ""}`);
    lines.push(`Prediction,Model,${c.prediction.model ?? ""}`);
    lines.push(`Prediction,Risk band,${c.prediction.riskBand ?? ""}`);
  } else {
    lines.push(`Prediction,Status,${c.prediction.caveat}`);
  }
  lines.push(`Simulations,Basis,${c.simulations.caveat}`);
  c.simulations.runs.forEach((run, i) => {
    lines.push(`Simulations,Run ${i + 1} (${run.selected ?? "—"}),survival=${run.survival ?? ""} response=${run.response ?? ""}`);
  });
  lines.push(`Documents,Count,${c.documents.count}`);
  return lines.join("\n");
}

function downloadBlob(content: string, mime: string, filename: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function ReportsPage() {
  const { data: patients = [] } = usePatients();
  const [patientId, setPatientId] = useState<string>("");
  const [filter, setFilter] = useState<string>("All");
  const [activeReportId, setActiveReportId] = useState<string | null>(null);

  useEffect(() => {
    if (!patientId && patients.length > 0) setPatientId(patients[0].id);
  }, [patients, patientId]);

  const { data: reports = [], isLoading: reportsLoading, isError: reportsError, refetch: refetchReports } = useReports();
  const patientReports = useMemo(() => reports.filter((r) => r.patientId === patientId), [reports, patientId]);

  useEffect(() => {
    if (patientReports.length > 0 && (!activeReportId || !patientReports.some((r) => r.id === activeReportId))) {
      setActiveReportId(patientReports[0].id);
    }
    if (patientReports.length === 0) setActiveReportId(null);
  }, [patientReports, activeReportId]);

  const { data: activeReport, isLoading: detailLoading } = useReport(activeReportId ?? "");
  const { data: versions = [] } = useReportVersions(activeReportId ?? "");
  const { data: downloads = [] } = useDownloadHistory();

  const generate = useGenerateReport();
  const exportReport = useExportReport();

  const filtered = filter === "All" ? reports : reports.filter((r) => r.type === filter);

  const handleGenerate = (type: string = "Clinical summary") => {
    if (!patientId) return;
    generate.mutate({ patientId, type }, {
      onSuccess: (result) => {
        if (result.data?.id) setActiveReportId(result.data.id);
      },
    });
  };

  const handleExport = (format: "pdf" | "csv") => {
    if (!activeReportId) return;
    exportReport.mutate(
      { reportId: activeReportId, format },
      {
        onSuccess: (result) => {
          const report = result.data;
          if (!report) return;
          if (format === "csv") {
            downloadBlob(reportToCsv(report), "text/csv", `${report.id}.csv`);
          } else {
            // No PDF library in this codebase — the browser's own print-to-PDF
            // is the real, dependency-free mechanism (see Phase 8 scope note).
            window.print();
          }
        },
      },
    );
  };

  if (reportsLoading) return <Skeleton className="h-[500px] rounded-2xl" />;
  if (reportsError) {
    return (
      <PageErrorState
        title="Couldn't load reports"
        description="We could not reach the server to load clinical reports. Check your connection and try again."
        onRetry={() => refetchReports()}
      />
    );
  }

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader
        title="Reports"
        description="A print-ready clinical summary combining the patient record, twin state and recorded predictions."
        crumbs={[{ label: "Home", to: "/" }, { label: "Reports" }]}
        actions={
          <>
            <Select value={patientId} onValueChange={setPatientId}>
              <SelectTrigger className="w-[220px]" aria-label="Select patient for report">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {patients.slice(0, 12).map((x) => (
                  <SelectItem key={x.id} value={x.id}>
                    {x.name} · {x.id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => handleGenerate()} disabled={generate.isPending || !patientId}>
              <Sparkles className="size-4" aria-hidden="true" /> Generate
            </Button>
            <Button variant="outline" onClick={() => handleExport("pdf")} disabled={!activeReportId || exportReport.isPending}>
              <FileText className="size-4" aria-hidden="true" /> PDF
            </Button>
            <Button variant="outline" onClick={() => handleExport("csv")} disabled={!activeReportId || exportReport.isPending}>
              <FileSpreadsheet className="size-4" aria-hidden="true" /> CSV
            </Button>
            <Button onClick={() => window.print()} disabled={!activeReportId}>
              <Printer className="size-4" aria-hidden="true" /> Print
            </Button>
          </>
        }
      />

      {detailLoading && activeReportId ? (
        <Skeleton className="h-[420px] rounded-2xl" />
      ) : !activeReport ? (
        <Card className="p-8">
          <EmptyState
            icon={FileText}
            title="No report generated yet"
            description="Generate a clinical decision support report for this patient from their current record, digital twin and recorded predictions."
          />
        </Card>
      ) : (
        <Card className="p-8">
          <header className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold">{activeReport.title}</h2>
              <p className="text-sm text-muted-foreground">
                Generated {activeReport.created} · v{activeReport.version}
              </p>
            </div>
            <StatusChip tone="primary">Confidential</StatusChip>
          </header>

          <Separator className="my-6" />

          <section>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Patient summary</h3>
            <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                ["Name", activeReport.content.patient.name],
                ["Patient ID", activeReport.content.patient.patientId],
                ["Age", activeReport.content.patient.age == null ? "—" : `${activeReport.content.patient.age}`],
                ["Stage", activeReport.content.patient.stage ? `Stage ${activeReport.content.patient.stage}` : "—"],
                [
                  "Tumor size",
                  activeReport.content.patient.tumorSizeMm == null ? "—" : `${activeReport.content.patient.tumorSizeMm} mm`,
                ],
                [
                  "ER / PR / HER2",
                  [activeReport.content.patient.erStatus, activeReport.content.patient.prStatus, activeReport.content.patient.her2Status]
                    .map((s) => s?.[0] ?? "—")
                    .join(" / "),
                ],
                ["Treatment", activeReport.content.patient.currentTreatment || "—"],
                ["Status", activeReport.content.patient.status ?? "—"],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="text-xs text-muted-foreground">{k}</dt>
                  <dd className="mt-0.5 text-sm font-medium">{v}</dd>
                </div>
              ))}
            </dl>
          </section>

          <Separator className="my-6" />

          <section className="grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Digital twin summary</h3>
              {activeReport.content.digitalTwin ? (
                <div className="mt-3 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Twin status</span>
                    <StatusChip tone="success">{activeReport.content.digitalTwin.status}</StatusChip>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Risk level</span>
                    <RiskChip level={activeReport.content.digitalTwin.risk as RiskLevel | null} />
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Version</span>
                    <span className="font-medium">{activeReport.content.digitalTwin.version}</span>
                  </div>
                </div>
              ) : (
                <p className="mt-3 text-sm text-muted-foreground">No digital twin has been created for this patient yet.</p>
              )}
            </div>
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Prediction summary</h3>
              {activeReport.content.prediction.basis === "measured" ? (
                <div className="mt-3 space-y-2 text-sm">
                  <div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Survival estimate</span>
                      <span className="font-medium">
                        {activeReport.content.prediction.survival == null ? "—" : `${activeReport.content.prediction.survival}%`}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Heuristic estimate — not a validated 5-year survival prediction
                    </p>
                  </div>
                  <div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Recurrence estimate</span>
                      <span className="font-medium">
                        {activeReport.content.prediction.recurrence == null ? "—" : `${activeReport.content.prediction.recurrence}%`}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">Heuristic estimate — not independently validated</p>
                  </div>
                  <div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Classifier confidence</span>
                      <span className="font-medium">
                        {activeReport.content.prediction.confidence == null ? "—" : `${activeReport.content.prediction.confidence}%`}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">Random Forest malignancy-classification probability</p>
                  </div>
                  {activeReport.content.prediction.model && (
                    <p className="text-xs text-muted-foreground">Model: {activeReport.content.prediction.model}</p>
                  )}
                </div>
              ) : (
                <p className="mt-3 text-sm text-muted-foreground">{activeReport.content.prediction.caveat}</p>
              )}
            </div>
          </section>

          <Separator className="my-6" />

          <section>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Treatment simulations</h3>
            <p className="mt-1 text-xs text-muted-foreground">{activeReport.content.simulations.caveat}</p>
            {activeReport.content.simulations.runs.length === 0 ? (
              <p className="mt-3 text-sm text-muted-foreground">No simulation runs recorded for this patient.</p>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Selected regimen</TableHead>
                      <TableHead>Decision</TableHead>
                      <TableHead>Projected survival</TableHead>
                      <TableHead>Confidence</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {activeReport.content.simulations.runs.map((run) => (
                      <TableRow key={run.id}>
                        <TableCell>{run.date}</TableCell>
                        <TableCell className="font-medium">{run.selected ?? "—"}</TableCell>
                        <TableCell>{run.decision ?? "—"}</TableCell>
                        <TableCell>{run.survival == null ? "—" : `${run.survival}%`}</TableCell>
                        <TableCell>{run.confidence == null ? "—" : `${run.confidence}%`}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </section>

          <Separator className="my-6" />

          <section className="grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Timeline</h3>
              <div className="mt-4">
                {activeReport.content.timeline.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No recorded timeline events.</p>
                ) : (
                  <Timeline items={activeReport.content.timeline} />
                )}
              </div>
            </div>
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Clinical notes</h3>
              <p className="mt-3 text-sm text-muted-foreground">{activeReport.content.notes || "No notes on file."}</p>
              <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Documents</h3>
              <p className="mt-3 text-sm text-muted-foreground">
                {activeReport.content.documents.count} document{activeReport.content.documents.count === 1 ? "" : "s"} on file.
              </p>
            </div>
          </section>
        </Card>
      )}

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-base">Report history</CardTitle>
          <CardDescription>Previously generated reports, their versions and download counts</CardDescription>
          <div className="pt-3">
            <Tabs value={filter} onValueChange={setFilter}>
              <TabsList className="flex-wrap">
                {["All", ...REPORT_TYPES].map((t) => (
                  <TabsTrigger key={t} value={t}>
                    {t}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Report</TableHead>
                <TableHead>Patient</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Version</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Downloads</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="py-10 text-center text-sm text-muted-foreground">
                    No reports match this filter yet.
                  </TableCell>
                </TableRow>
              )}
              {filtered.map((r) => (
                <TableRow key={r.id} className="cursor-pointer" onClick={() => setActiveReportId(r.id)}>
                  <TableCell className="font-medium">{r.title}</TableCell>
                  <TableCell>{r.patient}</TableCell>
                  <TableCell>{r.type}</TableCell>
                  <TableCell>{r.created}</TableCell>
                  <TableCell>v{r.version}</TableCell>
                  <TableCell>
                    <StatusChip tone={r.status === "Final" ? "success" : r.status === "Draft" ? "warning" : "neutral"}>
                      {r.status}
                    </StatusChip>
                  </TableCell>
                  <TableCell className="text-right">{r.downloads}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Version history</CardTitle>
            <CardDescription>Revisions of the selected report</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {versions.length === 0 && <p className="text-sm text-muted-foreground">Select a report to see its version history.</p>}
            {versions.map((v) => (
              <div key={v.version} className="flex gap-3 rounded-xl border border-border p-3">
                <StatusChip tone={v.version === versions[0]?.version ? "success" : "neutral"}>v{v.version}</StatusChip>
                <div className="min-w-0">
                  <p className="text-sm font-medium">{v.note}</p>
                  <p className="text-xs text-muted-foreground">
                    {v.author} · {v.date}
                  </p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Download history</CardTitle>
            <CardDescription>Who exported what, and when</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {downloads.length === 0 && <p className="text-sm text-muted-foreground">No exports recorded yet.</p>}
            {downloads.map((d) => (
              <div key={d.id} className="flex items-center justify-between gap-3 rounded-xl border border-border p-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium">
                    {d.report} · {d.format}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {d.by} · {d.at}
                  </p>
                </div>
                <Download className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-base">Report templates</CardTitle>
          <CardDescription>Generate a pre-configured report type for the selected patient</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-3">
          {(["Tumor board packet", "Cohort summary", "Model audit"] as const).map((t) => (
            <button
              key={t}
              onClick={() => handleGenerate(t)}
              disabled={generate.isPending || !patientId}
              className="hover-lift flex items-center gap-3 rounded-xl border border-border p-4 text-left disabled:opacity-50"
            >
              <Sparkles className="size-4 text-primary" aria-hidden="true" />
              <span className="text-sm font-medium">{t}</span>
            </button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
