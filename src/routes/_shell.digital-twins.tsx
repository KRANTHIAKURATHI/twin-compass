import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Boxes, RefreshCw, Activity, Ruler, Syringe, Clock } from "lucide-react";
import { toast } from "sonner";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/common/PageHeader";
import { RiskChip, StatusChip } from "@/components/common/StatusChip";
import { Timeline } from "@/components/common/Timeline";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { patients, progressionForecast } from "@/lib/mock-data";
import { twinService } from "@/services";

export const Route = createFileRoute("/_shell/digital-twins")({
  head: () => ({
    meta: [
      { title: "Digital Twins — OncoTwin" },
      { name: "description", content: "Interactive virtual patient models with live tumor, treatment and risk state." },
      { property: "og:title", content: "Digital Twins — OncoTwin" },
      { property: "og:description", content: "Interactive virtual patient models with live tumor, treatment and risk state." },
    ],
  }),
  component: DigitalTwinsPage,
});

const twins = patients.slice(0, 8);
const axis = { stroke: "var(--color-muted-foreground)", fontSize: 12 };
const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid var(--color-border)",
  background: "var(--color-card)",
  fontSize: 12,
};

function DigitalTwinsPage() {
  const [selectedId, setSelectedId] = useState(twins[0].id);
  const [syncing, setSyncing] = useState(false);
  const twin = twins.find((t) => t.id === selectedId)!;

  const resync = async () => {
    setSyncing(true);
    await twinService.resync(twin.id);
    setSyncing(false);
    toast.success("Digital twin re-synced", { description: "TODO: wire POST /api/digital-twins/{id}/resync" });
  };

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Digital Twins"
        description="Each twin mirrors a patient's tumor biology, treatment exposure and predicted trajectory."
        crumbs={[{ label: "Home", to: "/" }, { label: "Digital Twins" }]}
        actions={
          <Button onClick={resync} disabled={syncing}>
            <RefreshCw className={syncing ? "size-4 animate-spin" : "size-4"} aria-hidden="true" />
            {syncing ? "Re-syncing…" : "Re-sync twin"}
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
        <Card className="h-fit gap-0 p-2">
          <p className="px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Active twins</p>
          <div className="space-y-1">
            {twins.map((t) => (
              <button
                key={t.id}
                onClick={() => setSelectedId(t.id)}
                aria-pressed={t.id === selectedId}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${
                  t.id === selectedId ? "bg-primary-soft text-primary" : "hover:bg-muted"
                }`}
              >
                <Boxes className="size-4 shrink-0" aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{t.name}</span>
                  <span className="block text-xs text-muted-foreground">
                    {t.id} · Stage {t.stage}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="overflow-hidden">
            <div className="grid gap-6 p-6 md:grid-cols-[220px_1fr]">
              <div className="relative flex flex-col items-center justify-center rounded-2xl bg-primary-soft/60 p-6">
                <div className="relative flex size-32 items-center justify-center rounded-full bg-card shadow-[var(--shadow-card)]">
                  <span className="absolute inset-0 animate-ping rounded-full bg-primary/10" aria-hidden="true" />
                  <Activity className="size-12 text-primary" aria-hidden="true" />
                </div>
                <p className="mt-4 text-center text-sm font-semibold">Virtual patient</p>
                <p className="text-center text-xs text-muted-foreground">Twin ID TW-{twin.id.slice(3)}</p>
                <StatusChip
                  tone={twin.twinStatus === "Synced" ? "success" : twin.twinStatus === "Stale" ? "warning" : "primary"}
                  dot
                  className="mt-3"
                >
                  {twin.twinStatus}
                </StatusChip>
              </div>

              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="text-xl font-semibold">{twin.name}</h2>
                  <RiskChip level={twin.risk} />
                  <StatusChip tone="neutral">Stage {twin.stage}</StatusChip>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {twin.age} years · {twin.hospital}
                </p>

                <dl className="mt-5 grid grid-cols-2 gap-4 xl:grid-cols-4">
                  {[
                    { icon: Ruler, label: "Tumor size", value: `${twin.tumorSizeMm} mm` },
                    { icon: Syringe, label: "Treatment", value: twin.currentTreatment },
                    { icon: Activity, label: "Health status", value: twin.status },
                    { icon: Clock, label: "Twin updated", value: twin.lastUpdated },
                  ].map((m) => (
                    <div key={m.label} className="rounded-xl border border-border p-3">
                      <m.icon className="size-4 text-primary" aria-hidden="true" />
                      <dt className="mt-2 text-xs text-muted-foreground">{m.label}</dt>
                      <dd className="text-sm font-medium leading-snug break-words">{m.value}</dd>
                    </div>
                  ))}
                </dl>

                <div className="mt-5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Predicted 5-year survival</span>
                    <span className="font-semibold">{twin.survivalProbability}%</span>
                  </div>
                  <Progress value={twin.survivalProbability} className="mt-2 h-2" />
                </div>

                <div className="mt-5 flex flex-wrap gap-2">
                  <Button asChild>
                    <Link to="/simulator">Run treatment simulation</Link>
                  </Button>
                  <Button variant="outline" asChild>
                    <Link to="/patients/$patientId" params={{ patientId: twin.id }}>
                      Open patient profile
                    </Link>
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Simulated tumor trajectory</CardTitle>
                <CardDescription>Treated vs. untreated tumor volume (mm)</CardDescription>
              </CardHeader>
              <CardContent className="h-64">
                {syncing ? (
                  <Skeleton className="size-full rounded-xl" />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={progressionForecast} margin={{ left: -20 }}>
                      <defs>
                        <linearGradient id="gUntreated" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="var(--color-chart-4)" stopOpacity={0.3} />
                          <stop offset="100%" stopColor="var(--color-chart-4)" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="gTreated" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="var(--color-chart-2)" stopOpacity={0.3} />
                          <stop offset="100%" stopColor="var(--color-chart-2)" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                      <XAxis dataKey="month" tickLine={false} axisLine={false} {...axis} />
                      <YAxis tickLine={false} axisLine={false} {...axis} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Area type="monotone" dataKey="untreated" stroke="var(--color-chart-4)" strokeWidth={2} fill="url(#gUntreated)" />
                      <Area type="monotone" dataKey="treated" stroke="var(--color-chart-2)" strokeWidth={2} fill="url(#gTreated)" />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Disease timeline</CardTitle>
                <CardDescription>Events feeding the twin</CardDescription>
              </CardHeader>
              <CardContent>
                <Timeline items={twin.timeline} />
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
