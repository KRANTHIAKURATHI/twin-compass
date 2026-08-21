import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates, PageErrorState } from "@/components/common/PageState";
import { Lightbulb, Minus, Plus } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/common/PageHeader";
import { StateNotice } from "@/components/common/StateNotice";
import { StatusChip } from "@/components/common/StatusChip";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { CardGridSkeleton, ChartSkeleton } from "@/components/common/Skeletons";
import { usePatients, usePrediction, useExplainability } from "@/hooks/api";

export const Route = createFileRoute("/_shell/explainability")({
  head: () => ({
    meta: [
      { title: "Model Explainability — OncoTwin" },
      { name: "description", content: "Feature importance, influencing factors and risk breakdown behind each AI prediction." },
      { property: "og:title", content: "Model Explainability — OncoTwin" },
      { property: "og:description", content: "Feature importance, influencing factors and risk breakdown behind each AI prediction." },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(ExplainabilityPage, { variant: "chart" }),
});

const axis = { stroke: "var(--color-muted-foreground)", fontSize: 12 };
const tooltipStyle = { borderRadius: 12, border: "1px solid var(--color-border)", background: "var(--color-card)", fontSize: 12 };

function ExplainabilityPage() {
  const { data: patients, isLoading: patientsLoading, isError: patientsError } = usePatients();
  const [patientId, setPatientId] = useState<string | null>(null);
  const activePatientId = patientId ?? patients?.[0]?.id ?? "";
  const patient = patients?.find((p) => p.id === activePatientId);

  const explain = useExplainability(activePatientId);
  const prediction = usePrediction(activePatientId);

  const { positive, negative, total } = useMemo(() => {
    const features = explain.data ?? [];
    const total = features.reduce((sum, f) => sum + Math.abs(f.weight), 0) || 1;
    return {
      positive: features.filter((f) => f.direction === "positive").sort((a, b) => b.weight - a.weight),
      negative: features.filter((f) => f.direction === "negative").sort((a, b) => b.weight - a.weight),
      total,
    };
  }, [explain.data]);

  if (patientsLoading) return <CardGridSkeleton count={3} />;
  if (patientsError || !patients || patients.length === 0) {
    return <PageErrorState title="Could not load patients" description="Patient list is required to select a subject for explainability." />;
  }

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Explainability"
        description="Understand which clinical variables drove the model's output before acting on it."
        crumbs={[{ label: "Home", to: "/" }, { label: "Explainability" }]}
        actions={
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
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Feature importance</CardTitle>
            <CardDescription>Global attribution across the prediction ensemble for {patient?.name ?? activePatientId}</CardDescription>
          </CardHeader>
          <CardContent className="h-80">
            {explain.isLoading ? (
              <ChartSkeleton height="h-64" />
            ) : explain.isError || !explain.data || explain.data.length === 0 ? (
              <StateNotice
                state="prediction-unavailable"
                title="No attribution available"
                description="The explainability endpoint has not returned feature attribution for this patient yet."
              />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={explain.data} layout="vertical" margin={{ left: 60, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
                  <XAxis type="number" tickLine={false} axisLine={false} {...axis} />
                  <YAxis type="category" dataKey="feature" width={140} tickLine={false} axisLine={false} {...axis} />
                  <Tooltip cursor={{ fill: "var(--color-muted)" }} contentStyle={tooltipStyle} />
                  <Bar dataKey="weight" radius={[0, 6, 6, 0]}>
                    {explain.data.map((f) => (
                      <Cell
                        key={f.feature}
                        fill={f.direction === "positive" ? "var(--color-chart-2)" : "var(--color-chart-4)"}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card className="border-primary/25 bg-primary-soft/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Lightbulb className="size-4 text-primary" aria-hidden="true" /> Prediction explanation
            </CardTitle>
            <CardDescription>
              {prediction.data ? `Model ${prediction.data.model} · generated for ${activePatientId}` : `Generated for ${activePatientId}`}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {positive.length === 0 && negative.length === 0 ? (
              <p className="text-muted-foreground">No per-patient reasoning is available yet for this prediction.</p>
            ) : (
              <p className="text-muted-foreground">
                {positive[0] ? `${positive[0].feature} pushes the outcome upward` : "No positive drivers identified"}
                {negative[0] ? `, while ${negative[0].feature} weighs it down` : ""}
                {positive[0] || negative[0] ? "." : ""}
                {" "}Attribution is derived from {positive.length + negative.length} ranked features in the model's SHAP output.
              </p>
            )}
            {prediction.data && <StatusChip tone="primary">{prediction.data.confidence}% confidence</StatusChip>}
          </CardContent>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-success">Positive factors</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {positive.length === 0 && <p className="text-sm text-muted-foreground">No positive-direction features returned.</p>}
            {positive.map((f) => (
              <div key={f.feature} className="flex items-start gap-2.5 rounded-lg bg-success-soft/60 p-2.5">
                <Plus className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
                <div>
                  <p className="text-sm font-medium">{f.feature}</p>
                  <p className="text-xs text-muted-foreground">{Math.round((f.weight / total) * 100)}% attribution weight</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base text-risk">Negative factors</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {negative.length === 0 && <p className="text-sm text-muted-foreground">No negative-direction features returned.</p>}
            {negative.map((f) => (
              <div key={f.feature} className="flex items-start gap-2.5 rounded-lg bg-risk-soft/60 p-2.5">
                <Minus className="mt-0.5 size-4 shrink-0 text-risk" aria-hidden="true" />
                <div>
                  <p className="text-sm font-medium">{f.feature}</p>
                  <p className="text-xs text-muted-foreground">{Math.round((f.weight / total) * 100)}% attribution weight</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Risk breakdown</CardTitle>
            <CardDescription>Contribution to the composite risk score</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {(explain.data ?? []).slice(0, 4).map((f) => (
              <div key={f.feature}>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{f.feature}</span>
                  <span className="font-medium">{Math.round((f.weight / total) * 100)}%</span>
                </div>
                <Progress value={Math.round((f.weight / total) * 100)} className="mt-1.5 h-1.5" />
              </div>
            ))}
            <Accordion type="single" collapsible>
              <AccordionItem value="method">
                <AccordionTrigger className="text-sm">How is this computed?</AccordionTrigger>
                <AccordionContent className="text-sm text-muted-foreground">
                  Attribution weights are returned per feature by the explainability endpoint and normalised here to a
                  percentage of the total absolute weight across the ranked feature set.
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
