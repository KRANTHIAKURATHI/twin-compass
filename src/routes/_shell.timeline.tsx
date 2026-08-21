import { useEffect, useState } from "react";
import { PageErrorState, RouteErrorState, withPageStates } from "@/components/common/PageState";
import { createFileRoute } from "@tanstack/react-router";

import { CalendarClock } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { Timeline } from "@/components/common/Timeline";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePatients, usePatientTimeline } from "@/hooks/api";

export const Route = createFileRoute("/_shell/timeline")({
  head: () => ({
    meta: [
      { title: "Patient Timeline — OncoTwin" },
      { name: "description", content: "Complete chronological view of diagnoses, treatments, scans and clinical notes." },
      { property: "og:title", content: "Patient Timeline — OncoTwin" },
      { property: "og:description", content: "Complete chronological view of diagnoses, treatments, scans and clinical notes." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(TimelinePage, { variant: "list" }),
});

const kinds = ["all", "diagnosis", "treatment", "scan", "note"] as const;

// Note: the backend only exposes a per-patient timeline
// (`/patients/{id}/timeline`) — there is no aggregate/global timeline
// endpoint, so this page keeps the existing single-patient picker pattern.
function TimelinePage() {
  const patientsQuery = usePatients();
  const patients = patientsQuery.data ?? [];
  const [patientId, setPatientId] = useState<string | null>(null);
  const [kind, setKind] = useState<string>("all");

  useEffect(() => {
    if (!patientId && patients.length > 0) setPatientId(patients[0].id);
  }, [patientId, patients]);

  const patient = patients.find((p) => p.id === patientId) ?? patients[0];
  const timelineQuery = usePatientTimeline(patient?.id ?? "");

  if (patientsQuery.isLoading) {
    return (
      <div className="mx-auto max-w-[1000px] space-y-4 pt-4">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (patientsQuery.isError) {
    return (
      <div className="mx-auto max-w-[1000px] pt-4">
        <PageErrorState title="Could not load patients" />
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="mx-auto max-w-[1000px] pt-4">
        <EmptyState icon={CalendarClock} title="No patients yet" description="Add a patient to start building a clinical timeline." />
      </div>
    );
  }

  const events = timelineQuery.data ?? [];
  const items = [...events]
    .filter((t) => kind === "all" || t.kind === kind)
    .sort((a, b) => (a.date < b.date ? 1 : -1));

  return (
    <div className="mx-auto max-w-[1000px]">
      <PageHeader
        title="Clinical Timeline"
        description="Everything that happened to a patient, newest first."
        crumbs={[{ label: "Home", to: "/" }, { label: "Timeline" }]}
        actions={
          <Select value={patient.id} onValueChange={setPatientId}>
            <SelectTrigger className="w-[240px]" aria-label="Select patient">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {patients.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name} · {p.id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>{patient.name}</CardTitle>
          <CardDescription>
            Diagnosed {patient.diagnosedOn} · Stage {patient.stage} · {items.length} events
          </CardDescription>
          <div className="pt-3">
            <Tabs value={kind} onValueChange={setKind}>
              <TabsList>
                {kinds.map((k) => (
                  <TabsTrigger key={k} value={k} className="capitalize">
                    {k}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
        </CardHeader>
        <CardContent>
          {timelineQuery.isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : timelineQuery.isError ? (
            <PageErrorState title="Could not load timeline" />
          ) : items.length === 0 ? (
            <EmptyState
              icon={CalendarClock}
              title="No events in this view"
              description="This patient has no recorded events of that type yet. Choose another filter."
            />
          ) : (
            <Timeline items={items} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
