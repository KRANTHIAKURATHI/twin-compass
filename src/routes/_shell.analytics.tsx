import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
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
import {
  accuracyTrend,
  ageDistribution,
  riskDistribution,
  stageDistribution,
  survivalCurve,
  treatmentComparison,
} from "@/lib/mock-data";

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

const hospitalStats = [
  { label: "Departments reporting", value: "12" },
  { label: "Oncologists onboarded", value: "86" },
  { label: "Avg. simulations / week", value: "412" },
  { label: "Median time to plan", value: "3.4 days" },
];

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

function AnalyticsPage() {
  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Analytics"
        description="Population-level insight across your hospital's breast oncology programme."
        crumbs={[{ label: "Home", to: "/" }, { label: "Analytics" }]}
      />

      <section className="mb-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {hospitalStats.map((s) => (
          <Card key={s.label} className="gap-0 p-5">
            <p className="text-sm text-muted-foreground">{s.label}</p>
            <p className="mt-2 font-display text-2xl font-semibold">{s.value}</p>
          </Card>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Age distribution" description="Patients per age band">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={ageDistribution} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis dataKey="range" tickLine={false} axisLine={false} {...axis} />
              <YAxis tickLine={false} axisLine={false} {...axis} />
              <Tooltip cursor={{ fill: "var(--color-muted)" }} contentStyle={tooltipStyle} />
              <Bar dataKey="count" fill="var(--color-chart-1)" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Cancer stage distribution" description="Diagnosed stage at intake">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={stageDistribution} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis dataKey="stage" tickLine={false} axisLine={false} {...axis} />
              <YAxis tickLine={false} axisLine={false} {...axis} />
              <Tooltip cursor={{ fill: "var(--color-muted)" }} contentStyle={tooltipStyle} />
              <Bar dataKey="count" fill="var(--color-chart-5)" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Treatment frequency" description="Response vs. recurrence by regimen (%)">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={treatmentComparison} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis dataKey="treatment" tickLine={false} axisLine={false} {...axis} interval={0} angle={-12} height={46} textAnchor="end" />
              <YAxis tickLine={false} axisLine={false} {...axis} />
              <Tooltip cursor={{ fill: "var(--color-muted)" }} contentStyle={tooltipStyle} />
              <Bar dataKey="response" fill="var(--color-chart-2)" radius={[6, 6, 0, 0]} />
              <Bar dataKey="recurrence" fill="var(--color-chart-4)" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Prediction trends" description="Ensemble accuracy over time (%)">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={accuracyTrend} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis dataKey="month" tickLine={false} axisLine={false} {...axis} />
              <YAxis domain={[80, 92]} tickLine={false} axisLine={false} {...axis} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="accuracy" stroke="var(--color-chart-1)" strokeWidth={2.5} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Risk trends" description="Current cohort stratification">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={riskDistribution} dataKey="value" nameKey="name" innerRadius={52} outerRadius={86} paddingAngle={3}>
                {riskDistribution.map((entry, i) => (
                  <Cell key={entry.key} fill={riskColors[i]} stroke="var(--color-card)" strokeWidth={2} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Survival estimates" description="5-year survival by risk group (%)">
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
        </ChartCard>
      </section>
    </div>
  );
}
