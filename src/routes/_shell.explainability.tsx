import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Lightbulb, Minus, Plus } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { StateNotice } from "@/components/common/StateNotice";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { useExplainability, usePatients, usePrediction } from "@/hooks/api";
import type { FeatureImportance } from "@/types/models";

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

const asPercent = (weight: number) => Math.round(weight * 1000) / 10;

/**
 * How a factor reads next to the patient's own value.
 *
 * The weight says how strongly the factor tracks recorded survival across the
 * cohort; `direction` says which way. Both come from the correlation, so the
 * wording stays correlational — "tracks with", never "causes" or "adds".
 */
const impactLabel = (f: FeatureImportance) => {
  const value = f.patientValue === null || f.patientValue === undefined || f.patientValue === "" ? "—" : f.patientValue;
  const r = f.correlation === undefined ? "" : ` · r=${f.correlation}`;
  return `This patient: ${value} · ${asPercent(f.weight)}% of cohort weight${r}`;
};

function ExplainabilityPage() {
  const { data: patients = [] } = usePatients();
  const [patientId, setPatientId] = useState("");

  useEffect(() => {
    if (!patientId && patients[0]) setPatientId(patients[0].id);
  }, [patients, patientId]);

  const { data: explain, isLoading } = useExplainability(patientId);
  const { data: latest } = usePrediction(patientId);

  const factors = explain?.factors ?? [];
  const positive = factors.filter((f) => f.direction === "positive");
  const negative = factors.filter((f) => f.direction === "negative");
  // The chart reads best with the strongest factors at the top; the full set
  // stays available in the two lists below.
  const chartData = factors.slice(0, 8).map((f) => ({ ...f, percent: asPercent(f.weight) }));
  const patient = patients.find((p) => p.id === patientId);

  if (!patients.length) {
    return (
      <StateNotice
        state="prediction-unavailable"
        title="No patients yet"
        description="Cohort statistics need patient records to compute against."
      />
    );
  }

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Explainability"
        description="Which recorded clinical variables track with survival across this cohort."
        crumbs={[{ label: "Home", to: "/" }, { label: "Explainability" }]}
        actions={
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
        }
      />

      {/* Stated up front, not buried: these are cohort correlations, and with a
          small cohort they are not stable. */}
      {explain && explain.reliability !== "reasonable" && (
        <StateNotice
          state={explain.reliability === "insufficient" ? "prediction-unavailable" : "low-confidence"}
          title={
            explain.reliability === "insufficient"
              ? "Not enough records to compute factor weights"
              : `Indicative only — ${explain.cohortSize} patient records`
          }
          description={explain.caveat}
          className="mb-4"
        />
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Factor weights across the cohort</CardTitle>
            <CardDescription>
              {explain
                ? `Correlation with recorded survival across ${explain.cohortSize} patient records, normalised to relative weights`
                : "Correlation with recorded survival across the patient records in this database"}
            </CardDescription>
          </CardHeader>
          <CardContent className="h-80">
            {isLoading ? (
              <Skeleton className="h-full rounded-xl" />
            ) : chartData.length === 0 ? (
              <div className="flex h-full items-center justify-center px-6 text-center text-sm text-muted-foreground">
                {explain?.caveat ?? "No factor weights could be computed from the records on file."}
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} layout="vertical" margin={{ left: 60, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
                  <XAxis type="number" unit="%" tickLine={false} axisLine={false} {...axis} />
                  <YAxis type="category" dataKey="feature" width={140} tickLine={false} axisLine={false} {...axis} />
                  <Tooltip
                    cursor={{ fill: "var(--color-muted)" }}
                    contentStyle={tooltipStyle}
                    formatter={(v: number) => [`${v}% of cohort weight`, "Weight"]}
                  />
                  <Bar dataKey="percent" radius={[0, 6, 6, 0]}>
                    {chartData.map((f) => (
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
              <Lightbulb className="size-4 text-primary" aria-hidden="true" /> What this is
            </CardTitle>
            <CardDescription>
              {patient ? `${patient.name} · ${patient.id}` : patientId}
              {explain ? ` · cohort of ${explain.cohortSize}` : ""}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="text-muted-foreground">
              {explain?.caveat ?? "Loading cohort statistics…"}
            </p>
            {latest ? (
              <>
                <div className="flex flex-wrap gap-2">
                  <StatusChip tone="primary">{latest.model}</StatusChip>
                  {latest.confidence != null && <StatusChip tone="neutral">{latest.confidence}% confidence</StatusChip>}
                </div>
                <p className="text-xs text-muted-foreground">
                  Last run {new Date(latest.date).toLocaleString()} recorded {latest.survival}% survival. The weights
                  above are not an attribution of that run.
                </p>
              </>
            ) : (
              <p className="text-xs text-muted-foreground">
                No prediction run recorded for this patient, so there is nothing to attribute. The weights above
                describe the cohort either way.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-success">Tracks with better survival</CardTitle>
            <CardDescription>Positive correlation across the cohort</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {positive.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">None computed.</p>
            ) : (
              positive.map((f) => (
                <div key={f.feature} className="flex items-start gap-2.5 rounded-lg bg-success-soft/60 p-2.5">
                  <Plus className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{f.feature}</p>
                    <p className="text-xs text-muted-foreground">{impactLabel(f)}</p>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base text-risk">Tracks with worse survival</CardTitle>
            <CardDescription>Negative correlation across the cohort</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {negative.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">None computed.</p>
            ) : (
              negative.map((f) => (
                <div key={f.feature} className="flex items-start gap-2.5 rounded-lg bg-risk-soft/60 p-2.5">
                  <Minus className="mt-0.5 size-4 shrink-0 text-risk" aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{f.feature}</p>
                    <p className="text-xs text-muted-foreground">{impactLabel(f)}</p>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Weight breakdown</CardTitle>
            <CardDescription>Share of total cohort weight per factor</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {factors.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">Nothing to break down yet.</p>
            ) : (
              factors.slice(0, 5).map((f) => (
                <div key={f.feature}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{f.feature}</span>
                    <span className="font-medium">{asPercent(f.weight)}%</span>
                  </div>
                  <Progress value={asPercent(f.weight)} className="mt-1.5 h-1.5" />
                </div>
              ))
            )}
            <Accordion type="single" collapsible>
              <AccordionItem value="method">
                <AccordionTrigger className="text-sm">How is this computed?</AccordionTrigger>
                <AccordionContent className="space-y-2 text-sm text-muted-foreground">
                  <p>
                    Each factor's value is correlated (Pearson) against the survival probability recorded on every
                    non-deleted patient record. ER, PR and HER2 status are encoded as 1 for positive, 0 otherwise. The
                    absolute correlations are then normalised to sum to 100%, which is the weight shown.
                  </p>
                  <p>
                    This is a descriptive statistic about the patients in this database. It is not SHAP, and it is not
                    an explanation of any individual prediction — no trained model is attached to this deployment.
                  </p>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
