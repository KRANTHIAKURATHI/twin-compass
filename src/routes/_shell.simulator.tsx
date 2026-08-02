import { useState } from "react";
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
import { patients, scenarios } from "@/lib/mock-data";
import { simulationService } from "@/services";


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

type Scenario = (typeof scenarios)[number];

function SimulatorPage() {
  const [patientId, setPatientId] = useState(patients[0].id);
  const [running, setRunning] = useState(false);
  const [hasRun, setHasRun] = useState(true);
  const [customScenarios, setCustomScenarios] = useState<Scenario[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [promoteNotes, setPromoteNotes] = useState("");
  const [builder, setBuilder] = useState({ name: "", regimen: "", dosage: "60 mg/m²", duration: "12", notes: "" });
  const patient = patients.find((p) => p.id === patientId)!;

  const allScenarios: Scenario[] = [...scenarios, ...customScenarios];
  const selected = allScenarios.find((s) => s.id === selectedScenario) ?? null;

  const run = async () => {
    setRunning(true);
    await simulationService.run(patientId);
    setRunning(false);
    setHasRun(true);
    toast.success("Simulation complete", { description: "4 scenarios compared · TODO: wire POST /api/simulations" });
  };

  const saveScenario = () => {
    if (!builder.name.trim() || !builder.regimen.trim()) {
      toast.error("Scenario name and regimen are required");
      return;
    }
    const draft: Scenario = {
      ...scenarios[0],
      id: `SC-${Date.now()}`,
      name: builder.name.trim(),
      regimen: `${builder.regimen.trim()} · ${builder.dosage} · ${builder.duration} weeks`,
      recommended: false,
    };
    setCustomScenarios((prev) => [...prev, draft]);
    setBuilder({ name: "", regimen: "", dosage: "60 mg/m²", duration: "12", notes: "" });
    toast.success("Scenario saved", { description: "TODO: wire POST /api/simulations/scenarios" });
  };

  const duplicateScenario = (s: Scenario) => {
    setCustomScenarios((prev) => [...prev, { ...s, id: `${s.id}-copy-${prev.length + 1}`, name: `${s.name} (copy)`, recommended: false }]);
    toast.success(`Duplicated ${s.name}`);
  };

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Treatment Simulator"
        description="Run the digital twin forward under different regimens and compare predicted outcomes."
        crumbs={[{ label: "Home", to: "/" }, { label: "Treatment Simulator" }]}
        actions={
          <>
            <Button variant="outline" disabled={!selected} onClick={() => setPromoteOpen(true)}>
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
                {patients.slice(0, 12).map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name} · {p.id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <StatusChip tone="neutral">Stage {patient.stage}</StatusChip>
              <StatusChip tone="neutral">{patient.tumorSizeMm} mm</StatusChip>
              <StatusChip tone={patient.her2Status === "Positive" ? "warning" : "neutral"}>
                HER2 {patient.her2Status === "Positive" ? "+" : "−"}
              </StatusChip>
              <RiskChip level={patient.risk} />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">Baseline twin state · last synced {patient.lastUpdated}</p>
        </CardContent>
      </Card>

      {running || !hasRun ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[420px] rounded-2xl" />
          ))}
        </div>
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
                <div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Predicted response</span>
                    <span className="font-semibold">{s.predictedResponse}%</span>
                  </div>
                  <Progress value={s.predictedResponse} className="mt-2 h-2" />
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-lg bg-muted/60 p-2.5">
                    <p className="flex items-center gap-1 text-xs text-muted-foreground">
                      <TrendingDown className="size-3" aria-hidden="true" /> Tumor change
                    </p>
                    <p className="mt-0.5 font-semibold text-success">{s.tumorChange}%</p>
                  </div>
                  <div className="rounded-lg bg-muted/60 p-2.5">
                    <p className="flex items-center gap-1 text-xs text-muted-foreground">
                      <ShieldCheck className="size-3" aria-hidden="true" /> 5-y survival
                    </p>
                    <p className="mt-0.5 font-semibold">{s.survival5y}%</p>
                  </div>
                  <div className="rounded-lg bg-muted/60 p-2.5">
                    <p className="flex items-center gap-1 text-xs text-muted-foreground">
                      <AlertTriangle className="size-3" aria-hidden="true" /> Side effects
                    </p>
                    <p className="mt-0.5 font-semibold">{s.sideEffectRisk}%</p>
                  </div>
                  <div className="rounded-lg bg-muted/60 p-2.5">
                    <p className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Clock className="size-3" aria-hidden="true" /> Recovery
                    </p>
                    <p className="mt-0.5 font-semibold">{s.recoveryWeeks} wks</p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2">
                  <RiskChip level={s.risk} />
                  <StatusChip tone="primary">{s.confidence}% confidence</StatusChip>
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
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <section className="mt-4 grid gap-4 lg:grid-cols-[380px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Scenario builder</CardTitle>
            <CardDescription>Define a custom regimen and add it to the comparison</CardDescription>
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
              <Button onClick={saveScenario}>Save scenario</Button>
              <Button
                variant="outline"
                disabled={!selected}
                onClick={() => selected && duplicateScenario(selected)}
              >
                <Copy className="size-4" aria-hidden="true" /> Duplicate selected
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
                      <TableCell>{s.predictedResponse}%</TableCell>
                      <TableCell className="text-success">{s.tumorChange}%</TableCell>
                      <TableCell>{s.survival5y}%</TableCell>
                      <TableCell>{s.sideEffectRisk}%</TableCell>
                      <TableCell>{s.confidence}%</TableCell>
                      <TableCell>
                        <RiskChip level={s.risk} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
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
            <Button
              onClick={() => {
                setPromoteOpen(false);
                toast.success("Scenario promoted to treatment plan", {
                  description: "TODO: wire POST /api/treatment-plans",
                });
              }}
            >
              Promote scenario
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>

  );
}
