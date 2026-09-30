import { createFileRoute, Link } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Copy, FlaskConical } from "lucide-react";

import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { useDuplicateScenario, useSimulationRuns } from "@/hooks/api";

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

/** `—` rather than `0` for anything the record simply does not carry. */
const show = (value: unknown, suffix = "") =>
  value === null || value === undefined || value === "" ? "—" : `${value}${suffix}`;

function SimulationsPage() {
  const { data: runs = [], isLoading } = useSimulationRuns();
  const duplicateScenario = useDuplicateScenario();
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

      {isLoading ? (
        <Card>
          <CardContent className="space-y-2 py-6">
            <Skeleton className="h-10 rounded-lg" />
            <Skeleton className="h-10 rounded-lg" />
            <Skeleton className="h-10 rounded-lg" />
          </CardContent>
        </Card>
      ) : runs.length === 0 ? (
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
                {runs.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs font-medium">{r.id.slice(0, 8)}</TableCell>
                    <TableCell>{show(r.patient)}</TableCell>
                    <TableCell>{show(r.twinVersion)}</TableCell>
                    <TableCell>{show(r.selected)}</TableCell>
                    <TableCell>{show(r.confidence, "%")}</TableCell>
                    <TableCell>
                      <StatusChip
                        tone={r.decision === "Promoted to plan" ? "success" : r.decision === "Rejected" ? "risk" : "warning"}
                      >
                        {r.decision}
                      </StatusChip>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Duplicate simulation ${r.id.slice(0, 8)}`}
                          disabled={duplicateScenario.isPending}
                          onClick={() => duplicateScenario.mutate(r.id)}
                        >
                          <Copy className="size-4" aria-hidden="true" />
                        </Button>
                        <Button size="sm" variant="outline" asChild>
                          <Link to="/simulations/$runId" params={{ runId: r.id }}>
                            View
                          </Link>
                        </Button>
                      </div>
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
