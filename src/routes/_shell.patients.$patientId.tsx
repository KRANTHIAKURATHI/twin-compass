import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Activity, Boxes, Download, FileText, FlaskConical, Image as ImageIcon, Pencil, Stethoscope } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { RiskChip, StatusChip } from "@/components/common/StatusChip";
import { Timeline, type TimelineItem } from "@/components/common/Timeline";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { patientService } from "@/services";
import {
  usePatient,
  usePatientImaging,
  usePatientLabs,
  usePatientTimeline,
  usePrediction,
  useSimulationRuns,
  useTreatmentPlan,
  useTwinVersions,
  useUpdatePatient,
} from "@/hooks/api";
import type { Patient } from "@/types/models";

export const Route = createFileRoute("/_shell/patients/$patientId")({
  loader: async ({ params }) => {
    const patient = await patientService.get(params.patientId);
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
  errorComponent: RouteErrorState,
  component: withPageStates(PatientProfile, { variant: "detail" }),
});

/** `—` rather than `0` for anything the record simply does not carry. */
const show = (value: unknown, suffix = "") =>
  value === null || value === undefined || value === "" ? "—" : `${value}${suffix}`;

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleDateString() : "—");

function Field({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium">{show(value)}</dd>
    </div>
  );
}

function Nothing({ children }: { children: string }) {
  return <p className="py-8 text-center text-sm text-muted-foreground">{children}</p>;
}

