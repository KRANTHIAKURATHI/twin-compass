import { useEffect, useState } from "react";
import { PageErrorState, RouteErrorState, withPageStates } from "@/components/common/PageState";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Boxes, RefreshCw, Activity, Ruler, Syringe, Clock, GitCompare, RotateCcw, Archive } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { PageHeader } from "@/components/common/PageHeader";
import { RiskChip, StatusChip } from "@/components/common/StatusChip";
import { StateNotice } from "@/components/common/StateNotice";
import { Timeline } from "@/components/common/Timeline";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import {
  useArchiveTwin,
  usePatient,
  usePatientTimeline,
  useResyncTwin,
  useRestoreTwinVersion,
  useTumorSizeHistory,
  useTwinSnapshots,
  useTwinVersions,
  useTwins,
} from "@/hooks/api";

export const Route = createFileRoute("/_shell/digital-twins")({
  head: () => ({
    meta: [
      { title: "Digital Twins — OncoTwin" },
      { name: "description", content: "Interactive virtual patient models with live tumor, treatment and risk state." },
      { property: "og:title", content: "Digital Twins — OncoTwin" },
      { property: "og:description", content: "Interactive virtual patient models with live tumor, treatment and risk state." },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(DigitalTwinsPage, { variant: "detail" }),
});

const axis = { stroke: "var(--color-muted-foreground)", fontSize: 12 };
const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid var(--color-border)",
  background: "var(--color-card)",
  fontSize: 12,
};

/** `—` rather than `0` for anything the record simply does not carry. */
const show = (value: unknown, suffix = "") =>
  value === null || value === undefined || value === "" ? "—" : `${value}${suffix}`;

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : "—");

function DigitalTwinsPage() {
  const { data: twins = [], isLoading: twinsLoading, isError: twinsError, refetch: refetchTwins } = useTwins();
  const [selectedId, setSelectedId] = useState("");
  const [tab, setTab] = useState("timeline");
  const [selected, setSelected] = useState<string[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const [restore, setRestore] = useState<string | null>(null);
  const [archiveOpen, setArchiveOpen] = useState(false);

  useEffect(() => {
    if (!selectedId && twins[0]) setSelectedId(twins[0].patientId);
  }, [twins, selectedId]);

  const twinRow = twins.find((t) => t.patientId === selectedId);
  const { data: patient } = usePatient(selectedId);
  const { data: versions = [], isLoading: versionsLoading, isError: versionsError } = useTwinVersions(selectedId);
  const { data: snapshots = [], isError: snapshotsError } = useTwinSnapshots(selectedId);
  const { data: timeline = [] } = usePatientTimeline(selectedId);
  const { data: sizeHistory = [], isLoading: historyLoading } = useTumorSizeHistory(selectedId);

  const resync = useResyncTwin();
  const restoreVersion = useRestoreTwinVersion();
  const archive = useArchiveTwin();

  // Clear any comparison selection when switching patient — the version
  // labels are per-patient, so carrying them across would compare nothing.
  useEffect(() => setSelected([]), [selectedId]);

  const toggleSelect = (version: string) =>
    setSelected((prev) =>
      prev.includes(version) ? prev.filter((v) => v !== version) : [...prev.slice(-1), version],
    );

  const compared = versions.filter((v) => selected.includes(v.version));
  const syncing = resync.isPending;
  const archived = (twinRow?.status ?? "") === "Archived";

  if (twinsLoading) {
    return <Skeleton className="h-[600px] rounded-2xl" />;
  }

  if (twinsError) {
    return (
      <PageErrorState
        title="Couldn't load digital twins"
        description="We could not reach the server to load the twin list. Check your connection and try again."
        onRetry={() => refetchTwins()}
      />
    );
  }

  if (!twins.length) {
    return (
      <StateNotice
        state="prediction-unavailable"
        title="No digital twins yet"
        description="Twins are built from patient records. Add a patient, then re-sync to create its first version."
      />
    );
  }

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Digital Twins"
        description="Each twin mirrors a patient's tumor biology, treatment exposure and recorded trajectory."
        crumbs={[{ label: "Home", to: "/" }, { label: "Digital Twins" }]}
        actions={
          <>
            <Button variant="outline" onClick={() => setArchiveOpen(true)} disabled={archived || !selectedId}>
              <Archive className="size-4" aria-hidden="true" />
              {archived ? "Archived" : "Archive twin"}
            </Button>
            <Button onClick={() => resync.mutate(selectedId)} disabled={syncing || !selectedId}>
              <RefreshCw className={syncing ? "size-4 animate-spin" : "size-4"} aria-hidden="true" />
              {syncing ? "Re-syncing…" : "Re-sync twin"}
            </Button>
          </>
        }
      />

      {syncing && (
        <div className="mb-4">
          <StateNotice state="twin-recalculating" />
        </div>
      )}
      {archived && (
        <div className="mb-4">
          <StateNotice
            state="prediction-unavailable"
            title="Twin archived"
            description="This twin is read-only. Restore a version to resume simulations and predictions."
          />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
        <Card className="h-fit gap-0 p-2">
          <p className="px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Twins</p>
          <div className="space-y-1">
            {twins.map((t) => (
              <button
                key={t.patientId}
                onClick={() => setSelectedId(t.patientId)}
                aria-pressed={t.patientId === selectedId}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${
                  t.patientId === selectedId ? "bg-primary-soft text-primary" : "hover:bg-muted"
                }`}
              >
                <Boxes className="size-4 shrink-0" aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{t.patient}</span>
                  <span className="block text-xs text-muted-foreground">
                    {t.patientId} · {t.version ?? "No version"}
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
                <p className="text-center text-xs text-muted-foreground">
                  {twinRow?.version ? `Version ${twinRow.version}` : "No version yet"}
                </p>
                <StatusChip
                  tone={
                    twinRow?.status === "Active"
                      ? "success"
                      : twinRow?.status === "Not created"
                        ? "neutral"
                        : "warning"
                  }
                  dot
                  className="mt-3"
                >
                  {twinRow?.status ?? "Unknown"}
                </StatusChip>
              </div>

              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="text-xl font-semibold">{twinRow?.patient ?? "—"}</h2>
                  {patient?.risk && <RiskChip level={patient.risk} />}
                  <StatusChip tone="neutral">Stage {show(patient?.stage)}</StatusChip>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {show(patient?.age)} years · {show(patient?.hospital)}
                </p>

                <dl className="mt-5 grid grid-cols-2 gap-4 xl:grid-cols-4">
                  {[
                    { icon: Ruler, label: "Tumor size", value: show(twinRow?.tumorSizeMm, " mm") },
                    { icon: Syringe, label: "Treatment", value: show(patient?.currentTreatment) },
                    { icon: Activity, label: "Health status", value: show(patient?.status) },
                    { icon: Clock, label: "Twin updated", value: formatDate(twinRow?.createdAt) },
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
                    {/* "Recorded", not "predicted": this number is stored on the
                        twin version, not produced by a model at view time. */}
                    <span className="text-muted-foreground">Recorded 5-year survival</span>
                    <span className="font-semibold">
                      {twinRow?.survival != null ? `${Math.round(twinRow.survival * 100)}%` : "—"}
                    </span>
                  </div>
                  <Progress value={twinRow?.survival != null ? twinRow.survival * 100 : 0} className="mt-2 h-2" />
                </div>

                <div className="mt-5 flex flex-wrap gap-2">
                  <Button asChild>
                    <Link to="/simulator">Run treatment simulation</Link>
                  </Button>
                  {selectedId && (
                    <Button variant="outline" asChild>
                      <Link to="/patients/$patientId" params={{ patientId: selectedId }}>
                        Open patient profile
                      </Link>
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Measured tumor size</CardTitle>
                <CardDescription>
                  Tumor size recorded on each twin version — measurements, not a projection
                </CardDescription>
              </CardHeader>
              <CardContent className="h-64">
                {historyLoading || syncing ? (
                  <Skeleton className="size-full rounded-xl" />
                ) : sizeHistory.length === 0 ? (
                  <div className="flex h-full items-center justify-center text-center text-sm text-muted-foreground">
                    No measurements recorded yet. Re-sync the twin to record the current size.
                  </div>
                ) : sizeHistory.length === 1 ? (
                  // A single reading is a point, not a trend. Drawing a line
                  // through one measurement would imply a trajectory.
                  <div className="flex h-full flex-col items-center justify-center gap-1 text-center">
                    <p className="text-3xl font-semibold">{sizeHistory[0].tumorSizeMm} mm</p>
                    <p className="text-sm text-muted-foreground">
                      {sizeHistory[0].version} · {formatDate(sizeHistory[0].date)}
                    </p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      One measurement so far — a trend needs at least two.
                    </p>
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={sizeHistory} margin={{ left: -20 }}>
                      <defs>
                        <linearGradient id="gMeasured" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="var(--color-chart-2)" stopOpacity={0.3} />
                          <stop offset="100%" stopColor="var(--color-chart-2)" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                      <XAxis dataKey="version" tickLine={false} axisLine={false} {...axis} />
                      <YAxis tickLine={false} axisLine={false} unit=" mm" {...axis} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Area
                        type="monotone"
                        dataKey="tumorSizeMm"
                        name="Tumor size (mm)"
                        stroke="var(--color-chart-2)"
                        strokeWidth={2}
                        fill="url(#gMeasured)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Twin history</CardTitle>
                <CardDescription>Clinical events, versions and snapshots feeding the twin</CardDescription>
                <div className="pt-3">
                  <Tabs value={tab} onValueChange={setTab}>
                    <TabsList>
                      <TabsTrigger value="timeline">Timeline</TabsTrigger>
                      <TabsTrigger value="versions">Version history</TabsTrigger>
                      <TabsTrigger value="snapshots">Snapshots</TabsTrigger>
                    </TabsList>
                  </Tabs>
                </div>
              </CardHeader>
              <CardContent>
                {tab === "timeline" &&
                  (timeline.length ? (
                    <Timeline items={timeline} />
                  ) : (
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      No timeline events recorded for this patient yet.
                    </p>
                  ))}

                {tab === "versions" && (
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Button size="sm" variant="outline" onClick={() => setCompareOpen(true)}>
                        <GitCompare className="size-4" aria-hidden="true" /> Compare versions
                      </Button>
                      <span className="text-xs text-muted-foreground">{selected.length}/2 selected</span>
                    </div>
                    {versionsLoading ? (
                      <Skeleton className="h-40 rounded-xl" />
                    ) : versionsError ? (
                      <p className="py-8 text-center text-sm text-destructive">
                        Couldn't load version history. Try refreshing the page.
                      </p>
                    ) : versions.length === 0 ? (
                      <p className="py-8 text-center text-sm text-muted-foreground">
                        No versions yet. Re-sync the twin to cut its first version.
                      </p>
                    ) : (
                      <ul className="space-y-3">
                        {versions.map((v) => (
                          <li
                            key={v.version}
                            className={cn(
                              "rounded-xl border p-3",
                              selected.includes(v.version) ? "border-primary ring-1 ring-primary/30" : "border-border",
                            )}
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <StatusChip tone="neutral">{v.version}</StatusChip>
                              <StatusChip
                                tone={v.status === "Active" ? "success" : v.status === "Archived" ? "warning" : "neutral"}
                              >
                                {v.status}
                              </StatusChip>
                              <span className="ml-auto text-xs text-muted-foreground">{formatDate(v.createdAt)}</span>
                            </div>
                            <p className="mt-2 text-sm font-medium">{show(v.summary)}</p>
                            <p className="text-xs text-muted-foreground">
                              {show(v.author)} · {show(v.model)} · {show(v.tumorSizeMm, " mm")} ·{" "}
                              {v.survival != null ? `${Math.round(v.survival * 100)}% survival` : "no survival recorded"}
                            </p>
                            <div className="mt-3 flex flex-wrap items-center gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                aria-pressed={selected.includes(v.version)}
                                onClick={() => toggleSelect(v.version)}
                              >
                                {selected.includes(v.version) ? "Deselect" : "Select to compare"}
                              </Button>
                              {v.status !== "Active" && (
                                <Button size="sm" variant="ghost" onClick={() => setRestore(v.version)}>
                                  <RotateCcw className="size-4" aria-hidden="true" /> Restore
                                </Button>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                {tab === "snapshots" &&
                  (snapshotsError ? (
                    <p className="py-8 text-center text-sm text-destructive">
                      Couldn't load snapshots. Try refreshing the page.
                    </p>
                  ) : snapshots.length === 0 ? (
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      No snapshots recorded for this twin.
                    </p>
                  ) : (
                    <ul className="space-y-3">
                      {snapshots.map((s) => (
                        <li key={s.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-border p-3">
                          <StatusChip tone="primary">{s.version}</StatusChip>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium">{s.id}</p>
                            <p className="text-xs text-muted-foreground">
                              {show(s.trigger)} · {show(s.size)}
                            </p>
                          </div>
                          <span className="text-xs text-muted-foreground">{formatDate(s.takenAt)}</span>
                        </li>
                      ))}
                    </ul>
                  ))}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      <Dialog open={compareOpen} onOpenChange={setCompareOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Compare twin versions</DialogTitle>
            <DialogDescription>
              {compared.length === 2
                ? `${compared[1].version} vs ${compared[0].version}`
                : "Select two versions in the version history to compare them."}
            </DialogDescription>
          </DialogHeader>
          {compared.length === 2 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Field</th>
                    {compared.map((v) => (
                      <th key={v.version} className="py-2 pr-4 font-medium">
                        {v.version}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["Created", (v: (typeof compared)[number]) => formatDate(v.createdAt)],
                    ["Status", (v: (typeof compared)[number]) => v.status],
                    ["Model", (v: (typeof compared)[number]) => show(v.model)],
                    ["Tumor size", (v: (typeof compared)[number]) => show(v.tumorSizeMm, " mm")],
                    [
                      "5-year survival",
                      (v: (typeof compared)[number]) => (v.survival != null ? `${Math.round(v.survival * 100)}%` : "—"),
                    ],
                    ["Risk", (v: (typeof compared)[number]) => show(v.risk)],
                    ["Change", (v: (typeof compared)[number]) => show(v.summary)],
                  ].map(([label, get]) => (
                    <tr key={label as string} className="border-t border-border align-top">
                      <td className="py-2 pr-4 text-muted-foreground">{label as string}</td>
                      {compared.map((v) => (
                        <td key={v.version} className="py-2 pr-4">
                          {(get as (x: typeof v) => string)(v)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Currently selected: {selected.join(", ") || "none"}.</p>
          )}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={restore !== null}
        onOpenChange={(o) => !o && setRestore(null)}
        title={`Restore ${restore ?? ""}?`}
        description="Restoring copies this version forward as a new active version. The original stays in the history."
        confirmLabel="Restore version"
        onConfirm={() => {
          if (restore) restoreVersion.mutate({ patientId: selectedId, version: restore });
          setRestore(null);
        }}
      />

      <ConfirmDialog
        open={archiveOpen}
        onOpenChange={setArchiveOpen}
        title="Archive this digital twin?"
        description="The twin becomes read-only. Existing reports keep their references and you can restore any version later."
        confirmLabel="Archive twin"
        destructive
        onConfirm={() => {
          archive.mutate(selectedId);
          setArchiveOpen(false);
        }}
      />
    </div>
  );
}
