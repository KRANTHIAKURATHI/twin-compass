import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Pill, ShieldAlert, Syringe } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { treatmentPlan } from "@/lib/mock-extra";

export const Route = createFileRoute("/_patient/portal/treatment")({
  head: () => ({
    meta: [
      { title: "My Treatment — OncoTwin Patient Portal" },
      { name: "description", content: "Your current regimen, medication schedule, cycles and side-effect guidance." },
      { property: "og:title", content: "My Treatment — OncoTwin Patient Portal" },
      { property: "og:description", content: "Your current regimen, medication schedule, cycles and side-effect guidance." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(MyTreatment, { variant: "list" }),
});

function MyTreatment() {
  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader title="My Treatment" description="Everything about your current care plan, explained in plain language." />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Syringe className="size-4 text-primary" aria-hidden="true" /> {treatmentPlan.regimen}
            </CardTitle>
            <CardDescription>Started {treatmentPlan.startedOn} · next dose {treatmentPlan.nextDose}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Cycle progress</span>
                <span className="font-semibold">
                  {treatmentPlan.cycle} of {treatmentPlan.totalCycles}
                </span>
              </div>
              <Progress value={(treatmentPlan.cycle / treatmentPlan.totalCycles) * 100} className="mt-2 h-2" />
            </div>
            <div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Plan adherence</span>
                <span className="font-semibold">{treatmentPlan.adherence}%</span>
              </div>
              <Progress value={treatmentPlan.adherence} className="mt-2 h-2" />
            </div>

            <div>
              <p className="mb-2 flex items-center gap-2 text-sm font-medium">
                <Pill className="size-4 text-primary" aria-hidden="true" /> Medications
              </p>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Medication</TableHead>
                    <TableHead>Dose</TableHead>
                    <TableHead>Schedule</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {treatmentPlan.medications.map((m) => (
                    <TableRow key={m.name}>
                      <TableCell className="font-medium">{m.name}</TableCell>
                      <TableCell>{m.dose}</TableCell>
                      <TableCell className="text-muted-foreground">{m.schedule}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldAlert className="size-4 text-warning-foreground" aria-hidden="true" /> Side effects to watch
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {treatmentPlan.sideEffects.map((s) => (
              <div key={s.name} className="rounded-xl border border-border p-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">{s.name}</p>
                  <StatusChip tone={s.grade === "Grade 2" ? "warning" : "neutral"}>{s.grade}</StatusChip>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{s.advice}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
