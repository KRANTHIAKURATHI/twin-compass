import { FlaskConical, Info } from "lucide-react";

import { StatusChip } from "@/components/common/StatusChip";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  CONFIDENCE_EXPLANATION,
  CONFIDENCE_NOT_APPLICABLE,
  MODEL_STATUS_DETAIL,
  MODEL_STATUS_TITLE,
  NOT_AVAILABLE,
  UNVERIFIED_NOTE,
  inputRows,
  type InputRow,
} from "@/lib/simulationDisplay";
import type { ScenarioProvenance } from "@/types/models";

/** What kind of result this is, stated once per page. Always shown: it is true of every run. */
export function ModelStatusNotice({ parametersVerified }: { parametersVerified: boolean }) {
  return (
    <div className="mb-4 flex items-start gap-3 rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm">
      <FlaskConical className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
      <div className="space-y-0.5">
        <p className="font-semibold">{MODEL_STATUS_TITLE}</p>
        <p className="text-muted-foreground">{MODEL_STATUS_DETAIL}</p>
        {parametersVerified === false && <p className="font-medium text-warning">{UNVERIFIED_NOTE}</p>}
      </div>
    </div>
  );
}

/**
 * Confidence is null for a kinetic projection. "Not applicable" with the reason, never "0%". A number appears only
 * if the API ever sends one.
 */
export function ConfidenceBadge({ confidence, className }: { confidence: number | null; className?: string }) {
  if (confidence !== null) {
    return <StatusChip tone="primary" className={className}>{`${confidence}% model confidence`}</StatusChip>;
  }
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button type="button" className="inline-flex items-center gap-1 rounded-full" aria-label={`Confidence: ${CONFIDENCE_NOT_APPLICABLE}. ${CONFIDENCE_EXPLANATION}`}>
            <StatusChip tone="neutral" className={className}>
              Confidence: {CONFIDENCE_NOT_APPLICABLE}
              <Info className="size-3" aria-hidden="true" />
            </StatusChip>
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">{CONFIDENCE_EXPLANATION}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

/** Compact "Inputs used" card. A row reads Not available only when the value is absent from the record. */
export function InputsUsedCard({
  provenance,
  twinVersion,
  model,
  title = "Inputs used",
  description = "The twin state this projection ran on",
}: {
  provenance: ScenarioProvenance | null | undefined;
  twinVersion?: string | null;
  model?: string | null;
  title?: string;
  description?: string;
}) {
  const rows: InputRow[] = inputRows(provenance, { twinVersion, model });
  return (
    <Card className="mb-4">
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3 lg:grid-cols-4">
          {rows.map((r) => (
            <div key={r.label} className="min-w-0">
              <dt className="text-xs text-muted-foreground">{r.label}</dt>
              <dd className={r.value === null ? "text-muted-foreground" : "break-words font-medium"}>
                {r.value ?? NOT_AVAILABLE}
              </dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
