import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Brain, Gauge, LineChart as TrendIcon, Target } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { PageErrorState, PageSkeleton } from "@/components/common/PageState";
import { useResearchPerformance } from "@/hooks/api";

export const Route = createFileRoute("/_research/research/performance")({
  head: () => ({
    meta: [
      { title: "Model Performance — OncoTwin Research" },
      { name: "description", content: "AUC, precision and recall trends for the production digital twin model suite." },
      { property: "og:title", content: "Model Performance — OncoTwin Research" },
      { property: "og:description", content: "AUC, precision and recall trends for the production digital twin model suite." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(PerformancePage, { variant: "cards" }),
});

const axis = { stroke: "var(--color-muted-foreground)", fontSize: 12 };

const num = (v: unknown) => (typeof v === "number" ? v : v == null ? null : Number(v));
const fmt = (v: unknown) => (num(v) == null ? "—" : (num(v) as number).toFixed(2));
/** Change from the first to the latest recorded point, or undefined when it cannot be computed. */
const change = (first: unknown, last: unknown, points: number) => {
  const a = num(first);
  const b = num(last);
  if (a == null || b == null || points < 2) return undefined;
  const d = b - a;
  return `${d >= 0 ? "+" : ""}${d.toFixed(2)} since first record`;
};

function PerformancePage() {
  const { data = [], isLoading, isError, refetch } = useResearchPerformance();
  const header = <PageHeader title="Performance" description="Evaluation on the held-out validation cohort, as recorded on the server." />;

  if (isLoading) return <div className="mx-auto max-w-[1200px]">{header}<PageSkeleton variant="list" /></div>;
  if (isError)
    return (
      <div className="mx-auto max-w-[1200px]">
        {header}
        <PageErrorState onRetry={() => void refetch()} />
      </div>
    );
  if (data.length === 0)
    return (
      <div className="mx-auto max-w-[1200px]">
        {header}
        <EmptyState icon={TrendIcon} title="No performance metrics recorded" description="No model evaluation results have been recorded yet." />
      </div>
    );

  const points = data;
  const first = points[0]!;
  const latest = points[points.length - 1]!;

  return (
    <div className="mx-auto max-w-[1200px]">
      {header}

      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        <StatCard icon={Brain} label="AUC" value={fmt(latest.auc)} delta={change(first.auc, latest.auc, points.length)} />
        <StatCard icon={Target} label="Precision" value={fmt(latest.precision)} delta={change(first.precision, latest.precision, points.length)} tone="success" />
        <StatCard icon={Gauge} label="Recall" value={fmt(latest.recall)} delta={change(first.recall, latest.recall, points.length)} tone="warning" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Metric trend</CardTitle>
          <CardDescription>Validation performance, {first.month} – {latest.month}</CardDescription>
        </CardHeader>
        <CardContent className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis dataKey="month" tickLine={false} axisLine={false} {...axis} />
              <YAxis domain={[0.7, 1]} tickLine={false} axisLine={false} {...axis} />
              <Tooltip
                contentStyle={{
                  borderRadius: 12,
                  border: "1px solid var(--color-border)",
                  background: "var(--color-card)",
                  fontSize: 12,
                }}
              />
              <Legend />
              <Line type="monotone" dataKey="auc" stroke="var(--color-chart-1)" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="precision" stroke="var(--color-chart-2)" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="recall" stroke="var(--color-chart-4)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}
