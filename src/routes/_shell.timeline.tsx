import { useEffect, useState } from "react";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { createFileRoute } from "@tanstack/react-router";

import { CalendarClock, Users } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { Timeline } from "@/components/common/Timeline";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePatient, usePatients, usePatientTimeline } from "@/hooks/api";

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

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleDateString() : "—");

function TimelinePage() {
  const { data: patients = [], isLoading: patientsLoading } = usePatients();
  const [patientId, setPatientId] = useState("");
  const [kind, setKind] = useState<string>("all");

  useEffect(() => {
    if (!patientId && patients[0]) setPatientId(patients[0].id);
  }, [patients, patientId]);

  const { data: patient } = usePatient(patientId);
  const { data: events = [], isLoading } = usePatientTimeline(patientId);

  const items = [...events]
    .filter((t) => kind === "all" || t.kind === kind)
    .sort((a, b) => (a.date < b.date ? 1 : -1));

  if (!patientsLoading && patients.length === 0) {
    return (
      <div className="mx-auto max-w-[1000px]">
        <PageHeader
          title="Clinical Timeline"
          description="Everything that happened to a patient, newest first."
          crumbs={[{ label: "Home", to: "/" }, { label: "Timeline" }]}
        />
        <EmptyState
          icon={Users}
          title="No patients yet"
          description="Add a patient record to start building a clinical timeline."
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1000px]">
      <PageHeader
        title="Clinical Timeline"
        description="Everything that happened to a patient, newest first."
        crumbs={[{ label: "Home", to: "/" }, { label: "Timeline" }]}
        actions={
          <Select value={patientId} onValueChange={setPatientId}>
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
          <CardTitle>{patient?.name ?? patientId}</CardTitle>
          <CardDescription>
            Diagnosed {formatDate(patient?.diagnosedOn)} · Stage {patient?.stage ?? "—"} · {items.length} events
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
          {isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-16 rounded-xl" />
              <Skeleton className="h-16 rounded-xl" />
              <Skeleton className="h-16 rounded-xl" />
            </div>
          ) : items.length === 0 ? (
            <EmptyState
              icon={CalendarClock}
              title={events.length === 0 ? "No events recorded" : "No events in this view"}
              description={
                events.length === 0
                  ? "Nothing has been recorded for this patient yet. Events appear here as twins resync, predictions run and treatment is logged."
                  : "This patient has no recorded events of that type yet. Choose another filter."
              }
            />
          ) : (
            <Timeline items={items} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
