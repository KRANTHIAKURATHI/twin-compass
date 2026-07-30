import { createFileRoute } from "@tanstack/react-router";
import { FileQuestion, Inbox, Lock, ServerCrash, TriangleAlert } from "lucide-react";
import { Link } from "@tanstack/react-router";

import { EmptyState } from "@/components/common/EmptyState";
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
          { icon: FileQuestion, title: "404 — Page not found", desc: "The requested route does not exist.", to: "/404-preview" as const },
          { icon: ServerCrash, title: "500 — Server error", desc: "An unexpected failure occurred.", to: "/error" as const },
          { icon: Lock, title: "403 — Permission denied", desc: "Role lacks the required capability.", to: "/forbidden" as const },
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
                <Link to={s.to}>Preview page</Link>
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
      </div>
    </div>
  );
}
