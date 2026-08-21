import { useMemo, useState } from "react";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Brain, HeartPulse, Repeat, Gauge, RefreshCw } from "lucide-react";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/common/PageHeader";
import { RiskChip, StatusChip, type ChipTone } from "@/components/common/StatusChip";
import { StateNotice } from "@/components/common/StateNotice";
import { PageErrorState } from "@/components/common/PageState";
import { ChartSkeleton, CardGridSkeleton, TableSkeleton } from "@/components/common/Skeletons";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { progressionForecast, survivalCurve } from "@/services/data";
import {
  usePatients,
  usePrediction,
  usePredictionHistory,
  useConfidenceTrend,
  useTwinVersions,
  useRunPrediction,
} from "@/hooks/api";
import type { PredictionRun, RiskLevel } from "@/types/models";

export const Route = createFileRoute("/_shell/predictions")({
  head: () => ({
    meta: [
      { title: "AI Predictions — OncoTwin" },
      { name: "description", content: "Disease progression, treatment response, survival probability and recurrence risk predictions." },
      { property: "og:title", content: "AI Predictions — OncoTwin" },
      { property: "og:description", content: "Disease progression, treatment response, survival probability and recurrence risk predictions." },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(PredictionsPage, { variant: "chart" }),
});

const axis = { stroke: "var(--color-muted-foreground)", fontSize: 12 };
const tooltipStyle = { borderRadius: 12, border: "1px solid var(--color-border)", background: "var(--color-card)", fontSize: 12 };

const statusTone: Record<PredictionRun["status"], ChipTone> = {
  Complete: "success",
  "Low confidence": "warning",
  Superseded: "neutral",
};

/** Derives a risk tier from the calibrated recurrence probability returned by the backend. */
function riskFromRecurrence(recurrence: number): RiskLevel {
  if (recurrence < 15) return "low";
  if (recurrence < 25) return "moderate";
  return "high";
}

function PredictionsPage() {
  const { data: patients, isLoading: patientsLoading, isError: patientsError } = usePatients();
  const [patientId, setPatientId] = useState<string | null>(null);
  const [twinVersion, setTwinVersion] = useState<string | null>(null);

  const activePatientId = patientId ?? patients?.[0]?.id ?? "";
  const patient = patients?.find((p) => p.id === activePatientId);

  const prediction = usePrediction(activePatientId);
  const history = usePredictionHistory(activePatientId);
  const trend = useConfidenceTrend(activePatientId);
  const versions = useTwinVersions(activePatientId);
  const runPrediction = useRunPrediction();

  const activeTwinVersion = twinVersion ?? versions.data?.[0]?.version ?? null;
  const latest = useMemo(() => {
    if (!history.data || history.data.length === 0) return prediction.data;
    return history.data.find((r) => r.twinVersion === activeTwinVersion) ?? history.data[0];
  }, [history.data, activeTwinVersion, prediction.data]);

  if (patientsLoading) return <CardGridSkeleton count={5} />;
  if (patientsError || !patients || patients.length === 0) {
    return <PageErrorState title="Could not load patients" description="Patient list is required to select a subject for prediction." />;
  }

  const lowConfidence = (latest?.confidence ?? 0) < 80 && Boolean(latest);

  const cards: {
    icon: typeof Brain;
    title: string;
    value: string;
    explanation: string;
  }[] = latest
    ? [
        {
          icon: HeartPulse,
          title: "Treatment response",
          value: latest.response,
          explanation: `Model ${latest.model} on twin ${latest.twinVersion} · run ${latest.id} (${latest.date}).`,
        },
        {
          icon: Gauge,
          title: "Survival probability",
          value: `${latest.survival}% predicted`,
          explanation: `Survival head of ${latest.model}, twin version ${latest.twinVersion}.`,
        },
        {
          icon: Repeat,
          title: "Recurrence risk",
          value: `${latest.recurrence}%`,
          explanation: `Calibrated recurrence probability from ${latest.model}.`,
        },
        {
          icon: Brain,
          title: "Prediction confidence",
          value: `${latest.confidence}% confidence`,
          explanation: `Run status: ${latest.status}.`,
        },
      ]
    : [];

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="AI Predictions"
        description="Outputs of the digital-twin models for the selected patient cohort."
        crumbs={[{ label: "Home", to: "/" }, { label: "Predictions" }]}
        actions={
          <>
            <Select value={activePatientId} onValueChange={setPatientId}>
              <SelectTrigger className="w-[220px]" aria-label="Select patient">
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
            <Select
              value={activeTwinVersion ?? undefined}
              onValueChange={setTwinVersion}
              disabled={!versions.data || versions.data.length === 0}
            >
              <SelectTrigger className="w-[150px]" aria-label="Select twin version">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {versions.data?.map((v) => (
                  <SelectItem key={v.version} value={v.version}>
                    Twin {v.version}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              onClick={() => runPrediction.mutate(activePatientId)}
              disabled={runPrediction.isPending || !activePatientId}
            >
              <RefreshCw className={runPrediction.isPending ? "size-4 animate-spin" : "size-4"} aria-hidden="true" />
              {runPrediction.isPending ? "Running…" : "Run new prediction"}
            </Button>
            <Button variant="outline" asChild>
              <Link to="/explainability">Why this prediction?</Link>
            </Button>
          </>
        }
      />

      <div className="mb-4 space-y-3">
        {prediction.isError || history.isError ? (
          <StateNotice
            state="prediction-unavailable"
            title="Prediction unavailable"
            description="The prediction service did not return a result for this patient and twin version."
          />
        ) : latest ? (
          <StateNotice
            state="model-updating"
            title={`Showing ${patient?.name ?? activePatientId} · twin ${latest.twinVersion} · ${latest.model}`}
            description={`Run ${latest.id} generated ${latest.date} — ${latest.response}, ${latest.confidence}% confidence.`}
          />
        ) : null}
        {lowConfidence && <StateNotice state="low-confidence" />}
      </div>

      {prediction.isLoading || history.isLoading ? (
        <CardGridSkeleton count={4} />
      ) : (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {cards.map((p) => {
            const tone = statusTone[latest!.status];
            const risk = riskFromRecurrence(latest!.recurrence);
            return (
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
                    <StatusChip tone={tone}>{latest!.status}</StatusChip>
                    <RiskChip level={risk} />
                  </div>
                  <div>
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>Confidence</span>
                      <span className="font-medium text-foreground">{latest!.confidence}%</span>
                    </div>
                    <Progress value={latest!.confidence} className="mt-1.5 h-1.5" />
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </section>
      )}

      <section className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Predicted progression</CardTitle>
            <CardDescription>Tumor volume with and without the recommended regimen</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={progressionForecast} margin={{ left: -20 }}>
                <defs>
                  <linearGradient id="pUn" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-chart-4)" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="var(--color-chart-4)" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="pTr" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-chart-2)" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="var(--color-chart-2)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="month" tickLine={false} axisLine={false} {...axis} />
                <YAxis tickLine={false} axisLine={false} {...axis} />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="untreated" stroke="var(--color-chart-4)" strokeWidth={2} fill="url(#pUn)" />
                <Area type="monotone" dataKey="treated" stroke="var(--color-chart-2)" strokeWidth={2} fill="url(#pTr)" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Survival probability by risk group</CardTitle>
            <CardDescription>Kaplan–Meier style estimate across risk cohorts</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={survivalCurve} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="year" tickLine={false} axisLine={false} {...axis} />
                <YAxis domain={[40, 100]} tickLine={false} axisLine={false} {...axis} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="low" stroke="var(--color-chart-2)" strokeWidth={2.5} dot={false} />
                <Line type="monotone" dataKey="moderate" stroke="var(--color-chart-3)" strokeWidth={2.5} dot={false} />
                <Line type="monotone" dataKey="high" stroke="var(--color-chart-4)" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <Card>
          <CardHeader>
            <CardTitle>Confidence trend</CardTitle>
            <CardDescription>Model confidence across twin versions</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            {trend.isLoading ? (
              <ChartSkeleton height="h-56" />
            ) : trend.isError || !trend.data || trend.data.length === 0 ? (
              <StateNotice state="prediction-unavailable" title="No confidence trend" description="No historical confidence points are available for this patient yet." />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trend.data} margin={{ left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                  <XAxis dataKey="date" tickLine={false} axisLine={false} {...axis} />
                  <YAxis domain={[50, 100]} tickLine={false} axisLine={false} {...axis} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line type="monotone" dataKey="confidence" stroke="var(--color-primary)" strokeWidth={2.5} dot />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Prediction history</CardTitle>
            <CardDescription>Previous runs for {patient?.name ?? activePatientId}</CardDescription>
          </CardHeader>
          <CardContent>
            {history.isLoading ? (
              <TableSkeleton rows={5} columns={7} />
            ) : history.isError || !history.data || history.data.length === 0 ? (
              <StateNotice state="prediction-unavailable" title="No prediction history" description="This patient has no completed prediction runs yet." />
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Run</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Twin</TableHead>
                      <TableHead>Survival</TableHead>
                      <TableHead>Recurrence</TableHead>
                      <TableHead>Confidence</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {history.data.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell className="font-medium">{r.id}</TableCell>
                        <TableCell className="text-muted-foreground">{r.date}</TableCell>
                        <TableCell>{r.twinVersion}</TableCell>
                        <TableCell>{r.survival}%</TableCell>
                        <TableCell>{r.recurrence}%</TableCell>
                        <TableCell>{r.confidence}%</TableCell>
                        <TableCell>
                          <StatusChip tone={statusTone[r.status]}>{r.status}</StatusChip>
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
