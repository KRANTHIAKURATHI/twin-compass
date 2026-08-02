import { createFileRoute, Link } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Activity, CalendarDays, FileText, HeartPulse, Syringe } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { StatusChip } from "@/components/common/StatusChip";
import { Timeline } from "@/components/common/Timeline";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { patients, progressionForecast } from "@/lib/mock-data";
import { appointments, treatmentPlan } from "@/lib/mock-extra";

export const Route = createFileRoute("/_patient/portal/")({
  head: () => ({
    meta: [
      { title: "My Health Dashboard — OncoTwin Patient Portal" },
      { name: "description", content: "Track your treatment progress, upcoming appointments and reports in one place." },
      { property: "og:title", content: "My Health Dashboard — OncoTwin Patient Portal" },
      { property: "og:description", content: "Track your treatment progress, upcoming appointments and reports in one place." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(PatientDashboard, { variant: "cards" }),
});

const me = patients[0];

function PatientDashboard() {
  const next = appointments.find((a) => a.status !== "Completed")!;

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
        <StatCard label="Treatment cycle" value={`${treatmentPlan.cycle} of ${treatmentPlan.totalCycles}`} icon={Syringe} />
        <StatCard label="Next appointment" value={next.date} icon={CalendarDays} tone="success" />
        <StatCard label="Plan adherence" value={`${treatmentPlan.adherence}%`} icon={HeartPulse} tone="success" />
        <StatCard label="Reports on file" value={String(me.reports.length)} icon={FileText} tone="primary" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Your progress</CardTitle>
            <CardDescription>Tumor measurement trend from your imaging reports (mm)</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={progressionForecast} margin={{ left: -20 }}>
                <defs>
                  <linearGradient id="pTreated" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-chart-2)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="var(--color-chart-2)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="month" tickLine={false} axisLine={false} stroke="var(--color-muted-foreground)" fontSize={12} />
                <YAxis tickLine={false} axisLine={false} stroke="var(--color-muted-foreground)" fontSize={12} />
                <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid var(--color-border)", background: "var(--color-card)", fontSize: 12 }} />
                <Area type="monotone" dataKey="treated" stroke="var(--color-chart-2)" strokeWidth={2} fill="url(#pTreated)" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="size-4 text-primary" aria-hidden="true" /> Care plan
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium">{treatmentPlan.regimen}</p>
              <p className="text-xs text-muted-foreground">Started {treatmentPlan.startedOn}</p>
            </div>
            <div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Cycles completed</span>
                <span className="font-semibold">
                  {treatmentPlan.cycle}/{treatmentPlan.totalCycles}
                </span>
              </div>
              <Progress value={(treatmentPlan.cycle / treatmentPlan.totalCycles) * 100} className="mt-2 h-2" />
            </div>
            <div className="rounded-xl border border-border p-3">
              <p className="text-xs text-muted-foreground">Next session</p>
              <p className="text-sm font-medium">{next.title}</p>
              <p className="text-xs text-muted-foreground">
                {next.date} · {next.time} · {next.location}
              </p>
              <StatusChip tone="primary" className="mt-2">
                {next.status}
              </StatusChip>
            </div>
            <Button variant="outline" className="w-full" asChild>
              <Link to="/portal/treatment">View my treatment</Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>My care timeline</CardTitle>
          <CardDescription>Key events recorded by your care team</CardDescription>
        </CardHeader>
        <CardContent>
          <Timeline items={me.timeline} />
        </CardContent>
      </Card>
    </div>
  );
}
