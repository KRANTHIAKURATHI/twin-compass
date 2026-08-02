import { createFileRoute } from "@tanstack/react-router";
import { FileQuestion, Inbox, Lock, ServerCrash, TriangleAlert } from "lucide-react";
import { Link } from "@tanstack/react-router";

import { EmptyState } from "@/components/common/EmptyState";
import { StateNotice, type SystemState } from "@/components/common/StateNotice";

import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/_shell/states")({
  head: () => ({
    meta: [
      { title: "UI States — OncoTwin" },
      { name: "description", content: "Reference gallery of empty, loading, error and permission-denied states used across OncoTwin." },
      { property: "og:title", content: "UI States — OncoTwin" },
      { property: "og:description", content: "Reference gallery of empty, loading, error and permission-denied states used across OncoTwin." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: StatesPage,
});

const systemStates: SystemState[] = [
  "low-confidence",
  "model-updating",
  "twin-recalculating",
  "simulation-running",
  "waiting-verification",
  "prediction-unavailable",
];


function StatesPage() {
  return (
    <div className="mx-auto max-w-[1200px]">
      <PageHeader
        title="UI states"
        description="Canonical empty, loading, error and permission states used across the platform."
        crumbs={[{ label: "Home", to: "/" }, { label: "UI States" }]}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Empty state</CardTitle>
            <CardDescription>No records match the current filters</CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyState
              icon={Inbox}
              title="No patients yet"
              description="Add your first patient to generate a digital twin and start simulating treatments."
              action={
                <Button asChild>
                  <Link to="/patients/new">Add patient</Link>
                </Button>
              }
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Loading state</CardTitle>
            <CardDescription>Skeletons preserve layout while data resolves</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-8 w-1/3 rounded-lg" />
            <Skeleton className="h-32 w-full rounded-xl" />
            <div className="grid grid-cols-3 gap-3">
              <Skeleton className="h-16 rounded-xl" />
              <Skeleton className="h-16 rounded-xl" />
              <Skeleton className="h-16 rounded-xl" />
            </div>
          </CardContent>
        </Card>

        {[
          { icon: FileQuestion, title: "404 — Page not found", desc: "The requested route does not exist.", href: "/this-page-does-not-exist" },
          { icon: ServerCrash, title: "500 — Server error", desc: "An unexpected failure occurred.", href: "/error" },
          { icon: Lock, title: "403 — Permission denied", desc: "Role lacks the required capability.", href: "/forbidden" },
        ].map((s) => (
          <Card key={s.title}>
            <CardHeader>
              <CardTitle className="text-base">{s.title}</CardTitle>
              <CardDescription>{s.desc}</CardDescription>
            </CardHeader>
            <CardContent className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl bg-muted text-muted-foreground">
                <s.icon className="size-5" aria-hidden="true" />
              </span>
              <Button variant="outline" asChild>
                <a href={s.href}>Preview page</a>
              </Button>
            </CardContent>
          </Card>
        ))}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Inline warning</CardTitle>
            <CardDescription>Non-blocking data quality notice</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-start gap-3 rounded-xl border border-warning/40 bg-warning/10 p-4">
              <TriangleAlert className="mt-0.5 size-5 text-warning-foreground" aria-hidden="true" />
              <div>
                <p className="text-sm font-medium">Twin data is 14 days old</p>
                <p className="text-sm text-muted-foreground">Upload the latest imaging report to refresh predictions.</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Clinical system states</CardTitle>
            <CardDescription>Model, twin and simulation lifecycle notices shown inline across modules</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {systemStates.map((s) => (
              <StateNotice key={s} state={s} />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Table loading skeleton</CardTitle>
            <CardDescription>Row placeholders keep column widths stable</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-9 w-9 shrink-0 rounded-xl" />
                <Skeleton className="h-4 flex-1 rounded" />
                <Skeleton className="h-4 w-16 rounded" />
                <Skeleton className="h-4 w-20 rounded" />
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Chart loading skeleton</CardTitle>
            <CardDescription>Used while prediction and confidence charts resolve</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-5 w-40 rounded" />
            <Skeleton className="h-48 w-full rounded-xl" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Inline error state</CardTitle>
            <CardDescription>A module failed to load but the page is still usable</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-start gap-3 rounded-xl border border-risk/40 bg-risk-soft/60 p-4">
              <ServerCrash className="mt-0.5 size-5 shrink-0 text-risk" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">Couldn't load predictions</p>
                <p className="text-sm text-muted-foreground">The prediction service did not respond. Try again in a moment.</p>
              </div>
              <Button size="sm" variant="outline">
                Retry
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Empty — no simulations</CardTitle>
            <CardDescription>Module-specific empty state with a primary action</CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyState
              icon={Inbox}
              title="No simulations for this twin"
              description="Run the treatment simulator to compare regimens side by side."
              action={
                <Button asChild>
                  <Link to="/simulator">Open simulator</Link>
                </Button>
              }
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

