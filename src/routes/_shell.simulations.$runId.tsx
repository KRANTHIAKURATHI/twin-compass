import { createFileRoute, notFound } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { CheckCircle2 } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { simulationService } from "@/services";
import type { SimulationRun } from "@/types/models";

export const Route = createFileRoute("/_shell/simulations/$runId")({
  loader: async ({ params }) => {
    const run = await simulationService.get(params.runId);
    if (!run) throw notFound();
    return { run };
  },
  head: ({ loaderData }) => {
    if (!loaderData) {
      return { meta: [{ title: "Simulation unavailable — OncoTwin" }, { name: "robots", content: "noindex" }] };
    }
    const short = loaderData.run.id.slice(0, 8);
    const title = `Simulation ${short} — OncoTwin`;
    const description = `Scenario comparison, results and decision notes for simulation ${short}.`;
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

/** `—` rather than `0` for anything the record simply does not carry. */
const show = (value: unknown, suffix = "") =>
  value === null || value === undefined || value === "" ? "—" : `${value}${suffix}`;

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : "—");

function SimulationDetail() {
  const { run } = Route.useLoaderData() as { run: SimulationRun };
  // The scenarios stored on the run itself, so reopening it shows what was
  // actually compared. This used to fall back to the full scenario catalogue
  // when none matched, which showed rows that were never part of the run.
  const rows = run.scenarios ?? [];
  const selectedName = run.selected;
  // A run whose regimen had no parameters (or whose twin lacked the inputs)
  // stores every outcome as null. The reason itself is not persisted, so say
  // only what the record shows rather than guessing at one cause.
  // The reason the backend recorded when the projection could not run, shown
  // verbatim; absent on runs stored before it was persisted.
  const storedReason = rows
    .map((s) => (s as { provenance?: { unavailableReason?: string | null } }).provenance?.unavailableReason)
    .find((r): r is string => Boolean(r));
  const noProjection =
    rows.length > 0 &&
    rows.every(
      (s) =>
        s.predictedResponse == null &&
        s.tumorChange == null &&
        s.survival5y == null &&
        s.sideEffectRisk == null &&
        s.recoveryWeeks == null,
    );

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader
        title={`Simulation ${run.id.slice(0, 8)}`}
        description={[
          run.patient,
          run.twinVersion ? `twin ${run.twinVersion}` : null,
          run.model ? `model ${run.model}` : null,
          `run on ${formatDate(run.date)}`,
        ]
          .filter(Boolean)
          .join(" · ")}
        crumbs={[
          { label: "Home", to: "/" },
          { label: "Simulations", to: "/simulations" },
          { label: run.id.slice(0, 8) },
        ]}
        actions={
          <StatusChip tone={run.decision === "Promoted to plan" ? "success" : run.decision === "Rejected" ? "risk" : "warning"}>
            {show(run.decision)}
          </StatusChip>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {[
          ["Projected response", show(run.response, "%")],
          ["Survival estimate", show(run.survival, "%")],
          ["Confidence", show(run.confidence, "%")],
        ].map(([label, value]) => (
          <Card key={label}>
            <CardContent className="py-6">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
              <p className="mt-1 text-2xl font-semibold">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {noProjection ? (
        <p className="mt-4 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm">
          {storedReason
            ? `The projection could not be calculated for this run: ${storedReason}`
            : "The projection could not be calculated for this run: no parameters exist for the regimen on file, or the twin lacked the receptor status or tumor size it needs."}{" "}
          No values have been invented.
        </p>
      ) : (
        <p className="mt-4 text-xs text-muted-foreground">
          Kinetic projection (log-kill with exponential regrowth).{" "}
          <span className="font-semibold text-warning">Parameters unverified — pending clinical review.</span>
        </p>
      )}

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-base">Scenario comparison</CardTitle>
          <CardDescription>The scenarios as recorded when this run executed</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {rows.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              This run recorded no scenarios.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scenario</TableHead>
                  <TableHead>Response</TableHead>
                  <TableHead>Tumor change</TableHead>
                  <TableHead>Survival estimate</TableHead>
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
                    <TableCell>{show(s.predictedResponse, "%")}</TableCell>
                    <TableCell>{show(s.tumorChange, "%")}</TableCell>
                    <TableCell>{show(s.survival5y, "%")}</TableCell>
                    <TableCell>{show(s.sideEffectRisk, "%")}</TableCell>
                    <TableCell>{show(s.confidence, "%")}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-base">Decision notes</CardTitle>
          <CardDescription>{run.decidedBy ? `Recorded by ${run.decidedBy}` : "No decision recorded"}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{run.notes || "No notes were recorded for this run."}</p>
        </CardContent>
      </Card>
    </div>
  );
}
