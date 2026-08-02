import { useState } from "react";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { createFileRoute } from "@tanstack/react-router";

import { CalendarClock } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { Timeline } from "@/components/common/Timeline";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { patients } from "@/lib/mock-data";

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

function TimelinePage() {
  const [patientId, setPatientId] = useState(patients[0].id);
  const [kind, setKind] = useState<string>("all");
  const patient = patients.find((p) => p.id === patientId)!;
  const items = [...patient.timeline]
    .filter((t) => kind === "all" || t.kind === kind)
    .sort((a, b) => (a.date < b.date ? 1 : -1));

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
          {items.length === 0 ? (
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
