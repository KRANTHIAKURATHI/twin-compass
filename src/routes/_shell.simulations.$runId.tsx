import { createFileRoute, notFound } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { CheckCircle2 } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { scenarios } from "@/lib/mock-data";
import { simulationRuns, type SimulationRun } from "@/lib/mock-lifecycle";

export const Route = createFileRoute("/_shell/simulations/$runId")({
  loader: ({ params }) => {
    const run = simulationRuns.find((r) => r.id === params.runId);
    if (!run) throw notFound();
    return { run };
  },
  head: ({ loaderData }) => {
    if (!loaderData) {
      return { meta: [{ title: "Simulation unavailable — OncoTwin" }, { name: "robots", content: "noindex" }] };
    }
    const title = `Simulation ${loaderData.run.id} — OncoTwin`;
    const description = `Scenario comparison, results and decision notes for simulation ${loaderData.run.id}.`;
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
  errorComponent: RouteErrorState,
  component: withPageStates(SimulationDetail, { variant: "detail" }),
});

function SimulationDetail() {
  const { run } = Route.useLoaderData() as { run: SimulationRun };
  const compared = scenarios.filter((s) => run.compared.includes(s.name));
  const rows = compared.length > 0 ? compared : scenarios;
  const selectedName = compared.length > 0 ? run.selected : (rows.find((s) => s.recommended)?.name ?? run.selected);


  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader
        title={`Simulation ${run.id}`}
        description={`${run.patient} · twin ${run.twinVersion} · model ${run.model} · run on ${run.date}`}
        crumbs={[{ label: "Home", to: "/" }, { label: "Simulations", to: "/simulations" }, { label: run.id }]}
        actions={
          <StatusChip tone={run.decision === "Promoted to plan" ? "success" : run.decision === "Rejected" ? "risk" : "warning"}>
            {run.decision}
          </StatusChip>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {[
          ["Predicted response", `${run.response}%`],
          ["5-year survival", `${run.survival}%`],
          ["Model confidence", `${run.confidence}%`],
        ].map(([label, value]) => (
          <Card key={label}>
            <CardContent className="py-6">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
              <p className="mt-1 text-2xl font-semibold">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-base">Scenario comparison</CardTitle>
          <CardDescription>Outcomes across every scenario included in this run</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Scenario</TableHead>
                <TableHead>Response</TableHead>
                <TableHead>Tumor change</TableHead>
                <TableHead>5-y survival</TableHead>
                <TableHead>Side effects</TableHead>
                <TableHead>Confidence</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((s) => (
                <TableRow key={s.id} className={s.name === selectedName ? "bg-primary-soft/40" : undefined}>
                  <TableCell className="font-medium">
                    <span className="inline-flex items-center gap-2">
                      {s.name}
                      {s.name === selectedName && (

                        <span className="inline-flex items-center gap-1 text-xs text-primary">
                          <CheckCircle2 className="size-3.5" aria-hidden="true" /> Selected
                        </span>
                      )}
                    </span>
                  </TableCell>
                  <TableCell>{s.predictedResponse}%</TableCell>
                  <TableCell>{s.tumorChange}%</TableCell>
                  <TableCell>{s.survival5y}%</TableCell>
                  <TableCell>{s.sideEffectRisk}%</TableCell>
                  <TableCell>{s.confidence}%</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-base">Decision notes</CardTitle>
          <CardDescription>Recorded by {run.decidedBy}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{run.notes}</p>
        </CardContent>
      </Card>
    </div>
  );
}
