import { createFileRoute, notFound } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { CheckCircle2 } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { InputsUsedCard, ModelStatusNotice } from "@/components/simulation/SimulationPanels";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  CONFIDENCE_EXPLANATION,
  CONFIDENCE_NOT_APPLICABLE,
  NOT_CALCULATED,
  hasOutcomes,
  runUnavailableReason,
  unavailableExplanation,
} from "@/lib/simulationDisplay";
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

/** "Not available" rather than `0` for anything the record simply does not carry. */
const show = (value: unknown, suffix = "") =>
  value === null || value === undefined || value === "" ? "Not available" : `${value}${suffix}`;

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : "—");

function SimulationDetail() {
  const { run } = Route.useLoaderData() as { run: SimulationRun };
  // The scenarios stored on the run itself, so reopening it shows what was
  // actually compared. This used to fall back to the full scenario catalogue
  // when none matched, which showed rows that were never part of the run.
  const rows = run.scenarios ?? [];
  const selectedName = run.selected;
  // The reason the backend recorded when the projection could not run, shown verbatim; absent on runs stored before
  // it was persisted, in which case the generic "not calculated" note is used and no cause is guessed at.
  const storedReason = runUnavailableReason(rows);
  const noProjection = rows.length > 0 && !rows.some(hasOutcomes);
  const provenance = rows.find((s) => s.provenance)?.provenance ?? null;
  const cell = (s: (typeof rows)[number], value: unknown, suffix = "") =>
    hasOutcomes(s) ? show(value, suffix) : NOT_CALCULATED;

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader
        title={`Simulation ${run.id.slice(0, 8)}`}
        description={[
          "Projected scenario · Research / experimental",
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
          ["Projected response", noProjection ? NOT_CALCULATED : show(run.response, "%"), null],
          ["Projected survival (scenario)", noProjection ? NOT_CALCULATED : show(run.survival, "%"), null],
          [
            "Confidence",
            run.confidence === null || run.confidence === undefined ? CONFIDENCE_NOT_APPLICABLE : `${run.confidence}%`,
            run.confidence === null || run.confidence === undefined ? CONFIDENCE_EXPLANATION : null,
          ],
        ].map(([label, value, note]) => (
          <Card key={label}>
            <CardContent className="py-6">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
              <p className={`mt-1 text-2xl font-semibold ${noProjection || note ? "text-muted-foreground" : ""}`}>{value}</p>
              {note && <p className="mt-1 text-xs text-muted-foreground">{note}</p>}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-4">
        <ModelStatusNotice parametersVerified={rows.every((s) => s.provenance?.parametersVerified === true)} />
      </div>
      {noProjection && (
        <p className="mb-4 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm">
          {storedReason ?? unavailableExplanation({ provenance })} No values have been invented.
        </p>
      )}
      <InputsUsedCard provenance={provenance} twinVersion={run.twinVersion} model={run.model} />

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
                  <TableHead>Projected response</TableHead>
                  <TableHead>Projected tumor change</TableHead>
                  <TableHead>Projected survival (scenario)</TableHead>
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
                    <TableCell>{cell(s, s.predictedResponse, "%")}</TableCell>
                    <TableCell>{cell(s, s.tumorChange, "%")}</TableCell>
                    <TableCell>{cell(s, s.survival5y, "%")}</TableCell>
                    <TableCell>{cell(s, s.sideEffectRisk, "%")}</TableCell>
                    <TableCell title={s.confidence === null ? CONFIDENCE_EXPLANATION : undefined}>{s.confidence === null ? CONFIDENCE_NOT_APPLICABLE : `${s.confidence}%`}</TableCell>
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