function PatientProfile() {
  const { patient: loaded } = Route.useLoaderData() as { patient: Patient };
  // The loader result seeds the first paint; the query keeps it current after
  // an edit without a full route reload.
  const { data: live } = usePatient(loaded.id);
  const p = live ?? loaded;

  const { data: labs = [] } = usePatientLabs(p.id);
  const { data: imaging = [] } = usePatientImaging(p.id);
  const { data: timeline = [] } = usePatientTimeline(p.id);
  const { data: versions = [] } = useTwinVersions(p.id);
  const { data: runs = [] } = useSimulationRuns(p.id);
  const { data: plan } = useTreatmentPlan(p.id);
  const { data: latestPrediction } = usePrediction(p.id);
  const updatePatient = useUpdatePatient(p.id);

  const diseaseEvents = [...timeline].sort((a, b) => (a.date < b.date ? 1 : -1));
  const treatmentEvents = diseaseEvents.filter((t) => t.kind === "treatment" || t.kind === "note");

  // The twin/simulation tab is built from the twin versions and simulation
  // runs themselves rather than from timeline rows, because those rows are all
  // stored with kind "note" and cannot be told apart after the fact.
  const systemEvents: TimelineItem[] = [
    ...versions.map((v) => ({
      date: v.createdAt,
      title: `Twin ${v.version} — ${v.status}`,
      detail: v.summary || `${v.model || "No model recorded"} · ${v.author || "unattributed"}`,
      kind: "note" as const,
    })),
    ...runs.map((r) => ({
      date: r.date,
      title: `Simulation ${r.id.slice(0, 8)} — ${r.decision}`,
      detail: `${r.selected || "no scenario selected"} · ${r.model || "no model recorded"}`,
      kind: "treatment" as const,
    })),
  ].sort((a, b) => (a.date < b.date ? 1 : -1));

  const biomarkers = [
    { k: "ER", v: p.erStatus },
    { k: "PR", v: p.prStatus },
    { k: "HER2", v: p.her2Status },
  ];

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title={p.name}
        description={[p.id, p.age == null ? null : `${p.age} years`, p.stage ? `Stage ${p.stage}` : null]
          .filter(Boolean)
          .join(" · ")}
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
                <Field label="Diagnosed" value={formatDate(p.diagnosedOn)} />
                <Field label="Email" value={p.email} />
                <Field label="Phone" value={p.phone} />
                <Field label="Hospital" value={p.hospital} />
                <Field label="Last updated" value={formatDate(p.lastUpdated)} />
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Clinical information & biomarkers</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Field label="Cancer stage" value={p.stage ? `Stage ${p.stage}` : null} />
                <Field label="Tumor size" value={p.tumorSizeMm == null ? null : `${p.tumorSizeMm} mm`} />
                <Field label="Histologic grade" value={p.grade == null ? null : `G${p.grade}`} />
                <Field label="Nodes involved" value={p.nodesInvolved} />
              </dl>
              <Separator />
              <div className="grid gap-3 sm:grid-cols-4">
                {biomarkers.map((b) => (
                  <div key={b.k} className="rounded-xl border border-border p-3">
                    <p className="text-xs text-muted-foreground">{b.k} status</p>
                    <StatusChip tone={b.v === "Positive" ? "success" : "neutral"} className="mt-1.5">
                      {b.v ?? "Not recorded"}
                    </StatusChip>
                  </div>
                ))}
                <div className="rounded-xl border border-border p-3">
                  <p className="text-xs text-muted-foreground">Ki-67 index</p>
                  <p className="mt-1 text-sm font-semibold">{show(p.ki67, "%")}</p>
                  {/* No bar when there is no index — an empty bar reads as 0%. */}
                  {p.ki67 != null && <Progress value={p.ki67} className="mt-2 h-1.5" />}
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
              {p.history.length === 0 ? (
                <Nothing>No clinical history recorded for this patient.</Nothing>
              ) : (
                <ul className="grid gap-2 sm:grid-cols-2">
                  {p.history.map((h) => (
                    <li key={h} className="flex gap-2 rounded-xl border border-border p-3 text-sm">
                      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />
                      {h}
                    </li>
                  ))}
                </ul>
              )}
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
              {labs.length === 0 ? (
                <Nothing>No lab results recorded for this patient.</Nothing>
              ) : (
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
                    {labs.map((l) => (
                      <TableRow key={l.date + l.marker}>
                        <TableCell className="text-muted-foreground">{formatDate(l.date)}</TableCell>
                        <TableCell>{show(l.panel)}</TableCell>
                        <TableCell className="font-medium">{l.marker}</TableCell>
                        <TableCell>
                          {l.value} {l.unit}
                        </TableCell>
                        <TableCell className="text-muted-foreground">{show(l.range)}</TableCell>
                        <TableCell>
                          <StatusChip tone={l.flag === "normal" ? "success" : l.flag === "high" ? "risk" : "warning"}>
                            {l.flag}
                          </StatusChip>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
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
              {imaging.length === 0 ? (
                <Nothing>No imaging studies recorded for this patient.</Nothing>
              ) : (
                imaging.map((s) => (
                  <div key={s.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-border p-3">
                    <StatusChip tone="primary">{show(s.modality)}</StatusChip>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium">{show(s.finding)}</p>
                      <p className="text-xs text-muted-foreground">
                        {show(s.region)} · {formatDate(s.date)} · {show(s.radiologist)}
                      </p>
                    </div>
                    <StatusChip tone="success">{show(s.status)}</StatusChip>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Treatment</CardTitle>
              <CardDescription>Active regimen and adherence</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {!plan ? (
                <Nothing>No treatment plan recorded. Promote a simulation to create one.</Nothing>
              ) : (
                <>
                  <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                    <Field label="Regimen" value={plan.regimen} />
                    <Field
                      label="Cycle"
                      value={plan.cycle == null ? null : `${plan.cycle} of ${plan.totalCycles ?? "—"}`}
                    />
                    <Field label="Started" value={formatDate(plan.startedOn)} />
                    <Field label="Next dose" value={formatDate(plan.nextDose)} />
                  </dl>
                  {plan.adherence != null && (
                    <div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Adherence</span>
                        <span className="font-semibold">{plan.adherence}%</span>
                      </div>
                      <Progress value={plan.adherence} className="mt-2 h-2" />
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Timelines</CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="disease">
                <TabsList className="flex-wrap">
                  <TabsTrigger value="disease">Disease timeline</TabsTrigger>
                  <TabsTrigger value="treatment">Treatment timeline</TabsTrigger>
                  <TabsTrigger value="system">Twin & simulations</TabsTrigger>
                  <TabsTrigger value="reports">Uploaded reports</TabsTrigger>
                </TabsList>
                <TabsContent value="disease" className="pt-5">
                  {diseaseEvents.length === 0 ? (
                    <Nothing>No events recorded for this patient yet.</Nothing>
                  ) : (
                    <Timeline items={diseaseEvents} />
                  )}
                </TabsContent>
                <TabsContent value="treatment" className="pt-5">
                  {treatmentEvents.length === 0 ? (
                    <Nothing>No treatment events recorded yet.</Nothing>
                  ) : (
                    <Timeline items={treatmentEvents} />
                  )}
                </TabsContent>
                <TabsContent value="system" className="pt-5">
                  {systemEvents.length === 0 ? (
                    <Nothing>No twin versions or simulation runs recorded yet.</Nothing>
                  ) : (
                    <Timeline items={systemEvents} />
                  )}
                </TabsContent>

                <TabsContent value="reports" className="space-y-2 pt-5">
                  {p.reports.length === 0 ? (
                    <Nothing>No reports have been uploaded for this patient.</Nothing>
                  ) : (
                    p.reports.map((r) => (
                      <div key={r.name} className="flex items-center gap-3 rounded-xl border border-border p-3">
                        <FileText className="size-4 text-primary" aria-hidden="true" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{r.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {show(r.type)} · {formatDate(r.date)} · {show(r.size)}
                          </p>
                        </div>
                        <Button variant="ghost" size="icon" aria-label={`Download ${r.name}`}>
                          <Download className="size-4" aria-hidden="true" />
                        </Button>
                      </div>
                    ))
                  )}
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
              {runs.length === 0 ? (
                <Nothing>No simulations have been run for this patient.</Nothing>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Run</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Scenario</TableHead>
                      <TableHead>Survival</TableHead>
                      <TableHead>Decision</TableHead>
                      <TableHead>Model</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {runs.map((s) => (
                      <TableRow key={s.id}>
                        <TableCell className="font-medium">{s.id.slice(0, 8)}</TableCell>
                        <TableCell className="text-muted-foreground">{formatDate(s.date)}</TableCell>
                        <TableCell>{show(s.selected)}</TableCell>
                        <TableCell>{show(s.survival, "%")}</TableCell>
                        <TableCell>
                          <StatusChip tone={s.decision === "Promoted to plan" ? "success" : "neutral"}>
                            {show(s.decision)}
                          </StatusChip>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{show(s.model)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Doctor notes</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <form
                className="space-y-3"
                onSubmit={async (e) => {
                  e.preventDefault();
                  const notes = String(new FormData(e.currentTarget).get("notes") ?? "");
                  await updatePatient.mutateAsync({ notes });
                }}
              >
                {/* Keyed on the patient so switching records resets the box. */}
                <Textarea key={p.id} name="notes" defaultValue={p.notes} rows={4} aria-label="Doctor notes" />
                <Button type="submit" variant="outline" size="sm" disabled={updatePatient.isPending}>
                  {updatePatient.isPending ? "Saving…" : "Save note"}
                </Button>
              </form>
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
                {p.twinStatus ? (
                  <StatusChip
                    tone={p.twinStatus === "Synced" ? "success" : p.twinStatus === "Stale" ? "warning" : "primary"}
                    dot
                  >
                    {p.twinStatus}
                  </StatusChip>
                ) : (
                  <StatusChip tone="neutral">No twin</StatusChip>
                )}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Risk level</span>
                <RiskChip level={p.risk} />
              </div>
              <div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">5-year survival</span>
                  <span className="font-semibold">{show(p.survivalProbability, "%")}</span>
                </div>
                {p.survivalProbability != null && (
                  <Progress value={p.survivalProbability} className="mt-2 h-2" />
                )}
              </div>
              <Button className="w-full" asChild>
                <Link to="/digital-twins">Open twin</Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Prediction summary</CardTitle>
              <CardDescription>
                {latestPrediction
                  ? `Run ${latestPrediction.id.slice(0, 8)} · ${formatDate(latestPrediction.date)}`
                  : "No prediction run recorded"}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {!latestPrediction ? (
                <Nothing>Run a prediction to populate this summary.</Nothing>
              ) : (
                [
                  // Labelled "Treatment response" until the field it reads was
                  // traced: it has only ever carried the twin's risk band.
                  { k: "Risk band at run", v: latestPrediction.riskBand ?? "—", tone: "success" as const },
                  {
                    k: "Recurrence risk (5y)",
                    v: latestPrediction.recurrence == null ? "—" : `${latestPrediction.recurrence}%`,
                    tone: p.risk === "high" ? ("risk" as const) : ("warning" as const),
                  },
                  {
                    k: "Model confidence",
                    v: latestPrediction.confidence == null ? "Not recorded" : `${latestPrediction.confidence}%`,
                    tone: "primary" as const,
                  },
                ].map((row) => (
                  <div key={row.k} className="flex items-center justify-between">
                    <span className="text-muted-foreground">{row.k}</span>
                    <StatusChip tone={row.tone}>{row.v}</StatusChip>
                  </div>
                ))
              )}
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
              {p.history.length === 0 ? (
                <Nothing>Nothing recorded.</Nothing>
              ) : (
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {p.history.map((h) => (
                    <li key={h} className="flex gap-2">
                      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />
                      {h}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
