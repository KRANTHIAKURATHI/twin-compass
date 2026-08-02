import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Brain, HeartPulse, Repeat, Activity, Gauge } from "lucide-react";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/common/PageHeader";
import { RiskChip, StatusChip, type ChipTone } from "@/components/common/StatusChip";
import { StateNotice } from "@/components/common/StateNotice";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { patients, progressionForecast, survivalCurve, type RiskLevel } from "@/lib/mock-data";
import { confidenceTrend, predictionHistory, twinVersions } from "@/lib/mock-lifecycle";


export const Route = createFileRoute("/_shell/predictions")({
  head: () => ({
    meta: [
      { title: "AI Predictions — OncoTwin" },
      { name: "description", content: "Disease progression, treatment response, survival probability and recurrence risk predictions." },
      { property: "og:title", content: "AI Predictions — OncoTwin" },
      { property: "og:description", content: "Disease progression, treatment response, survival probability and recurrence risk predictions." },
    ],
  }),
  component: PredictionsPage,
});

const axis = { stroke: "var(--color-muted-foreground)", fontSize: 12 };
const tooltipStyle = { borderRadius: 12, border: "1px solid var(--color-border)", background: "var(--color-card)", fontSize: 12 };

const predictions: {
  icon: typeof Brain;
  title: string;
  value: string;
  status: string;
  tone: ChipTone;
  risk: RiskLevel;
  confidence: number;
  explanation: string;
}[] = [
  {
    icon: Activity,
    title: "Disease progression",
    value: "Slow progression",
    status: "Stable",
    tone: "success",
    risk: "low",
    confidence: 89,
    explanation: "Placeholder: model rationale will be returned by the FastAPI inference endpoint.",
  },
  {
    icon: HeartPulse,
    title: "Treatment response",
    value: "84% response",
    status: "Likely responder",
    tone: "success",
    risk: "low",
    confidence: 91,
    explanation: "Placeholder: SHAP-based attribution to be supplied by the explainability service.",
  },
  {
    icon: Gauge,
    title: "Survival probability",
    value: "88% at 5 years",
    status: "Favourable",
    tone: "primary",
    risk: "low",
    confidence: 86,
    explanation: "Placeholder: survival head of the digital-twin model (Cox + neural ODE ensemble).",
  },
  {
    icon: Repeat,
    title: "Recurrence risk",
    value: "17%",
    status: "Monitor",
    tone: "warning",
    risk: "moderate",
    confidence: 78,
    explanation: "Placeholder: recurrence classifier output with calibrated probability.",
  },
  {
    icon: Brain,
    title: "Prediction confidence",
    value: "86% average",
    status: "Model v2.4",
    tone: "primary",
    risk: "low",
    confidence: 86,
    explanation: "Placeholder: ensemble agreement across the five prediction heads.",
  },
];

function PredictionsPage() {
  const [patientId, setPatientId] = useState(patients[0].id);
  const [twinVersion, setTwinVersion] = useState(twinVersions[0].version);
  const patient = patients.find((p) => p.id === patientId)!;
  const latest = predictionHistory.find((r) => r.twinVersion === twinVersion) ?? predictionHistory[0];
  const lowConfidence = latest.confidence < 80;

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="AI Predictions"
        description="Outputs of the digital-twin models for the selected patient cohort."
        crumbs={[{ label: "Home", to: "/" }, { label: "Predictions" }]}
        actions={
          <>
            <Select value={patientId} onValueChange={setPatientId}>
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
            <Select value={twinVersion} onValueChange={setTwinVersion}>
              <SelectTrigger className="w-[150px]" aria-label="Select twin version">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {twinVersions.map((v) => (
                  <SelectItem key={v.version} value={v.version}>
                    Twin {v.version}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" asChild>
              <Link to="/explainability">Why this prediction?</Link>
            </Button>
          </>
        }
      />

      <div className="mb-4 space-y-3">
        <StateNotice
          state="model-updating"
          title={`Showing ${patient.name} · twin ${twinVersion} · ${latest.model}`}
          description={`Run ${latest.id} generated ${latest.date} — ${latest.response}, ${latest.confidence}% confidence.`}
        />
        {lowConfidence && <StateNotice state="low-confidence" />}
      </div>


      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {predictions.map((p) => (
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
                <RiskChip level={p.risk} />
              </div>
              <div>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Confidence</span>
                  <span className="font-medium text-foreground">{p.confidence}%</span>
                </div>
                <Progress value={p.confidence} className="mt-1.5 h-1.5" />
              </div>
            </CardContent>
          </Card>
        ))}
      </section>

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
            <CardDescription>Placeholder Kaplan–Meier style estimate</CardDescription>
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
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={confidenceTrend} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="date" tickLine={false} axisLine={false} {...axis} />
                <YAxis domain={[50, 100]} tickLine={false} axisLine={false} {...axis} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="confidence" stroke="var(--color-primary)" strokeWidth={2.5} dot />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Prediction history</CardTitle>
            <CardDescription>Previous runs for {patient.name}</CardDescription>
          </CardHeader>
          <CardContent>
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
                  {predictionHistory.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="font-medium">{r.id}</TableCell>
                      <TableCell className="text-muted-foreground">{r.date}</TableCell>
                      <TableCell>{r.twinVersion}</TableCell>
                      <TableCell>{r.survival}%</TableCell>
                      <TableCell>{r.recurrence}%</TableCell>
                      <TableCell>{r.confidence}%</TableCell>
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
          </CardContent>
        </Card>
      </section>

    </div>
  );
}
