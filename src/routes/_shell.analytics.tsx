import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAccuracyAnalytics, useCohortAnalytics, useDashboardAnalytics } from "@/hooks/api";
import type { DashboardStat } from "@/types/models";

export const Route = createFileRoute("/_shell/analytics")({
  head: () => ({
    meta: [
      { title: "Analytics — OncoTwin" },
      { name: "description", content: "Cohort analytics: age and stage distribution, treatment frequency, risk and survival trends." },
      { property: "og:title", content: "Analytics — OncoTwin" },
      { property: "og:description", content: "Cohort analytics: age and stage distribution, treatment frequency, risk and survival trends." },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(AnalyticsPage, { variant: "cards" }),
});

const axis = { stroke: "var(--color-muted-foreground)", fontSize: 12 };
const tooltipStyle = { borderRadius: 12, border: "1px solid var(--color-border)", background: "var(--color-card)", fontSize: 12 };
const riskColors = ["var(--color-success)", "var(--color-warning)", "var(--color-risk)"];

const statValue = (s: DashboardStat) =>
  s.value === null ? "—" : s.format === "percent" ? `${s.value}%` : String(s.value);

function ChartCard({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="h-64">{children}</CardContent>
    </Card>
  );
}

function ChartEmpty({ children }: { children: string }) {
  return (
    <div className="flex h-full items-center justify-center px-6 text-center text-sm text-muted-foreground">
      {children}
    </div>
  );
}

function AnalyticsPage() {
  const { data: cohort, isLoading } = useCohortAnalytics();
  const { data: dashboard } = useDashboardAnalytics();
  const { data: accuracy } = useAccuracyAnalytics();

  const ages = cohort?.ageDistribution ?? [];
  const stages = cohort?.stageDistribution ?? [];
  const treatments = cohort?.treatmentComparison ?? [];
  const risk = cohort?.riskDistribution ?? [];
  const survival = cohort?.survivalByRisk;
  const riskTotal = risk.reduce((sum, r) => sum + r.value, 0);

  // The four summary cards used to read "12 departments", "86 oncologists",
  // "412 simulations/week" and "3.4 days to plan" — none of which this system
  // records. These are the cohort counts the database can actually answer.
  const summary = (dashboard?.stats ?? []).filter((s) =>
    ["patients", "twins", "simulations", "survival"].includes(s.key),
  );

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Analytics"
        description="Population-level insight across your hospital's breast oncology programme."
        crumbs={[{ label: "Home", to: "/" }, { label: "Analytics" }]}
      />

      <section className="mb-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {summary.length === 0
          ? Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-[90px] rounded-xl" />)
          : summary.map((s) => (
              <Card key={s.key} className="gap-0 p-5">
                <p className="text-sm text-muted-foreground">{s.label}</p>
                <p className="mt-2 font-display text-2xl font-semibold">{statValue(s)}</p>
              </Card>
            ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Age distribution" description="Patients per age band">
          {isLoading ? (
            <Skeleton className="h-full rounded-xl" />
          ) : ages.length === 0 ? (
            <ChartEmpty>No patient carries a recorded age yet.</ChartEmpty>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={ages} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="range" tickLine={false} axisLine={false} {...axis} />
                <YAxis tickLine={false} axisLine={false} allowDecimals={false} {...axis} />
                <Tooltip cursor={{ fill: "var(--color-muted)" }} contentStyle={tooltipStyle} />
                <Bar dataKey="count" name="Patients" fill="var(--color-chart-1)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Cancer stage distribution" description="Diagnosed stage at intake">
          {isLoading ? (
            <Skeleton className="h-full rounded-xl" />
          ) : stages.length === 0 ? (
            <ChartEmpty>No patient carries a recorded stage yet.</ChartEmpty>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stages} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="stage" tickLine={false} axisLine={false} {...axis} />
                <YAxis tickLine={false} axisLine={false} allowDecimals={false} {...axis} />
                <Tooltip cursor={{ fill: "var(--color-muted)" }} contentStyle={tooltipStyle} />
                <Bar dataKey="count" name="Patients" fill="var(--color-chart-5)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard
          title="Treatment frequency"
          description="Average recorded survival vs. its complement, per regimen on file"
        >
          {isLoading ? (
            <Skeleton className="h-full rounded-xl" />
          ) : treatments.length === 0 ? (
            <ChartEmpty>No patient has a treatment recorded yet.</ChartEmpty>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={treatments} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis
                  dataKey="treatment"
                  tickLine={false}
                  axisLine={false}
                  {...axis}
                  interval={0}
                  angle={-12}
                  height={46}
                  textAnchor="end"
                />
                <YAxis tickLine={false} axisLine={false} {...axis} />
                <Tooltip
                  cursor={{ fill: "var(--color-muted)" }}
                  contentStyle={tooltipStyle}
                  labelFormatter={(label: string) => {
                    const row = treatments.find((t) => t.treatment === label);
                    return row ? `${label} (${row.runs} patients)` : label;
                  }}
                />
                <Bar dataKey="response" name="Avg. survival %" fill="var(--color-chart-2)" radius={[6, 6, 0, 0]} />
                <Bar dataKey="recurrence" name="Complement %" fill="var(--color-chart-4)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard
          title="Validation performance"
          description={
            accuracy?.model
              ? `${accuracy.model.name} v${accuracy.model.version} · cross-validation folds, not a time trend`
              : "No registered model"
          }
        >
          {!accuracy?.series.length ? (
            <ChartEmpty>No validation results are recorded for any model.</ChartEmpty>
          ) : (
            // Folds are independent samples, so they are drawn as bars. A line
            // would imply the model got better over successive months.
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={accuracy.series} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} {...axis} />
                <YAxis domain={[0, 1]} tickLine={false} axisLine={false} {...axis} />
                <Tooltip cursor={{ fill: "var(--color-muted)" }} contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="auc" name="AUC" fill="var(--color-chart-1)" radius={[6, 6, 0, 0]} />
                <Bar dataKey="precision" name="Precision" fill="var(--color-chart-2)" radius={[6, 6, 0, 0]} />
                <Bar dataKey="recall" name="Recall" fill="var(--color-chart-3)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Risk trends" description="Current cohort stratification">
          {isLoading ? (
            <Skeleton className="h-full rounded-xl" />
          ) : riskTotal === 0 ? (
            <ChartEmpty>No patient carries a recorded risk level yet.</ChartEmpty>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={risk} dataKey="value" nameKey="name" innerRadius={52} outerRadius={86} paddingAngle={3}>
                  {risk.map((entry, i) => (
                    <Cell key={entry.key} fill={riskColors[i]} stroke="var(--color-card)" strokeWidth={2} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard
          title="Survival estimates"
          description={survival?.caveat ?? "Average recorded survival probability, grouped by risk band"}
        >
          {!survival?.points.length ? (
            <ChartEmpty>No survival probabilities recorded yet.</ChartEmpty>
          ) : (
            // Two anchor points, not a six-year curve: baseline and the
            // probability actually recorded. Nothing in between was measured.
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={survival.points} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="point" tickLine={false} axisLine={false} {...axis} />
                <YAxis domain={[0, 100]} tickLine={false} axisLine={false} unit="%" {...axis} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line
                  type="linear"
                  dataKey="low"
                  name={`Low (n=${survival.cohortSizes.low ?? 0})`}
                  stroke="var(--color-chart-2)"
                  strokeWidth={2.5}
                  connectNulls={false}
                />
                <Line
                  type="linear"
                  dataKey="moderate"
                  name={`Moderate (n=${survival.cohortSizes.moderate ?? 0})`}
                  stroke="var(--color-chart-3)"
                  strokeWidth={2.5}
                  connectNulls={false}
                />
                <Line
                  type="linear"
                  dataKey="high"
                  name={`High (n=${survival.cohortSizes.high ?? 0})`}
                  stroke="var(--color-chart-4)"
                  strokeWidth={2.5}
                  connectNulls={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </section>
    </div>
  );
}
