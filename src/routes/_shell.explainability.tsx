import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Lightbulb, Minus, Plus } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { featureImportance } from "@/lib/mock-data";

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

const positive = [
  { factor: "ER positive tumor", impact: "+12% response likelihood" },
  { factor: "No distant metastasis", impact: "+9% survival probability" },
  { factor: "High treatment adherence", impact: "+6% response likelihood" },
  { factor: "Age under 55", impact: "+4% survival probability" },
];

const negative = [
  { factor: "HER2 amplification", impact: "-14% survival probability" },
  { factor: "Tumor size 42 mm", impact: "-11% response likelihood" },
  { factor: "Ki-67 index 48%", impact: "-8% response likelihood" },
  { factor: "3 positive lymph nodes", impact: "-7% survival probability" },
];

const riskBreakdown = [
  { label: "Tumor biology", value: 42 },
  { label: "Nodal involvement", value: 24 },
  { label: "Comorbidities", value: 18 },
  { label: "Treatment exposure", value: 16 },
];

function ExplainabilityPage() {
  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Explainability"
        description="Understand which clinical variables drove the model's output before acting on it."
        crumbs={[{ label: "Home", to: "/" }, { label: "Explainability" }]}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Feature importance</CardTitle>
            <CardDescription>Global attribution across the prediction ensemble (placeholder SHAP values)</CardDescription>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={featureImportance} layout="vertical" margin={{ left: 60, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
                <XAxis type="number" tickLine={false} axisLine={false} {...axis} />
                <YAxis type="category" dataKey="feature" width={140} tickLine={false} axisLine={false} {...axis} />
                <Tooltip cursor={{ fill: "var(--color-muted)" }} contentStyle={tooltipStyle} />
                <Bar dataKey="weight" radius={[0, 6, 6, 0]}>
                  {featureImportance.map((f) => (
                    <Cell
                      key={f.feature}
                      fill={f.direction === "positive" ? "var(--color-chart-2)" : "var(--color-chart-4)"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="border-primary/25 bg-primary-soft/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Lightbulb className="size-4 text-primary" aria-hidden="true" /> Prediction explanation
            </CardTitle>
            <CardDescription>Model v2.4 · generated for PT-1042</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="text-muted-foreground">
              The twin predicts a strong response to HER2-targeted therapy. HER2 amplification and tumor size dominate the
              risk score, while ER positivity and absence of metastasis push survival upward.
            </p>
            <StatusChip tone="primary">91% confidence</StatusChip>
            <p className="text-xs text-muted-foreground">
              Placeholder narrative — the FastAPI explainability endpoint will return per-patient reasoning.
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-success">Positive factors</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {positive.map((f) => (
              <div key={f.factor} className="flex items-start gap-2.5 rounded-lg bg-success-soft/60 p-2.5">
                <Plus className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
                <div>
                  <p className="text-sm font-medium">{f.factor}</p>
                  <p className="text-xs text-muted-foreground">{f.impact}</p>
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
            {negative.map((f) => (
              <div key={f.factor} className="flex items-start gap-2.5 rounded-lg bg-risk-soft/60 p-2.5">
                <Minus className="mt-0.5 size-4 shrink-0 text-risk" aria-hidden="true" />
                <div>
                  <p className="text-sm font-medium">{f.factor}</p>
                  <p className="text-xs text-muted-foreground">{f.impact}</p>
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
            {riskBreakdown.map((r) => (
              <div key={r.label}>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{r.label}</span>
                  <span className="font-medium">{r.value}%</span>
                </div>
                <Progress value={r.value} className="mt-1.5 h-1.5" />
              </div>
            ))}
            <Accordion type="single" collapsible>
              <AccordionItem value="method">
                <AccordionTrigger className="text-sm">How is this computed?</AccordionTrigger>
                <AccordionContent className="text-sm text-muted-foreground">
                  Placeholder: attribution is computed with SHAP over the ensemble and normalised to 100%. The backend will
                  expose the raw values per prediction head.
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
