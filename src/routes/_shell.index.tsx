import { createFileRoute, Link } from "@tanstack/react-router";
import { PageErrorState, PageSkeleton, RouteErrorState, withPageStates } from "@/components/common/PageState";
import {
  Users,
  Boxes,
  AlertTriangle,
  FlaskConical,
  CheckCircle2,
  HeartPulse,
  ArrowUpRight,
  CalendarClock,
  Bell,
} from "lucide-react";
import {
  Area,
  AreaChart,
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
import { StatCard } from "@/components/common/StatCard";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { EmptyState } from "@/components/common/EmptyState";
// No backend endpoint currently returns a response-vs-recurrence breakdown by
// treatment regimen — analyticsService only exposes dashboard/cohort/accuracy
// series — so this one chart stays sourced from fixtures until the API adds one.
import { treatmentComparison } from "@/services/data";
import {
  useAccuracyAnalytics,
  useAppointments,
  useCohortAnalytics,
  useDashboardAnalytics,
  useNotifications,
  usePatients,
  useSimulationRuns,
  useTwins,
} from "@/hooks/api";
import type { RiskLevel } from "@/types/models";

export const Route = createFileRoute("/_shell/")({
  head: () => ({
    meta: [
      { title: "Clinical Dashboard — OncoTwin" },
      { name: "description", content: "Executive overview of patients, digital twins, simulations and prediction accuracy." },
      { property: "og:title", content: "Clinical Dashboard — OncoTwin" },
      { property: "og:description", content: "Executive overview of patients, digital twins, simulations and prediction accuracy." },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(DashboardPage, { variant: "cards" }),
});

const riskColors = ["var(--color-success)", "var(--color-warning)", "var(--color-risk)"];
const riskOrder: { key: RiskLevel; name: string }[] = [
  { key: "low", name: "Low risk" },
  { key: "moderate", name: "Moderate risk" },
  { key: "high", name: "High risk" },
];

const notificationTone: Record<string, "primary" | "success" | "warning" | "risk"> = {
  patient: "primary",
  prediction: "success",
  twin: "primary",
  simulation: "warning",
  system: "risk",
};

const axis = { stroke: "var(--color-muted-foreground)", fontSize: 12 };
const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid var(--color-border)",
  background: "var(--color-card)",
  color: "var(--color-card-foreground)",
  fontSize: 12,
};

function DashboardPage() {
  const patientsQuery = usePatients();
  const twinsQuery = useTwins();
  const simulationsQuery = useSimulationRuns();
  const growthQuery = useDashboardAnalytics();
  const cohortQuery = useCohortAnalytics();
  const accuracyQuery = useAccuracyAnalytics();
  const appointmentsQuery = useAppointments();
  const notificationsQuery = useNotifications("doctor");

  const loading =
    patientsQuery.isLoading ||
    twinsQuery.isLoading ||
    simulationsQuery.isLoading ||
    growthQuery.isLoading ||
    cohortQuery.isLoading ||
    accuracyQuery.isLoading;

  const error =
    patientsQuery.isError ||
    twinsQuery.isError ||
    simulationsQuery.isError ||
    growthQuery.isError ||
    cohortQuery.isError ||
    accuracyQuery.isError;

  if (loading) return <PageSkeleton variant="cards" />;
  if (error)
    return (
      <div className="mx-auto max-w-[900px] pt-4">
        <PageErrorState />
      </div>
    );

  const patients = patientsQuery.data ?? [];
  const twins = twinsQuery.data ?? [];
  const simulations = simulationsQuery.data ?? [];
  const patientGrowth = growthQuery.data ?? [];
  const stageDistribution = cohortQuery.data ?? [];
  const accuracyTrend = accuracyQuery.data ?? [];
  const appointments = appointmentsQuery.data ?? [];
  const notifications = notificationsQuery.data ?? [];

  const riskDistribution = riskOrder.map((r) => ({
    ...r,
    value: patients.filter((p) => p.risk === r.key).length,
  }));

  const avgSurvival = patients.length
    ? Math.round((patients.reduce((sum, p) => sum + p.survivalProbability, 0) / patients.length) * 10) / 10
    : 0;

  const latestAccuracy = accuracyTrend.length ? Number(accuracyTrend[accuracyTrend.length - 1].accuracy) : null;

  const dashboardStats = [
    { label: "Total Patients", value: patients.length.toLocaleString(), icon: Users, tone: "primary" as const },
    { label: "Active Digital Twins", value: twins.length.toLocaleString(), icon: Boxes, tone: "primary" as const },
    {
      label: "High Risk Patients",
      value: patients.filter((p) => p.risk === "high").length.toLocaleString(),
      icon: AlertTriangle,
      tone: "risk" as const,
    },
    { label: "Treatment Simulations", value: simulations.length.toLocaleString(), icon: FlaskConical, tone: "primary" as const },
    {
      label: "Latest Prediction Accuracy",
      value: latestAccuracy !== null ? `${latestAccuracy}%` : "—",
      icon: CheckCircle2,
      tone: "success" as const,
    },
    { label: "Avg. Survival Probability", value: `${avgSurvival}%`, icon: HeartPulse, tone: "warning" as const },
  ];

  const recentActivity = notifications.slice(0, 5).map((n) => ({
    title: n.title,
    detail: n.body,
    time: n.time,
    tone: notificationTone[n.type ?? "system"] ?? "primary",
  }));

  const upcomingAppointments = appointments
    .filter((a) => a.status === "Confirmed" || a.status === "Scheduled")
    .slice(0, 4);

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Clinical Dashboard"
        description="Live overview of your breast-oncology cohort, digital twins and AI prediction performance."
        crumbs={[{ label: "Home", to: "/" }, { label: "Dashboard" }]}
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/reports">Export report</Link>
            </Button>
            <Button asChild>
              <Link to="/simulator">New simulation</Link>
            </Button>
          </>
        }
      />

      <section aria-label="Key metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {dashboardStats.map((s) => (
          <StatCard key={s.label} label={s.label} value={s.value} tone={s.tone} icon={s.icon} />
        ))}
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Patient & twin growth</CardTitle>
            <CardDescription>Registered patients vs. active digital twins</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={patientGrowth} margin={{ left: -18, right: 8 }}>
                <defs>
                  <linearGradient id="gPatients" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-chart-1)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="var(--color-chart-1)" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gTwins" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-chart-2)" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="var(--color-chart-2)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="month" tickLine={false} axisLine={false} {...axis} />
                <YAxis tickLine={false} axisLine={false} {...axis} />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="patients" stroke="var(--color-chart-1)" strokeWidth={2} fill="url(#gPatients)" />
                <Area type="monotone" dataKey="twins" stroke="var(--color-chart-2)" strokeWidth={2} fill="url(#gTwins)" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Risk distribution</CardTitle>
            <CardDescription>Cohort stratification by AI risk score</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={riskDistribution} dataKey="value" nameKey="name" innerRadius={58} outerRadius={92} paddingAngle={3}>
                  {riskDistribution.map((entry, i) => (
                    <Cell key={entry.key} fill={riskColors[i]} stroke="var(--color-card)" strokeWidth={2} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap justify-center gap-3">
              {riskDistribution.map((r, i) => (
                <span key={r.key} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="size-2 rounded-full" style={{ background: riskColors[i] }} aria-hidden="true" />
                  {r.name} · {r.value}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Cancer stage distribution</CardTitle>
            <CardDescription>Active cohort</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stageDistribution} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="stage" tickLine={false} axisLine={false} {...axis} />
                <YAxis tickLine={false} axisLine={false} {...axis} />
                <Tooltip cursor={{ fill: "var(--color-muted)" }} contentStyle={tooltipStyle} />
                <Bar dataKey="count" fill="var(--color-chart-1)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Treatment comparison</CardTitle>
            <CardDescription>Response vs. recurrence rate (%)</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={treatmentComparison} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="treatment" tickLine={false} axisLine={false} {...axis} interval={0} angle={-12} height={44} textAnchor="end" />
                <YAxis tickLine={false} axisLine={false} {...axis} />
                <Tooltip cursor={{ fill: "var(--color-muted)" }} contentStyle={tooltipStyle} />
                <Bar dataKey="response" fill="var(--color-chart-2)" radius={[6, 6, 0, 0]} />
                <Bar dataKey="recurrence" fill="var(--color-chart-4)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Prediction accuracy</CardTitle>
            <CardDescription>Ensemble accuracy over time (%)</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={accuracyTrend} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="month" tickLine={false} axisLine={false} {...axis} />
                <YAxis domain={[80, 92]} tickLine={false} axisLine={false} {...axis} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="accuracy" stroke="var(--color-chart-1)" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <CardDescription>Latest events across your cohort</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {recentActivity.length === 0 ? (
              <EmptyState icon={Bell} title="No recent activity" description="Events will appear here as they happen across your cohort." />
            ) : (
              recentActivity.map((a, i) => (
                <div key={a.title + i}>
                  <div className="flex items-center gap-3 py-2.5">
                    <StatusChip tone={a.tone} dot>
                      {a.tone === "risk" ? "Alert" : a.tone === "warning" ? "Watch" : a.tone === "success" ? "Done" : "Info"}
                    </StatusChip>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{a.title}</p>
                      <p className="truncate text-xs text-muted-foreground">{a.detail}</p>
                    </div>
                    <span className="shrink-0 text-xs text-muted-foreground">{a.time}</span>
                  </div>
                  {i < recentActivity.length - 1 && <Separator />}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <CalendarClock className="size-4 text-primary" aria-hidden="true" /> Upcoming follow-ups
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {upcomingAppointments.length === 0 ? (
                <p className="px-1 py-2 text-xs text-muted-foreground">No upcoming follow-ups scheduled.</p>
              ) : (
                upcomingAppointments.map((f) => (
                  <div key={f.id} className="flex items-center gap-3 rounded-lg border border-border p-2.5">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{f.title}</p>
                      <p className="text-xs text-muted-foreground">
                        {f.doctor} · {f.date} {f.time}
                      </p>
                    </div>
                    <ArrowUpRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Bell className="size-4 text-primary" aria-hidden="true" /> Notifications
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {notifications.slice(0, 3).map((n) => (
                <div key={n.id} className="rounded-lg bg-muted/60 p-2.5">
                  <p className="text-sm font-medium">{n.title}</p>
                  <p className="text-xs text-muted-foreground">{n.body}</p>
                </div>
              ))}
              <Button variant="ghost" className="w-full" asChild>
                <Link to="/notifications">View all</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
