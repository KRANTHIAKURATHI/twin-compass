import { useEffect, useState } from "react";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Brain, HeartPulse, Repeat, Activity, Gauge, Play } from "lucide-react";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/common/PageHeader";
import { RiskChip, StatusChip, type ChipTone } from "@/components/common/StatusChip";
import { StateNotice } from "@/components/common/StateNotice";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  useCohortAnalytics,
  useConfidenceTrend,
  usePatient,
  usePatients,
  usePredictionHistory,
  useRunPrediction,
  useTumorSizeHistory,
} from "@/hooks/api";
import type { PredictionRun, RiskLevel } from "@/types/models";

export const Route = createFileRoute("/_shell/predictions")({
  head: () => ({
    meta: [
      { title: "AI Predictions — OncoTwin" },
      { name: "description", content: "Malignancy classification with heuristic survival and recurrence estimates (research prototype, not clinically validated)." },
      { property: "og:title", content: "AI Predictions — OncoTwin" },
      { property: "og:description", content: "Malignancy classification with heuristic survival and recurrence estimates (research prototype, not clinically validated)." },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(PredictionsPage, { variant: "chart" }),
});

const axis = { stroke: "var(--color-muted-foreground)", fontSize: 12 };
const tooltipStyle = { borderRadius: 12, border: "1px solid var(--color-border)", background: "var(--color-card)", fontSize: 12 };

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : "—");
const pct = (value?: number | null) => (value === null || value === undefined ? "—" : `${value}%`);

type Card = {
  icon: typeof Brain;
  title: string;
  value: string;
  status: string;
  tone: ChipTone;
  risk?: RiskLevel | null;
  confidence: number | null;
  explanation: string;
};

/**
 * The headline cards, built from the recorded run and the patient's own
 * record.
 *
 * These used to be five hardcoded values with "Placeholder: SHAP-based
 * attribution…" captions. Every value below is now read from a stored row, and
 * each caption says which row it came from — no card claims a model produced
 * it, because none did.
 */
function buildCards(
  run: PredictionRun | null,
  patient: { risk?: RiskLevel | null; tumorSizeMm?: number | null; currentTreatment?: string } | undefined,
  sizeHistory: Array<{ tumorSizeMm: number; version: string }>,
): Card[] {
  const first = sizeHistory[0];
  const last = sizeHistory[sizeHistory.length - 1];
  const delta = first && last && sizeHistory.length > 1 ? last.tumorSizeMm - first.tumorSizeMm : null;

  return [
    {
      icon: Activity,
      title: "Tumor size change",
      value:
        delta === null
          ? last
            ? `${last.tumorSizeMm} mm`
            : "—"
          : `${delta > 0 ? "+" : ""}${delta.toFixed(1)} mm`,
      status: delta === null ? (last ? "Single measurement" : "No measurements") : delta <= 0 ? "Shrinking" : "Growing",
      tone: delta === null ? "neutral" : delta <= 0 ? "success" : "warning",
      confidence: null,
      explanation:
        sizeHistory.length > 1
          ? `Measured across ${sizeHistory.length} twin versions (${first.version} → ${last.version}).`
          : "Measured from the twin versions on record.",
    },
    {
      icon: Gauge,
      title: "Survival estimate",
      value: run?.survival != null ? `${run.survival}%` : "—",
      status: run ? (run.survival != null ? "Estimated" : "Not recorded") : "No run yet",
      tone: run?.survival != null ? "primary" : "neutral",
      confidence: run?.confidence ?? null,
      explanation: run
        ? "Heuristic estimate — not a validated 5-year survival prediction"
        : "No prediction run has been recorded for this patient.",
    },
    {
      icon: Repeat,
      title: "Recurrence estimate",
      value: run?.recurrence != null ? `${run.recurrence}%` : "—",
      status: run ? (run.recurrence != null ? "Estimated" : "Not recorded") : "No run yet",
      tone: run?.recurrence != null ? "warning" : "neutral",
      confidence: run?.confidence ?? null,
      explanation: run
        ? "Heuristic estimate — not independently validated"
        : "No prediction run has been recorded for this patient.",
    },
    {
      icon: HeartPulse,
      title: "Current treatment",
      value: patient?.currentTreatment || "—",
      status: patient?.currentTreatment ? "On record" : "None recorded",
      tone: patient?.currentTreatment ? "success" : "neutral",
      confidence: null,
      explanation: "The regimen stored on the patient record.",
    },
    {
      icon: Brain,
      title: "Risk band",
      value: patient?.risk ? patient.risk[0].toUpperCase() + patient.risk.slice(1) : "—",
      status: run?.status ?? "No run yet",
      tone: "primary",
      risk: patient?.risk,
      confidence: run?.confidence ?? null,
      explanation: "The risk level stored on the patient record.",
    },
  ];
}

function PredictionsPage() {
  const { data: patients = [] } = usePatients();
  const [patientId, setPatientId] = useState("");

  useEffect(() => {
    if (!patientId && patients[0]) setPatientId(patients[0].id);
  }, [patients, patientId]);

  const { data: patient } = usePatient(patientId);
  const { data: history = [], isLoading: historyLoading } = usePredictionHistory(patientId);
  const { data: confidenceTrend = [] } = useConfidenceTrend(patientId);
  const { data: sizeHistory = [] } = useTumorSizeHistory(patientId);
  const { data: cohort } = useCohortAnalytics();
  const runPrediction = useRunPrediction();

  const [runId, setRunId] = useState("");
  const latest = history.find((r) => r.id === runId) ?? history[0] ?? null;
  const lowConfidence = latest?.confidence != null && latest.confidence < 80;
  const cards = buildCards(latest, patient, sizeHistory);
  const survival = cohort?.survivalByRisk;

  if (!patients.length) {
    return (
      <StateNotice
        state="prediction-unavailable"
        title="No patients yet"
        description="Add a patient record before running predictions."
      />
    );
  }

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="AI Predictions"
        description="Recorded prediction runs and measured trajectory for the selected patient."
        crumbs={[{ label: "Home", to: "/" }, { label: "Predictions" }]}
        actions={
          <>
            <Select value={patientId} onValueChange={setPatientId}>
              <SelectTrigger className="w-[220px]" aria-label="Select patient">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {patients.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name} · {p.id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {history.length > 0 && (
              <Select value={latest?.id ?? ""} onValueChange={setRunId}>
                <SelectTrigger className="w-[190px]" aria-label="Select prediction run">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {history.map((r) => (
                    <SelectItem key={r.id} value={r.id}>
                      {r.twinVersion} · {new Date(r.date).toLocaleDateString()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <Button
              onClick={() => runPrediction.mutate(patientId)}
              disabled={runPrediction.isPending || !patientId}
            >
              <Play className="size-4" aria-hidden="true" />
              {runPrediction.isPending ? "Recording…" : "Record run"}
            </Button>
            <Button variant="outline" asChild>
              <Link to="/explainability">Why this prediction?</Link>
            </Button>
          </>
        }
      />

      <div className="mb-4 space-y-3">
        {latest ? (
          <StateNotice
            state="model-updating"
            title={[
              patient?.name ?? patientId,
              latest.twinVersion && latest.twinVersion !== "none"
                ? `twin ${latest.twinVersion}`
                : "no twin version",
              latest.model,
            ]
              .filter(Boolean)
              .join(" · ")}
            description={`Run recorded ${formatDate(latest.date)} — ${
              latest.riskBand ? `${latest.riskBand} risk` : "risk not assessed"
            }, ${
              latest.confidence != null ? `${latest.confidence}% classifier confidence` : "no confidence recorded"
            }.`}
          />
        ) : (
          <StateNotice
            state="prediction-unavailable"
            title="No prediction run recorded"
            description="Use “Record run” to capture the twin's current state as a run. Values below come from the patient record."
          />
        )}
        {lowConfidence && <StateNotice state="low-confidence" />}
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((p) => (
          <Card key={p.title} className="hover-lift">
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-base">{p.title}</CardTitle>
                  <CardDescription>{p.explanation}</CardDescription>
                </div>
                <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                  <p.icon className="size-[18px]" aria-hidden="true" />
                </span>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="font-display text-2xl font-semibold">{p.value}</p>
              <div className="flex flex-wrap items-center gap-2">
                <StatusChip tone={p.tone}>{p.status}</StatusChip>
                {p.risk && <RiskChip level={p.risk} />}
              </div>
              {/* No confidence bar when nothing recorded one — an empty bar
                  reads as "0% confident", which is a different claim. */}
              {p.confidence != null && (
                <div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>Classifier confidence</span>
                    <span className="font-medium text-foreground">{p.confidence}%</span>
                  </div>
                  <Progress value={p.confidence} className="mt-1.5 h-1.5" />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Random Forest malignancy-classification probability
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Measured tumor size</CardTitle>
            <CardDescription>Size recorded on each twin version — measurements, not a forecast</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {sizeHistory.length < 2 ? (
              <div className="flex h-full items-center justify-center px-6 text-center text-sm text-muted-foreground">
                {sizeHistory.length === 1
                  ? `One measurement on record (${sizeHistory[0].tumorSizeMm} mm at ${sizeHistory[0].version}). A trend needs at least two.`
                  : "No tumor measurements recorded for this patient yet."}
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={sizeHistory} margin={{ left: -20 }}>
                  <defs>
                    <linearGradient id="pMeasured" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--color-chart-2)" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="var(--color-chart-2)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                  <XAxis dataKey="version" tickLine={false} axisLine={false} {...axis} />
                  <YAxis tickLine={false} axisLine={false} unit=" mm" {...axis} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Area
                    type="monotone"
                    dataKey="tumorSizeMm"
                    name="Tumor size (mm)"
                    stroke="var(--color-chart-2)"
                    strokeWidth={2}
                    fill="url(#pMeasured)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recorded survival estimate by risk band</CardTitle>
            <CardDescription>
              {survival?.caveat ??
                "Average of the survival estimate stored on each patient record, grouped by risk band."}{" "}
              Recorded heuristic estimates — not clinically validated.
            </CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {!survival?.points.length ? (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                No survival estimates recorded yet.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                {/* Two anchor points, not a curve: baseline and the recorded
                    probability. There is no year-by-year outcome data to draw. */}
                <LineChart data={survival.points} margin={{ left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                  <XAxis dataKey="point" tickLine={false} axisLine={false} {...axis} />
                  <YAxis domain={[0, 100]} tickLine={false} axisLine={false} unit="%" {...axis} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line
                    type="linear"
                    dataKey="low"
                    name={`Low risk (n=${survival.cohortSizes.low ?? 0})`}
                    stroke="var(--color-chart-2)"
                    strokeWidth={2.5}
                    connectNulls={false}
                  />
                  <Line
                    type="linear"
                    dataKey="moderate"
                    name={`Moderate risk (n=${survival.cohortSizes.moderate ?? 0})`}
                    stroke="var(--color-chart-3)"
                    strokeWidth={2.5}
                    connectNulls={false}
                  />
                  <Line
                    type="linear"
                    dataKey="high"
                    name={`High risk (n=${survival.cohortSizes.high ?? 0})`}
                    stroke="var(--color-chart-4)"
                    strokeWidth={2.5}
                    connectNulls={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <Card>
          <CardHeader>
            <CardTitle>Classifier confidence trend</CardTitle>
            <CardDescription>
              Random Forest malignancy-classification probability of each recorded run, oldest first — not
              confidence in survival or recurrence.
            </CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            {confidenceTrend.length === 0 ? (
              <div className="flex h-full items-center justify-center px-6 text-center text-sm text-muted-foreground">
                No run has recorded a classifier confidence value. Runs taken from twin state carry none, because no model
                produced them.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={confidenceTrend} margin={{ left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(d: string) => new Date(d).toLocaleDateString()}
                    tickLine={false}
                    axisLine={false}
                    {...axis}
                  />
                  <YAxis domain={[0, 100]} tickLine={false} axisLine={false} unit="%" {...axis} />
                  <Tooltip contentStyle={tooltipStyle} labelFormatter={(d) => formatDate(String(d))} />
                  <Line type="monotone" dataKey="confidence" stroke="var(--color-primary)" strokeWidth={2.5} dot />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Prediction history</CardTitle>
            <CardDescription>Runs recorded for {patient?.name ?? patientId}</CardDescription>
          </CardHeader>
          <CardContent>
            {historyLoading ? (
              <Skeleton className="h-48 rounded-xl" />
            ) : history.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">
                No prediction runs recorded for this patient yet.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Run</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Twin</TableHead>
                      <TableHead>Survival estimate</TableHead>
                      <TableHead>Recurrence estimate</TableHead>
                      <TableHead>Classifier confidence</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {history.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell className="font-medium">{r.id.slice(0, 8)}</TableCell>
                        <TableCell className="text-muted-foreground">{formatDate(r.date)}</TableCell>
                        <TableCell>{r.twinVersion}</TableCell>
                        <TableCell>{pct(r.survival)}</TableCell>
                        <TableCell>{pct(r.recurrence)}</TableCell>
                        <TableCell>{pct(r.confidence)}</TableCell>
                        <TableCell>
                          <StatusChip
                            tone={r.status === "Complete" ? "success" : r.status === "Low confidence" ? "warning" : "neutral"}
                          >
                            {r.status}
                          </StatusChip>
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
    </div>
  );
}
