import { useEffect, useState } from "react";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { createFileRoute } from "@tanstack/react-router";
import { Play, Sparkles, ShieldCheck, TrendingDown, Clock, AlertTriangle, ArrowUpRight, Copy } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { RiskChip, StatusChip } from "@/components/common/StatusChip";
import { StateNotice } from "@/components/common/StateNotice";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { usePatients, usePromoteSimulation, useRunSimulation, useSimulationRuns } from "@/hooks/api";
import type { RiskLevel, Scenario } from "@/types/models";

export const Route = createFileRoute("/_shell/simulator")({
  head: () => ({
    meta: [
      { title: "Treatment Simulator — OncoTwin" },
      { name: "description", content: "Compare treatment scenarios side by side with predicted response, risk and survival." },
      { property: "og:title", content: "Treatment Simulator — OncoTwin" },
      { property: "og:description", content: "Compare treatment scenarios side by side with predicted response, risk and survival." },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(SimulatorPage, { variant: "detail" }),
});

/**
 * A scenario as the page displays it.
 *
 * Every outcome is nullable because a scenario drafted in the builder has not
 * been evaluated against anything yet. The builder used to spread the first
 * catalogue scenario over each draft, so a regimen the user had just invented
 * inherited a 72% response rate and an 89% confidence and looked computed.
 */
type DisplayScenario = {
  id: string;
  name: string;
  regimen: string;
  recommended: boolean;
  evaluated: boolean;
  predictedResponse: number | null;
  tumorChange: number | null;
  survival5y: number | null;
  sideEffectRisk: number | null;
  recoveryWeeks: number | null;
  confidence: number | null;
  risk: RiskLevel | null;
  baselineSizeMm: number | null;
  projectedSizeMm: number | null;
  cycles: number | null;
  basis: string | null;
  parametersVerified: boolean;
};

const fromApi = (s: Scenario): DisplayScenario => ({
  id: s.id,
  name: s.name,
  regimen: s.regimen,
  recommended: s.recommended,
  evaluated: true,
  predictedResponse: s.predictedResponse,
  tumorChange: s.tumorChange,
  survival5y: s.survival5y,
  sideEffectRisk: s.sideEffectRisk,
  recoveryWeeks: s.recoveryWeeks,
  confidence: s.confidence,
  risk: s.risk,
  baselineSizeMm: s.baselineSizeMm ?? null,
  projectedSizeMm: s.projectedSizeMm ?? null,
  cycles: s.cycles ?? null,
  basis: s.basis ?? null,
  // Defaults to verified so an older run - recorded before the projection
  // carried provenance - is not stamped with a warning nobody can act on.
  parametersVerified: s.provenance?.parametersVerified ?? true,
});

/** `—` rather than `0` for anything that was never evaluated. */
const show = (value: number | null, suffix = "") => (value === null ? "—" : `${value}${suffix}`);

/**
 * True when a recorded scenario carries none of the outcome measures.
 *
 * The card then says why the fields are dashed instead of leaving the reader to
 * guess whether the run failed.
 */
const outcomesMissing = (s: DisplayScenario) =>
  s.predictedResponse === null &&
  s.tumorChange === null &&
  s.sideEffectRisk === null &&
  s.recoveryWeeks === null;

function SimulatorPage() {
  const { data: patientList = [], isLoading: patientsLoading } = usePatients();
  const [patientId, setPatientId] = useState("");
  // At most one queued scenario, because the backend evaluates exactly one
  // custom regimen per run (whatever `builder` holds). A list here previously
  // let several drafts accumulate while only the last-typed regimen was ever
  // sent to Run — the others vanished unevaluated despite a success toast
  // claiming they had been "added to the comparison".
  const [pendingDraft, setPendingDraft] = useState<DisplayScenario | null>(null);
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [promoteNotes, setPromoteNotes] = useState("");
  const [builder, setBuilder] = useState({ name: "", regimen: "", dosage: "", duration: "", notes: "" });
  // The run this page is showing: either the patient's most recent recorded run
  // or one just executed here. Promotion needs its id.
  const [runId, setRunId] = useState<string | null>(null);
  const [runScenarios, setRunScenarios] = useState<DisplayScenario[] | null>(null);

  const runSimulation = useRunSimulation();
  const promoteSimulation = usePromoteSimulation();
  const { data: priorRuns = [], isLoading: runsLoading } = useSimulationRuns(patientId || undefined);

  const patient = patientList.find((p) => p.id === patientId);

  useEffect(() => {
    if (!patientId && patientList[0]) setPatientId(patientList[0].id);
  }, [patientList, patientId]);

  // Switching patient discards the previous patient's run and scenario drafts —
  // showing one patient's scenarios under another's name would be worse than
  // showing nothing.
  useEffect(() => {
    setRunId(null);
    setRunScenarios(null);
    setPendingDraft(null);
    setSelectedScenario(null);
  }, [patientId]);

  // Seed from the newest recorded run so reopening the page shows what was
  // actually last computed for this patient, not a blank grid.
  const latest = priorRuns[0];
  const shown = runScenarios ?? (latest?.scenarios ? latest.scenarios.map(fromApi) : null);
  const activeRunId = runId ?? latest?.id ?? null;
  const allScenarios: DisplayScenario[] = [...(shown ?? []), ...(pendingDraft ? [pendingDraft] : [])];
  const selected = allScenarios.find((s) => s.id === selectedScenario) ?? null;

  if (patientsLoading) {
    return (
      <div className="mx-auto max-w-[1400px] space-y-4">
        <Skeleton className="h-24 rounded-2xl" />
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    );
  }

  if (!patient) {
    return (
      <StateNotice
        state="prediction-unavailable"
        title="No patients available"
        description="Add a patient record before running a simulation."
      />
    );
  }

  const run = async () => {
    const result = await runSimulation.mutateAsync({
      patientId,
      // A saved draft names the regimen the next run should evaluate — this is
      // what makes the scenario builder do something rather than only decorate
      // the comparison table.
      draft: builder.regimen.trim()
        ? {
            name: builder.name.trim() || builder.regimen.trim(),
            regimen: builder.regimen.trim(),
            dosage: builder.dosage.trim(),
            durationWeeks: Number(builder.duration) || 0,
            notes: builder.notes.trim(),
          }
        : undefined,
    });
    // The run's own result is what gets displayed. It used to be awaited and
    // thrown away, leaving the fixed catalogue on screen regardless of outcome.
    setRunId(result.id);
    setRunScenarios(result.scenarios.map(fromApi));
    setPendingDraft(null);
    setSelectedScenario(null);
  };

  const saveScenario = () => {
    if (!builder.name.trim() || !builder.regimen.trim()) {
      toast.error("Scenario name and regimen are required");
      return;
    }
    const detail = [builder.dosage.trim(), builder.duration.trim() && `${builder.duration.trim()} weeks`]
      .filter(Boolean)
      .join(" · ");
    // One slot, not a list: this is exactly the regimen `run()` will send, so
    // there is nothing here that Run can silently drop.
    setPendingDraft({
      id: "draft-pending",
      name: builder.name.trim(),
      regimen: detail ? `${builder.regimen.trim()} · ${detail}` : builder.regimen.trim(),
      recommended: false,
      evaluated: false,
      predictedResponse: null,
      tumorChange: null,
      survival5y: null,
      sideEffectRisk: null,
      recoveryWeeks: null,
      confidence: null,
      risk: null,
      baselineSizeMm: null,
      projectedSizeMm: null,
      cycles: null,
      basis: "Queued — this is the regimen the next run will evaluate.",
      parametersVerified: true,
    });
    toast.success("Queued for the next run", {
      description: "Replaces any previously queued scenario — only one custom regimen is evaluated per run.",
    });
  };

  const duplicateScenario = (s: DisplayScenario) => {
    // Copies the regimen into the builder so what gets queued is exactly what
    // Run will send — a duplicate that just sat in a list, uneditable and
    // never evaluated, was indistinguishable from one that had been run.
    setBuilder({
      name: `${s.name} (copy)`,
      regimen: s.regimen,
      dosage: "",
      duration: "",
      notes: "",
    });
    toast.success(`Copied ${s.name} into the builder`, {
      description: "Adjust it and run the simulation to evaluate it.",
    });
  };

  const promote = async () => {
    if (!selected || !activeRunId) return;
    await promoteSimulation.mutateAsync({
      id: activeRunId,
      notes: promoteNotes.trim() || `Promoted ${selected.name}.`,
    });
    setPromoteOpen(false);
    setPromoteNotes("");
  };

  const running = runSimulation.isPending;
  // Promotion records a decision against a stored run, so an unevaluated draft
  // cannot be promoted.
  const canPromote = Boolean(selected?.evaluated && activeRunId);

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Treatment Simulator"
        description="Run the digital twin forward under different regimens and compare predicted outcomes."
        crumbs={[{ label: "Home", to: "/" }, { label: "Treatment Simulator" }]}
        actions={
          <>
            <Button variant="outline" disabled={!canPromote} onClick={() => setPromoteOpen(true)}>
              <ArrowUpRight className="size-4" aria-hidden="true" /> Promote to plan
            </Button>
            <Button onClick={run} disabled={running}>
              <Play className="size-4" aria-hidden="true" /> {running ? "Running simulation…" : "Run simulation"}
            </Button>
          </>
        }
      />

      {running && (
        <div className="mb-4">
          <StateNotice state="simulation-running" />
        </div>
      )}

      <Card className="mb-4">
        <CardContent className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Select value={patientId} onValueChange={setPatientId}>
              <SelectTrigger className="w-[260px]" aria-label="Select patient">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {patientList.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name} · {p.id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <StatusChip tone="neutral">{patient.stage ? `Stage ${patient.stage}` : "Stage not recorded"}</StatusChip>
              <StatusChip tone="neutral">
                {patient.tumorSizeMm === null ? "Tumor size not recorded" : `${patient.tumorSizeMm} mm`}
              </StatusChip>
              <StatusChip tone={patient.her2Status === "Positive" ? "warning" : "neutral"}>
                {patient.her2Status ? `HER2 ${patient.her2Status === "Positive" ? "+" : "−"}` : "HER2 not recorded"}
              </StatusChip>
              <RiskChip level={patient.risk} />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            {patient.lastUpdated
              ? `Baseline twin state · last synced ${new Date(patient.lastUpdated).toLocaleString()}`
              : "Baseline twin state · never synced"}
          </p>
        </CardContent>
      </Card>

      {running || runsLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[420px] rounded-2xl" />
          ))}
        </div>
      ) : allScenarios.length === 0 ? (
        <Card>
          <CardContent className="py-14 text-center">
            <p className="text-sm font-medium">No simulation has been run for {patient.name}</p>
            <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
              Run the simulator to compare regimens against this patient's twin, or draft a scenario below first.
            </p>
            <Button className="mt-4" onClick={run} disabled={running}>
              <Play className="size-4" aria-hidden="true" /> Run simulation
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {allScenarios.map((s) => (
            <Card
              key={s.id}
              className={cn(
                "hover-lift relative gap-0",
                s.recommended && "border-primary ring-1 ring-primary/30",
                selectedScenario === s.id && "border-primary ring-2 ring-primary/40",
              )}
            >
              {s.recommended && (
                <span className="absolute -top-3 left-5 inline-flex items-center gap-1 rounded-full bg-primary px-2.5 py-1 text-[11px] font-semibold text-primary-foreground">
                  <Sparkles className="size-3" aria-hidden="true" /> Recommended
                </span>
              )}
              <CardHeader>
                <CardTitle className="text-base">{s.name}</CardTitle>
                <CardDescription>{s.regimen}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {!s.evaluated ? (
                  <p className="rounded-lg bg-muted/60 p-2.5 text-xs text-muted-foreground">
                    Draft scenario — not yet evaluated. Run the simulation to fill these in.
                  </p>
                ) : (
                  outcomesMissing(s) && (
                    <p className="rounded-lg bg-muted/60 p-2.5 text-xs text-muted-foreground">
                      {s.basis ?? "No projection available for this scenario."}
                    </p>
                  )
                )}
                <div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Predicted response</span>
                    <span className="font-semibold">{show(s.predictedResponse, "%")}</span>
                  </div>
                  <Progress value={s.predictedResponse ?? 0} className="mt-2 h-2" />
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-lg bg-muted/60 p-2.5">
                    <p className="flex items-center gap-1 text-xs text-muted-foreground">
                      <TrendingDown className="size-3" aria-hidden="true" /> Tumor change
                    </p>
                    <p className={cn("mt-0.5 font-semibold", (s.tumorChange ?? 0) < 0 && "text-success")}>
                      {show(s.tumorChange, "%")}
                    </p>
                    {s.baselineSizeMm !== null && s.projectedSizeMm !== null && (
                      <p className="text-[11px] text-muted-foreground">
                        {s.baselineSizeMm}mm → {s.projectedSizeMm}mm
                      </p>
                    )}
                  </div>
                  <div className="rounded-lg bg-muted/60 p-2.5">
                    <p className="flex items-center gap-1 text-xs text-muted-foreground">
                      <ShieldCheck className="size-3" aria-hidden="true" /> 5-y survival
                    </p>
                    <p className="mt-0.5 font-semibold">{show(s.survival5y, "%")}</p>
                  </div>
                  <div className="rounded-lg bg-muted/60 p-2.5">
                    <p className="flex items-center gap-1 text-xs text-muted-foreground">
                      <AlertTriangle className="size-3" aria-hidden="true" /> Side effects
                    </p>
                    <p className="mt-0.5 font-semibold">{show(s.sideEffectRisk, "%")}</p>
                  </div>
                  <div className="rounded-lg bg-muted/60 p-2.5">
                    <p className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Clock className="size-3" aria-hidden="true" /> Recovery
                    </p>
                    <p className="mt-0.5 font-semibold">{show(s.recoveryWeeks, " wks")}</p>
                    {s.cycles !== null && (
                      <p className="text-[11px] text-muted-foreground">over {s.cycles} cycles</p>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2">
                  <RiskChip level={s.risk} />
                  <StatusChip tone={s.confidence === null ? "neutral" : "primary"}>
                    {s.confidence === null ? "No confidence recorded" : `${s.confidence}% confidence`}
                  </StatusChip>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant={selectedScenario === s.id ? "default" : s.recommended ? "default" : "outline"}
                    className="flex-1"
                    aria-pressed={selectedScenario === s.id}
                    onClick={() => setSelectedScenario(s.id)}
                  >
                    {selectedScenario === s.id ? "Selected" : "Select scenario"}
                  </Button>
                  <Button variant="ghost" size="icon" aria-label={`Duplicate ${s.name}`} onClick={() => duplicateScenario(s)}>
                    <Copy className="size-4" aria-hidden="true" />
                  </Button>
                </div>

                {/* Every card states where its numbers came from. A projection
                    that cannot be traced to a source is not usable clinically. */}
                {s.evaluated && !outcomesMissing(s) && s.basis && (
                  <p className="border-t pt-3 text-[11px] leading-relaxed text-muted-foreground">
                    {s.basis}
                    {!s.parametersVerified && (
                      <span className="ml-1 font-semibold text-warning">
                        Parameters unverified — pending clinical review.
                      </span>
                    )}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <section className="mt-4 grid gap-4 lg:grid-cols-[380px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Scenario builder</CardTitle>
            <CardDescription>Define a custom regimen and evaluate it on the next run</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="sc-name">Scenario name</Label>
              <Input
                id="sc-name"
                required
                value={builder.name}
                onChange={(e) => setBuilder({ ...builder, name: e.target.value })}
                placeholder="Dose-dense AC-T"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="sc-regimen">Drug / regimen</Label>
              <Input
                id="sc-regimen"
                required
                value={builder.regimen}
                onChange={(e) => setBuilder({ ...builder, regimen: e.target.value })}
                placeholder="Doxorubicin + Cyclophosphamide"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="sc-dosage">Dosage</Label>
                <Input
                  id="sc-dosage"
                  value={builder.dosage}
                  onChange={(e) => setBuilder({ ...builder, dosage: e.target.value })}
                  placeholder="60 mg/m²"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sc-duration">Duration (weeks)</Label>
                <Input
                  id="sc-duration"
                  type="number"
                  min={1}
                  max={104}
                  value={builder.duration}
                  onChange={(e) => setBuilder({ ...builder, duration: e.target.value })}
                  placeholder="12"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="sc-notes">Clinical notes</Label>
              <Textarea
                id="sc-notes"
                rows={3}
                value={builder.notes}
                onChange={(e) => setBuilder({ ...builder, notes: e.target.value })}
                placeholder="Cardiac monitoring every 3 cycles…"
              />
            </div>
            <div className="flex flex-wrap gap-2 pt-1">
              <Button onClick={saveScenario}>Queue for next run</Button>
              <Button variant="outline" disabled={!selected} onClick={() => selected && duplicateScenario(selected)}>
                <Copy className="size-4" aria-hidden="true" /> Duplicate selected into builder
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Scenario comparison</CardTitle>
            <CardDescription>All scenarios for {patient.name}, side by side</CardDescription>
          </CardHeader>
          <CardContent>
            {allScenarios.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">
                Nothing to compare yet — run the simulation or add a scenario.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Scenario</TableHead>
                      <TableHead>Response</TableHead>
                      <TableHead>Tumor change</TableHead>
                      <TableHead>5-y survival</TableHead>
                      <TableHead>Side effects</TableHead>
                      <TableHead>Confidence</TableHead>
                      <TableHead>Risk</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {allScenarios.map((s) => (
                      <TableRow key={s.id} className={cn(selectedScenario === s.id && "bg-primary-soft/50")}>
                        <TableCell className="font-medium">{s.name}</TableCell>
                        <TableCell>{show(s.predictedResponse, "%")}</TableCell>
                        <TableCell className={cn((s.tumorChange ?? 0) < 0 && "text-success")}>
                          {show(s.tumorChange, "%")}
                        </TableCell>
                        <TableCell>{show(s.survival5y, "%")}</TableCell>
                        <TableCell>{show(s.sideEffectRisk, "%")}</TableCell>
                        <TableCell>{show(s.confidence, "%")}</TableCell>
                        <TableCell>
                          <RiskChip level={s.risk} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <Dialog open={promoteOpen} onOpenChange={setPromoteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Promote to treatment plan</DialogTitle>
            <DialogDescription>
              {selected
                ? `${selected.name} — ${selected.regimen}. This becomes the active plan for ${patient.name} and is recorded in the audit log.`
                : "Select a scenario first."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="promote-notes">Decision notes</Label>
            <Textarea
              id="promote-notes"
              rows={4}
              value={promoteNotes}
              onChange={(e) => setPromoteNotes(e.target.value)}
              placeholder="Rationale, monitoring requirements, review date…"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPromoteOpen(false)}>
              Cancel
            </Button>
            <Button onClick={promote} disabled={!canPromote || promoteSimulation.isPending}>
              {promoteSimulation.isPending ? "Promoting…" : "Promote scenario"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
