import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { Activity, Boxes, Download, FileText, FlaskConical, Image as ImageIcon, Pencil, Stethoscope } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { RiskChip, StatusChip } from "@/components/common/StatusChip";
import { Timeline } from "@/components/common/Timeline";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { patients, type Patient } from "@/lib/mock-data";
import { imagingStudies, labResults, simulationHistory, treatmentPlan } from "@/lib/mock-extra";


export const Route = createFileRoute("/_shell/patients/$patientId")({
  loader: ({ params }) => {
    const patient = patients.find((p) => p.id === params.patientId);
    if (!patient) throw notFound();
    return { patient };
  },
  head: ({ loaderData }) => {
    if (!loaderData) {
      return { meta: [{ title: "Patient unavailable — OncoTwin" }, { name: "robots", content: "noindex" }] };
    }
    const title = `${loaderData.patient.name} — Patient Profile | OncoTwin`;
    const description = `Clinical profile, biomarkers, treatment timeline and digital twin status for ${loaderData.patient.name}.`;
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
      ],
    };
  },
  component: PatientProfile,
});

function Field({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium">{value}</dd>
    </div>
  );
}

function PatientProfile() {
  const { patient: p } = Route.useLoaderData() as { patient: Patient };

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title={p.name}
        description={`${p.id} · ${p.age} years · Stage ${p.stage} invasive ductal carcinoma`}
        crumbs={[{ label: "Home", to: "/" }, { label: "Patients", to: "/patients" }, { label: p.name }]}
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/patients/$patientId/edit" params={{ patientId: p.id }}>
                <Pencil className="size-4" aria-hidden="true" /> Edit
              </Link>
            </Button>

            <Button variant="outline" asChild>
              <Link to="/digital-twins">
                <Boxes className="size-4" aria-hidden="true" /> Digital twin
              </Link>
            </Button>
            <Button asChild>
              <Link to="/simulator">
                <Stethoscope className="size-4" aria-hidden="true" /> Simulate treatment
              </Link>
            </Button>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Personal information</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Field label="Patient ID" value={p.id} />
                <Field label="Age" value={p.age} />
                <Field label="Gender" value={p.gender} />
                <Field label="Diagnosed" value={p.diagnosedOn} />
                <Field label="Email" value={p.email} />
                <Field label="Phone" value={p.phone} />
                <Field label="Hospital" value={p.hospital} />
                <Field label="Last updated" value={p.lastUpdated} />
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Clinical information & biomarkers</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Field label="Cancer stage" value={`Stage ${p.stage}`} />
                <Field label="Tumor size" value={`${p.tumorSizeMm} mm`} />
                <Field label="Histologic grade" value={`G${p.grade}`} />
                <Field label="Nodes involved" value={p.nodesInvolved} />
              </dl>
              <Separator />
              <div className="grid gap-3 sm:grid-cols-4">
                {[
                  { k: "ER", v: p.erStatus },
                  { k: "PR", v: p.prStatus },
                  { k: "HER2", v: p.her2Status },
                ].map((b) => (
                  <div key={b.k} className="rounded-xl border border-border p-3">
                    <p className="text-xs text-muted-foreground">{b.k} status</p>
                    <StatusChip tone={b.v === "Positive" ? "success" : "neutral"} className="mt-1.5">
                      {b.v}
                    </StatusChip>
                  </div>
                ))}
                <div className="rounded-xl border border-border p-3">
                  <p className="text-xs text-muted-foreground">Ki-67 index</p>
                  <p className="mt-1 text-sm font-semibold">{p.ki67}%</p>
                  <Progress value={p.ki67} className="mt-2 h-1.5" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Clinical history</CardTitle>
              <CardDescription>Comorbidities, prior interventions and family history</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="grid gap-2 sm:grid-cols-2">
                {p.history.map((h) => (
                  <li key={h} className="flex gap-2 rounded-xl border border-border p-3 text-sm">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />
                    {h}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FlaskConical className="size-4 text-primary" aria-hidden="true" /> Lab results
              </CardTitle>
              <CardDescription>Most recent panels with reference ranges</CardDescription>
            </CardHeader>
            <CardContent className="px-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Panel</TableHead>
                    <TableHead>Marker</TableHead>
                    <TableHead>Value</TableHead>
                    <TableHead>Reference</TableHead>
                    <TableHead>Flag</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {labResults.map((l) => (
                    <TableRow key={l.date + l.marker}>
                      <TableCell className="text-muted-foreground">{l.date}</TableCell>
                      <TableCell>{l.panel}</TableCell>
                      <TableCell className="font-medium">{l.marker}</TableCell>
                      <TableCell>
                        {l.value} {l.unit}
                      </TableCell>
                      <TableCell className="text-muted-foreground">{l.range}</TableCell>
                      <TableCell>
                        <StatusChip tone={l.flag === "normal" ? "success" : l.flag === "high" ? "risk" : "warning"}>
                          {l.flag}
                        </StatusChip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ImageIcon className="size-4 text-primary" aria-hidden="true" /> Imaging
              </CardTitle>
              <CardDescription>MRI, CT, PET and mammography studies</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {imagingStudies.map((s) => (
                <div key={s.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-border p-3">
                  <StatusChip tone="primary">{s.modality}</StatusChip>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{s.finding}</p>
                    <p className="text-xs text-muted-foreground">
                      {s.region} · {s.date} · {s.radiologist}
                    </p>
                  </div>
                  <StatusChip tone="success">{s.status}</StatusChip>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Treatment</CardTitle>
              <CardDescription>Active regimen and adherence</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Field label="Regimen" value={treatmentPlan.regimen} />
                <Field label="Cycle" value={`${treatmentPlan.cycle} of ${treatmentPlan.totalCycles}`} />
                <Field label="Started" value={treatmentPlan.startedOn} />
                <Field label="Next dose" value={treatmentPlan.nextDose} />
              </dl>
              <div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Adherence</span>
                  <span className="font-semibold">{treatmentPlan.adherence}%</span>
                </div>
                <Progress value={treatmentPlan.adherence} className="mt-2 h-2" />
              </div>
            </CardContent>
          </Card>

          <Card>

            <CardHeader>
              <CardTitle>Timelines</CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="disease">
                <TabsList>
                  <TabsTrigger value="disease">Disease timeline</TabsTrigger>
                  <TabsTrigger value="treatment">Treatment timeline</TabsTrigger>
                  <TabsTrigger value="reports">Uploaded reports</TabsTrigger>
                </TabsList>
                <TabsContent value="disease" className="pt-5">
                  <Timeline items={p.timeline} />
                </TabsContent>
                <TabsContent value="treatment" className="pt-5">
                  <Timeline items={p.timeline.filter((t) => t.kind === "treatment" || t.kind === "note")} />
                </TabsContent>
                <TabsContent value="reports" className="space-y-2 pt-5">
                  {p.reports.map((r) => (
                    <div key={r.name} className="flex items-center gap-3 rounded-xl border border-border p-3">
                      <FileText className="size-4 text-primary" aria-hidden="true" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{r.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {r.type} · {r.date} · {r.size}
                        </p>
                      </div>
                      <Button variant="ghost" size="icon" aria-label={`Download ${r.name}`}>
                        <Download className="size-4" aria-hidden="true" />
                      </Button>
                    </div>
                  ))}
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle>Simulation history</CardTitle>
              <CardDescription>Previous treatment simulations run for this patient</CardDescription>
            </CardHeader>
            <CardContent className="px-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Run</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Scenario</TableHead>
                    <TableHead>Survival</TableHead>
                    <TableHead>Response</TableHead>
                    <TableHead>Model</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {simulationHistory.map((s) => (
                    <TableRow key={s.id}>
                      <TableCell className="font-medium">{s.id}</TableCell>
                      <TableCell className="text-muted-foreground">{s.date}</TableCell>
                      <TableCell>{s.scenario}</TableCell>
                      <TableCell>{s.survival}</TableCell>
                      <TableCell>
                        <StatusChip tone={s.response === "Likely responder" ? "success" : "warning"}>{s.response}</StatusChip>
                      </TableCell>
                      <TableCell className="text-muted-foreground">{s.model}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>

            <CardHeader>
              <CardTitle>Doctor notes</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Textarea defaultValue={p.notes} rows={4} aria-label="Doctor notes" />
              <Button variant="outline" size="sm">
                Save note
              </Button>
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-4">
          <Card className="border-primary/25 bg-primary-soft/40">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Activity className="size-4 text-primary" aria-hidden="true" /> Current digital twin
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Twin status</span>
                <StatusChip tone={p.twinStatus === "Synced" ? "success" : p.twinStatus === "Stale" ? "warning" : "primary"} dot>
                  {p.twinStatus}
                </StatusChip>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Risk level</span>
                <RiskChip level={p.risk} />
              </div>
              <div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">5-year survival</span>
                  <span className="font-semibold">{p.survivalProbability}%</span>
                </div>
                <Progress value={p.survivalProbability} className="mt-2 h-2" />
              </div>
              <Button className="w-full" asChild>
                <Link to="/digital-twins">Open twin</Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Prediction summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {[
                { k: "Treatment response", v: "Likely responder", tone: "success" as const },
                { k: "Recurrence risk (5y)", v: `${100 - p.survivalProbability}%`, tone: p.risk === "high" ? ("risk" as const) : ("warning" as const) },
                { k: "Model confidence", v: "88%", tone: "primary" as const },
              ].map((row) => (
                <div key={row.k} className="flex items-center justify-between">
                  <span className="text-muted-foreground">{row.k}</span>
                  <StatusChip tone={row.tone}>{row.v}</StatusChip>
                </div>
              ))}
              <Button variant="outline" className="w-full" asChild>
                <Link to="/predictions">View predictions</Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Medical history</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm text-muted-foreground">
                {p.history.map((h) => (
                  <li key={h} className="flex gap-2">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />
                    {h}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
