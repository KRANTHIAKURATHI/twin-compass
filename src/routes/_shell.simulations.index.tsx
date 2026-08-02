import { createFileRoute, Link } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { FlaskConical } from "lucide-react";

import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { simulationRuns } from "@/lib/mock-lifecycle";

export const Route = createFileRoute("/_shell/simulations/")({
  head: () => ({
    meta: [
      { title: "Simulation Runs — OncoTwin" },
      { name: "description", content: "Browse every treatment simulation run, its promoted scenario and decision notes." },
      { property: "og:title", content: "Simulation Runs — OncoTwin" },
      { property: "og:description", content: "Browse every treatment simulation run, its promoted scenario and decision notes." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(SimulationsPage, { variant: "list" }),
});

function SimulationsPage() {
  return (
    <div className="mx-auto max-w-[1200px]">
      <PageHeader
        title="Simulation runs"
        description="Every scenario comparison executed against a patient digital twin."
        crumbs={[{ label: "Home", to: "/" }, { label: "Simulations" }]}
        actions={
          <Button asChild>
            <Link to="/simulator">
              <FlaskConical className="size-4" aria-hidden="true" /> New simulation
            </Link>
          </Button>
        }
      />

      {simulationRuns.length === 0 ? (
        <EmptyState icon={FlaskConical} title="No simulations yet" description="Run the treatment simulator to compare scenarios." />
      ) : (
        <Card>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run</TableHead>
                  <TableHead>Patient</TableHead>
                  <TableHead>Twin</TableHead>
                  <TableHead>Selected scenario</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Decision</TableHead>
                  <TableHead className="text-right">Detail</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {simulationRuns.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">{r.id}</TableCell>
                    <TableCell>{r.patient}</TableCell>
                    <TableCell>{r.twinVersion}</TableCell>
                    <TableCell>{r.selected}</TableCell>
                    <TableCell>{r.confidence}%</TableCell>
                    <TableCell>
                      <StatusChip
                        tone={r.decision === "Promoted to plan" ? "success" : r.decision === "Rejected" ? "risk" : "warning"}
                      >
                        {r.decision}
                      </StatusChip>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="outline" asChild>
                        <Link to="/simulations/$runId" params={{ runId: r.id }}>
                          View
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
