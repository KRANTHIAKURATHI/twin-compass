import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Play, Sparkles, ShieldCheck, TrendingDown, Clock, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { RiskChip, StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
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
  component: SimulatorPage,
});

function SimulatorPage() {
  const [patientId, setPatientId] = useState(patients[0].id);
  const [running, setRunning] = useState(false);
  const [hasRun, setHasRun] = useState(true);
  const patient = patients.find((p) => p.id === patientId)!;

  const run = async () => {
    setRunning(true);
    await simulationService.run(patientId);
    setRunning(false);
    setHasRun(true);
    toast.success("Simulation complete", { description: "4 scenarios compared · TODO: wire POST /api/simulations" });
  };

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Treatment Simulator"
        description="Run the digital twin forward under different regimens and compare predicted outcomes."
        crumbs={[{ label: "Home", to: "/" }, { label: "Treatment Simulator" }]}
        actions={
          <Button onClick={run} disabled={running}>
            <Play className="size-4" aria-hidden="true" /> {running ? "Running simulation…" : "Run simulation"}
          </Button>
        }
      />

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
          {scenarios.map((s) => (
            <Card
              key={s.id}
              className={cn(
                "hover-lift relative gap-0",
                s.recommended && "border-primary ring-1 ring-primary/30",
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

                <Button variant={s.recommended ? "default" : "outline"} className="w-full">
                  Select scenario
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
