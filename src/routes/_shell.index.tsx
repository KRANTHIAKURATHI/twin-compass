import { createFileRoute, Link } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
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
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { StatusChip, type ChipTone } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardAnalytics, useNotifications } from "@/hooks/api";
import type { ActivityEntry, DashboardStat } from "@/types/models";

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

const icons = {
  patients: Users,
  twins: Boxes,
  highRisk: AlertTriangle,
  simulations: FlaskConical,
  predictions: CheckCircle2,
  survival: HeartPulse,
} as const;

const tones: Record<string, "primary" | "success" | "warning" | "risk"> = {
  patients: "primary",
  twins: "primary",
  highRisk: "risk",
  simulations: "primary",
  predictions: "success",
  survival: "success",
};

const riskColors = ["var(--color-success)", "var(--color-warning)", "var(--color-risk)"];

const axis = { stroke: "var(--color-muted-foreground)", fontSize: 12 };
const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid var(--color-border)",
  background: "var(--color-card)",
  color: "var(--color-card-foreground)",
  fontSize: 12,
};

/**
 * Stat values carry no delta.
 *
 * There is no stored month-over-month baseline anywhere in this database, so a
 * "+12% vs last month" line would have to be invented. The card simply omits
 * it, and a stat with nothing recorded shows "—" rather than 0.
 */
const statValue = (s: DashboardStat) =>
  s.value === null ? "—" : s.format === "percent" ? `${s.value}%` : String(s.value);

const activityTone = (role: string): ChipTone =>
  role === "admin" ? "warning" : role === "doctor" ? "primary" : "neutral";

const relativeTime = (iso: string) => {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.round(mins / 60)}h ago`;
  return new Date(iso).toLocaleDateString();
};

function ChartEmpty({ children }: { children: string }) {
  return (
    <div className="flex h-full items-center justify-center px-6 text-center text-sm text-muted-foreground">
      {children}
    </div>
  );
}

function DashboardPage() {
  const { data, isLoading } = useDashboardAnalytics();
  const { data: notifications = [] } = useNotifications("doctor");

  const stats = data?.stats ?? [];
  const growth = data?.patientGrowth ?? [];
  const risk = data?.riskDistribution ?? [];
  const stages = data?.stageDistribution ?? [];
  const treatments = data?.treatmentComparison ?? [];
  const accuracy = data?.accuracy;
  const activity: ActivityEntry[] = data?.recentActivity ?? [];
  const followUps = data?.followUps ?? [];
  const riskTotal = risk.reduce((sum, r) => sum + r.value, 0);

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
        {isLoading
          ? Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-[118px] rounded-xl" />)
          : stats.map((s) => (
              <StatCard
                key={s.key}
                label={s.label}
                value={statValue(s)}
                tone={tones[s.key] ?? "primary"}
                icon={icons[s.key as keyof typeof icons] ?? Users}
              />
            ))}
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Patient & twin growth</CardTitle>
            <CardDescription>
              Cumulative registered patients vs. patients with a digital twin, by month of first record
            </CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {growth.length === 0 ? (
              <ChartEmpty>No patient records yet, so there is no growth to plot.</ChartEmpty>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={growth} margin={{ left: -18, right: 8 }}>
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
                  <YAxis tickLine={false} axisLine={false} allowDecimals={false} {...axis} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Area
                    type="monotone"
                    dataKey="patients"
                    name="Patients"
                    stroke="var(--color-chart-1)"
                    strokeWidth={2}
                    fill="url(#gPatients)"
                  />
                  <Area
                    type="monotone"
                    dataKey="twins"
                    name="With a twin"
                    stroke="var(--color-chart-2)"
                    strokeWidth={2}
                    fill="url(#gTwins)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Risk distribution</CardTitle>
            <CardDescription>Cohort stratification by the risk recorded on each patient</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {riskTotal === 0 ? (
              <ChartEmpty>No patient carries a recorded risk level yet.</ChartEmpty>
            ) : (
              <>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={risk} dataKey="value" nameKey="name" innerRadius={58} outerRadius={92} paddingAngle={3}>
                      {risk.map((entry, i) => (
                        <Cell key={entry.key} fill={riskColors[i]} stroke="var(--color-card)" strokeWidth={2} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex flex-wrap justify-center gap-3">
                  {risk.map((r, i) => (
                    <span key={r.key} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <span className="size-2 rounded-full" style={{ background: riskColors[i] }} aria-hidden="true" />
                      {r.name} · {r.value}
                    </span>
                  ))}
                </div>
              </>
            )}
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
            {stages.length === 0 ? (
              <ChartEmpty>No patient carries a recorded stage yet.</ChartEmpty>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stages} margin={{ left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                  <XAxis dataKey="stage" tickLine={false} axisLine={false} {...axis} />
                  <YAxis tickLine={false} axisLine={false} allowDecimals={false} {...axis} />
                  <Tooltip cursor={{ fill: "var(--color-muted)" }} contentStyle={tooltipStyle} />
                  <Bar dataKey="count" name="Patients" fill="var(--color-chart-1)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Treatment comparison</CardTitle>
            <CardDescription>
              Average recorded survival vs. its complement, per regimen on file
            </CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            {treatments.length === 0 ? (
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
                    height={44}
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
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Validation performance</CardTitle>
            <CardDescription>
              {accuracy?.model
                ? `${accuracy.model.name} v${accuracy.model.version} · cross-validation folds`
                : "No registered model"}
            </CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            {!accuracy?.series.length ? (
              <ChartEmpty>No validation results are recorded for any model.</ChartEmpty>
            ) : (
              // Bars, not a line: the series is cross-validation folds, and a
              // line between folds would read as improvement over time.
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
          </CardContent>
        </Card>
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <CardDescription>Latest audited events across your cohort</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {activity.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">No activity recorded yet.</p>
            ) : (
              activity.map((a, i) => (
                <div key={a.title + a.time + i}>
                  <div className="flex items-center gap-3 py-2.5">
                    <StatusChip tone={activityTone(a.actorRole)} dot>
                      {a.actorRole || "system"}
                    </StatusChip>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{a.title}</p>
                      <p className="truncate text-xs text-muted-foreground">{a.detail}</p>
                    </div>
                    <span className="shrink-0 text-xs text-muted-foreground">{relativeTime(a.time)}</span>
                  </div>
                  {i < activity.length - 1 && <Separator />}
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
              {followUps.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">No appointments scheduled.</p>
              ) : (
                followUps.map((f) => (
                  <Link
                    key={f.id + f.when}
                    to="/patients/$patientId"
                    params={{ patientId: f.id }}
                    className="flex items-center gap-3 rounded-lg border border-border p-2.5 transition-colors hover:bg-muted"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{f.patient}</p>
                      <p className="text-xs text-muted-foreground">
                        {f.type} · {f.when}
                      </p>
                    </div>
                    <ArrowUpRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  </Link>
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
              {notifications.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">Nothing new.</p>
              ) : (
                notifications.slice(0, 3).map((n) => (
                  <div key={n.id} className="rounded-lg bg-muted/60 p-2.5">
                    <p className="text-sm font-medium">{n.title}</p>
                    <p className="text-xs text-muted-foreground">{n.body}</p>
                  </div>
                ))
              )}
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
