import { createFileRoute } from "@tanstack/react-router";
import { Download, FileSpreadsheet, FileText, Printer } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { RiskChip, StatusChip } from "@/components/common/StatusChip";
import { Timeline } from "@/components/common/Timeline";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { patients, scenarios } from "@/lib/mock-data";
import { reportService } from "@/services";

export const Route = createFileRoute("/_shell/reports")({
  head: () => ({
    meta: [
      { title: "Clinical Reports — OncoTwin" },
      { name: "description", content: "Generate patient, digital twin, prediction and treatment comparison reports." },
      { property: "og:title", content: "Clinical Reports — OncoTwin" },
      { property: "og:description", content: "Generate patient, digital twin, prediction and treatment comparison reports." },
    ],
  }),
  component: ReportsPage,
});

function ReportsPage() {
  const p = patients[0];

  const exportAs = async (format: "pdf" | "csv") => {
    await reportService.export(format);
    toast.success(`${format.toUpperCase()} export queued`, { description: "TODO: wire POST /api/reports/export" });
  };

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader
        title="Reports"
        description="A print-ready clinical summary combining the patient record, twin state and AI predictions."
        crumbs={[{ label: "Home", to: "/" }, { label: "Reports" }]}
        actions={
          <>
            <Button variant="outline" onClick={() => exportAs("pdf")}>
              <FileText className="size-4" aria-hidden="true" /> PDF
            </Button>
            <Button variant="outline" onClick={() => exportAs("csv")}>
              <FileSpreadsheet className="size-4" aria-hidden="true" /> CSV
            </Button>
            <Button onClick={() => toast.info("Opening print dialog", { description: "TODO: window.print() on published build" })}>
              <Printer className="size-4" aria-hidden="true" /> Print
            </Button>
          </>
        }
      />

      <Card className="p-8">
        <header className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">Clinical Decision Support Report</h2>
            <p className="text-sm text-muted-foreground">Generated 30 Jul 2026 · OncoTwin model v2.4</p>
          </div>
          <StatusChip tone="primary">Confidential</StatusChip>
        </header>

        <Separator className="my-6" />

        <section>
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Patient summary</h3>
          <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              ["Name", p.name],
              ["Patient ID", p.id],
              ["Age", `${p.age}`],
              ["Stage", `Stage ${p.stage}`],
              ["Tumor size", `${p.tumorSizeMm} mm`],
              ["ER / PR / HER2", `${p.erStatus[0]} / ${p.prStatus[0]} / ${p.her2Status[0]}`],
              ["Treatment", p.currentTreatment],
              ["Status", p.status],
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
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Twin status</span>
                <StatusChip tone="success">{p.twinStatus}</StatusChip>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Risk level</span>
                <RiskChip level={p.risk} />
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Last recalculated</span>
                <span className="font-medium">{p.lastUpdated}</span>
              </div>
            </div>
          </div>
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Prediction summary</h3>
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">5-year survival</span>
                <span className="font-medium">{p.survivalProbability}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Recurrence risk</span>
                <span className="font-medium">{100 - p.survivalProbability}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Model confidence</span>
                <span className="font-medium">89%</span>
              </div>
            </div>
          </div>
        </section>

        <Separator className="my-6" />

        <section>
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Treatment comparison</h3>
          <div className="mt-3 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scenario</TableHead>
                  <TableHead>Response</TableHead>
                  <TableHead>Tumor change</TableHead>
                  <TableHead>5-y survival</TableHead>
                  <TableHead>Side effects</TableHead>
                  <TableHead>Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {scenarios.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-medium">
                      {s.name} {s.recommended && <StatusChip tone="primary" className="ml-1">Recommended</StatusChip>}
                    </TableCell>
                    <TableCell>{s.predictedResponse}%</TableCell>
                    <TableCell className="text-success">{s.tumorChange}%</TableCell>
                    <TableCell>{s.survival5y}%</TableCell>
                    <TableCell>{s.sideEffectRisk}%</TableCell>
                    <TableCell>{s.confidence}%</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </section>

        <Separator className="my-6" />

        <section className="grid gap-6 sm:grid-cols-2">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Timeline</h3>
            <div className="mt-4">
              <Timeline items={p.timeline} />
            </div>
          </div>
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Clinical notes</h3>
            <p className="mt-3 text-sm text-muted-foreground">{p.notes}</p>
          </div>
        </section>
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-base">Report templates</CardTitle>
          <CardDescription>Pre-configured exports for tumor boards and hospital administration</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-3">
          {["Tumor board packet", "Monthly cohort summary", "Model performance audit"].map((t) => (
            <button
              key={t}
              onClick={() => exportAs("pdf")}
              className="hover-lift flex items-center gap-3 rounded-xl border border-border p-4 text-left"
            >
              <Download className="size-4 text-primary" aria-hidden="true" />
              <span className="text-sm font-medium">{t}</span>
            </button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
