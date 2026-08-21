import { useState, type FormEvent } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { PageErrorState, PageSkeleton, RouteErrorState } from "@/components/common/PageState";
import { CalendarDays, Clock, MapPin, Plus } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAppointments, useCreateAppointment } from "@/hooks/api";
import type { Appointment } from "@/types/models";

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
  component: MyAppointments,
});

function Row({ a }: { a: Appointment }) {
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

function RequestAppointmentForm({ onDone }: { onDone: () => void }) {
  const createAppointment = useCreateAppointment();

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const payload: Omit<Appointment, "id" | "status"> = {
      title: String(form.get("title") ?? ""),
      doctor: String(form.get("doctor") ?? ""),
      date: String(form.get("date") ?? ""),
      time: String(form.get("time") ?? ""),
      location: String(form.get("location") ?? ""),
    };
    createAppointment.mutate(payload, { onSuccess: onDone });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="req-title">Reason for visit</Label>
        <Input id="req-title" name="title" required placeholder="e.g. Follow-up consultation" />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="req-doctor">Preferred doctor</Label>
        <Input id="req-doctor" name="doctor" required placeholder="e.g. Dr. Patel" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="req-date">Preferred date</Label>
          <Input id="req-date" name="date" type="date" required />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="req-time">Preferred time</Label>
          <Input id="req-time" name="time" type="time" required />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="req-location">Location</Label>
        <Input id="req-location" name="location" required placeholder="e.g. Main campus, room 204" />
      </div>
      <DialogFooter>
        <Button type="submit" disabled={createAppointment.isPending}>
          {createAppointment.isPending ? "Sending…" : "Send request"}
        </Button>
      </DialogFooter>
    </form>
  );
}

function MyAppointments() {
  const appointmentsQuery = useAppointments();
  const [open, setOpen] = useState(false);

  if (appointmentsQuery.isLoading) return <PageSkeleton variant="list" />;
  if (appointmentsQuery.isError) {
    return (
      <div className="mx-auto max-w-[900px] pt-4">
        <PageErrorState onRetry={() => appointmentsQuery.refetch()} />
      </div>
    );
  }

  const appointments = appointmentsQuery.data ?? [];
  const upcoming = appointments.filter((a) => a.status !== "Completed");
  const past = appointments.filter((a) => a.status === "Completed");

  return (
    <div className="mx-auto max-w-[900px]">
      <PageHeader
        title="My Appointments"
        description="Your scheduled visits and treatment sessions."
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="size-4" aria-hidden="true" /> Request appointment
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Request an appointment</DialogTitle>
              </DialogHeader>
              <RequestAppointmentForm onDone={() => setOpen(false)} />
            </DialogContent>
          </Dialog>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Upcoming</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {upcoming.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No upcoming appointments scheduled.</p>
          ) : (
            upcoming.map((a) => <Row key={a.id} a={a} />)
          )}
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-base">Past</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {past.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No past appointments yet.</p>
          ) : (
            past.map((a) => <Row key={a.id} a={a} />)
          )}
        </CardContent>
      </Card>
    </div>
  );
}
