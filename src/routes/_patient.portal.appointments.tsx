import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { CalendarDays, Clock, MapPin, Plus } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { appointments } from "@/lib/mock-extra";

export const Route = createFileRoute("/_patient/portal/appointments")({
  head: () => ({
    meta: [
      { title: "My Appointments — OncoTwin Patient Portal" },
      { name: "description", content: "Upcoming and past visits, infusions and imaging appointments with your care team." },
      { property: "og:title", content: "My Appointments — OncoTwin Patient Portal" },
      { property: "og:description", content: "Upcoming and past visits, infusions and imaging appointments with your care team." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(MyAppointments, { variant: "list" }),
});

function Row({ a }: { a: (typeof appointments)[number] }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border p-4">
      <span className="flex size-11 shrink-0 flex-col items-center justify-center rounded-xl bg-primary-soft text-primary">
        <span className="text-[10px] uppercase">{a.date.slice(5, 7)}/{a.date.slice(8)}</span>
        <CalendarDays className="size-4" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{a.title}</p>
        <p className="text-xs text-muted-foreground">{a.doctor}</p>
        <p className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Clock className="size-3" aria-hidden="true" /> {a.time}
          </span>
          <span className="flex items-center gap-1">
            <MapPin className="size-3" aria-hidden="true" /> {a.location}
          </span>
        </p>
      </div>
      <StatusChip tone={a.status === "Confirmed" ? "success" : a.status === "Completed" ? "neutral" : "primary"}>{a.status}</StatusChip>
    </div>
  );
}

function MyAppointments() {
  const upcoming = appointments.filter((a) => a.status !== "Completed");
  const past = appointments.filter((a) => a.status === "Completed");

  return (
    <div className="mx-auto max-w-[900px]">
      <PageHeader
        title="My Appointments"
        description="Your scheduled visits and treatment sessions."
        actions={
          <Button onClick={() => toast.success("Request sent", { description: "TODO: wire POST /api/appointments" })}>
            <Plus className="size-4" aria-hidden="true" /> Request appointment
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Upcoming</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {upcoming.map((a) => (
            <Row key={a.id} a={a} />
          ))}
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-base">Past</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {past.map((a) => (
            <Row key={a.id} a={a} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
