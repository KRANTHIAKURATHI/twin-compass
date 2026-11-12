import { createFileRoute, Link } from "@tanstack/react-router";
import { PageErrorState, PageSkeleton, RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Activity, FileText, HeartPulse, Ruler, Syringe, User } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { Timeline } from "@/components/common/Timeline";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useDocuments, usePatients, usePatientTimeline, useTreatmentPlan, useTumorSizeHistory } from "@/hooks/api";
import type { TreatmentPlan } from "@/types/models";

export const Route = createFileRoute("/_patient/portal/")({
  head: () => ({
    meta: [
      { title: "My Health Dashboard — OncoTwin Patient Portal" },
      { name: "description", content: "Track your treatment progress and reports in one place." },
      { property: "og:title", content: "My Health Dashboard — OncoTwin Patient Portal" },
      { property: "og:description", content: "Track your treatment progress and reports in one place." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(PatientDashboard, { variant: "cards" }),
});

function PatientDashboard() {
  const patients = usePatients();
  const me = patients.data?.[0];
  const id = me?.id ?? "";
  const planQuery = useTreatmentPlan(id);
  const documents = useDocuments();
  const history = useTumorSizeHistory(id);
  const timeline = usePatientTimeline(id);

  if (patients.isLoading)
    return (
      <div className="mx-auto max-w-[1200px]">
        <PageSkeleton variant="cards" />
      </div>
    );
  if (patients.isError)
    return (
      <div className="mx-auto max-w-[1200px] pt-4">
        <PageErrorState onRetry={() => void patients.refetch()} />
      </div>
    );
  if (!me)
    return (
      <div className="mx-auto max-w-[1200px] pt-4">
        <EmptyState icon={User} title="No patient record found" description="No patient record is linked to your account yet." />
      </div>
    );

  // The backend returns null when no plan is recorded.
  const plan = (planQuery.data ?? null) as TreatmentPlan | null;
  const points = history.data ?? [];

  return (
    <div className="mx-auto max-w-[1200px]">
      <PageHeader
        title={`Hello, ${me.name.split(" ")[0]}`}
        description="Here is a summary of your care plan and recent activity."
        actions={
          <Button asChild>
            <Link to="/portal/upload">Upload a report</Link>
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Treatment cycle"
          value={plan ? `${plan.cycle} of ${plan.totalCycles}` : planQuery.isError ? "Unavailable" : "Not recorded"}
          icon={Syringe}
        />
        <StatCard
          label="Latest tumor size"
          value={me.tumorSizeMm == null ? "Not recorded" : `${me.tumorSizeMm} mm`}
          icon={Ruler}
          tone="success"
        />
        <StatCard label="Plan adherence" value={plan ? `${plan.adherence}%` : "Not recorded"} icon={HeartPulse} tone="success" />
        <StatCard
          label="Reports on file"
          value={documents.isError ? "Unavailable" : documents.isLoading ? "…" : String((documents.data ?? []).length)}
          icon={FileText}
          tone="primary"
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Your progress</CardTitle>
            <CardDescription>Recorded tumor measurements over time (mm)</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            {history.isLoading ? (
              <PageSkeleton variant="list" />
            ) : history.isError ? (
              <PageErrorState onRetry={() => void history.refetch()} />
            ) : points.length === 0 ? (
              <EmptyState icon={Activity} title="No measurements recorded" description="Tumor measurements will appear here once they are recorded." />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={points} margin={{ left: -20 }}>
                  <defs>
                    <linearGradient id="pTreated" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--color-chart-2)" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="var(--color-chart-2)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                  <XAxis dataKey="date" tickLine={false} axisLine={false} stroke="var(--color-muted-foreground)" fontSize={12} />
                  <YAxis tickLine={false} axisLine={false} stroke="var(--color-muted-foreground)" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      borderRadius: 12,
                      border: "1px solid var(--color-border)",
                      background: "var(--color-card)",
                      fontSize: 12,
                    }}
                  />
                  <Area type="monotone" dataKey="tumorSizeMm" stroke="var(--color-chart-2)" strokeWidth={2} fill="url(#pTreated)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="size-4 text-primary" aria-hidden="true" /> Care plan
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {planQuery.isError ? (
              <PageErrorState onRetry={() => void planQuery.refetch()} />
            ) : !plan ? (
              <p className="text-sm text-muted-foreground">No treatment plan has been recorded yet.</p>
            ) : (
              <>
                <div>
                  <p className="text-sm font-medium">{plan.regimen}</p>
                  <p className="text-xs text-muted-foreground">Started {plan.startedOn}</p>
                </div>
                <div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Cycles completed</span>
                    <span className="font-semibold">
                      {plan.cycle}/{plan.totalCycles}
                    </span>
                  </div>
                  <Progress value={plan.totalCycles ? (plan.cycle / plan.totalCycles) * 100 : 0} className="mt-2 h-2" />
                </div>
                <div className="rounded-xl border border-border p-3">
                  <p className="text-xs text-muted-foreground">Next dose</p>
                  <p className="text-sm font-medium">{plan.nextDose || "Not scheduled"}</p>
                </div>
                <Button variant="outline" className="w-full" asChild>
                  <Link to="/portal/treatment">View my treatment</Link>
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>My care timeline</CardTitle>
          <CardDescription>Key events recorded by your care team</CardDescription>
        </CardHeader>
        <CardContent>
          {timeline.isLoading ? (
            <PageSkeleton variant="list" />
          ) : timeline.isError ? (
            <PageErrorState onRetry={() => void timeline.refetch()} />
          ) : (timeline.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No events recorded yet.</p>
          ) : (
            <Timeline items={timeline.data ?? []} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
