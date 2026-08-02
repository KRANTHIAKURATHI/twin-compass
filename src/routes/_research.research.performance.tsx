import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Brain, Gauge, Target } from "lucide-react";
import { performanceTrend } from "@/lib/mock-extra";

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

function PerformancePage() {
  const latest = performanceTrend[performanceTrend.length - 1];

  return (
    <div className="mx-auto max-w-[1200px]">
      <PageHeader title="Performance" description="Monthly evaluation on the held-out validation cohort." />

      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        <StatCard icon={Brain} label="AUC" value={latest.auc.toFixed(2)} delta="+0.06 YTD" />
        <StatCard icon={Target} label="Precision" value={latest.precision.toFixed(2)} delta="+0.07 YTD" tone="success" />
        <StatCard icon={Gauge} label="Recall" value={latest.recall.toFixed(2)} delta="+0.07 YTD" tone="warning" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Metric trend</CardTitle>
          <CardDescription>Rolling validation performance, Feb – Jul 2026</CardDescription>
        </CardHeader>
        <CardContent className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={performanceTrend} margin={{ left: -20 }}>
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
