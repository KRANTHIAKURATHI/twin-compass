// Display rules for the treatment simulation. Pure functions, no React, no aliased imports, so they run under
// `node --experimental-strip-types --test` (see simulationDisplay.guard.test.mjs).
//
// Nothing in this file computes or defaults a clinical value. It only decides how the API's answer is worded:
// a null stays null, and a reason is the backend's own `provenance.unavailableReason` when there is one.
import { realRegimen } from "./simulationRegimen.ts";
import type { Scenario, ScenarioProvenance } from "../types/models.ts";

export const SELECT_REGIMEN_MESSAGE = "Select a treatment regimen before running the simulation.";
export const NOT_CALCULATED = "Not calculated";
export const NOT_AVAILABLE = "Not available";
/** Shown only when the backend sent no reason of its own. */
export const GENERIC_UNAVAILABLE_NOTE =
  "Not calculated — this scenario has not been evaluated with the required inputs.";
export const MODEL_STATUS_TITLE = "Kinetic projection using unvalidated parameters";
export const MODEL_STATUS_DETAIL =
  "A deterministic projection from the twin's recorded state. It is not a trained clinical prediction model and has no diagnostic capability.";
export const UNVERIFIED_NOTE = "Research / experimental — parameters have not been clinically verified.";
export const CONFIDENCE_NOT_APPLICABLE = "Not applicable";
export const CONFIDENCE_EXPLANATION = "This is a deterministic kinetic projection, not a trained predictive model.";

/**
 * Regimen choices for the Scenario Builder. Each `value` is what the API receives, so it must be text the backend's
 * `classify_regimen` maps to the named family (backend/app/services/response_model.py). The labels are the backend's
 * own family names; nothing here names a regimen the backend does not classify. `simulationDisplay.guard.test.mjs`
 * checks each value against the backend's keyword table, so a drift fails the test rather than a clinician's run.
 */
export const REGIMEN_OPTIONS: readonly { label: string; value: string }[] = [
  { label: "Anthracycline + taxane", value: "Anthracycline + taxane" },
  { label: "HER2-targeted therapy (trastuzumab-based)", value: "Trastuzumab-based HER2-targeted therapy" },
  { label: "Endocrine therapy", value: "Endocrine therapy" },
  { label: "CDK4/6 inhibitor + endocrine", value: "CDK4/6 inhibitor + endocrine" },
  { label: "Platinum-based", value: "Platinum-based" },
];

export type RegimenSource = "builder" | "displayed-run" | "patient-record";

/** Which real regimen a run would use, and where it came from. Null when none is usable — nothing is invented. */
export const describeRunRegimen = (
  builderRegimen: string,
  displayedRequested: (string | null | undefined)[],
  patientTreatment: string | null | undefined,
): { regimen: string; source: RegimenSource } | null => {
  const fromBuilder = realRegimen(builderRegimen);
  if (fromBuilder) return { regimen: fromBuilder, source: "builder" };
  const fromRun = displayedRequested.map(realRegimen).find(Boolean);
  if (fromRun) return { regimen: fromRun, source: "displayed-run" };
  const fromPatient = realRegimen(patientTreatment);
  return fromPatient ? { regimen: fromPatient, source: "patient-record" } : null;
};

const OUTCOMES = ["predictedResponse", "tumorChange", "survival5y", "sideEffectRisk", "recoveryWeeks"] as const;

type Outcomes = Pick<Scenario, (typeof OUTCOMES)[number]>;

/** True when at least one outcome measure is a real number. */
export const hasOutcomes = (s: Outcomes): boolean => OUTCOMES.some((k) => s[k] !== null && s[k] !== undefined);

export type ScenarioStatus = "draft" | "available" | "investigational" | "unavailable";

/**
 * `investigational` is the one case where the backend returns no numbers AND no reason: an investigational protocol
 * has no established effect size, and its own `basis` says so. Everything else without numbers is `unavailable`.
 */
export const scenarioStatus = (
  s: Outcomes & { evaluated?: boolean; provenance?: ScenarioProvenance | null },
): ScenarioStatus => {
  if (s.evaluated === false) return "draft";
  if (hasOutcomes(s)) return "available";
  if (s.provenance && !s.provenance.unavailableReason) return "investigational";
  return "unavailable";
};

/**
 * Why a scenario has no numbers. The backend's `unavailableReason` is returned exactly as sent; for the
 * investigational case the backend's `basis` is used; the generic note appears only when the backend said nothing.
 */
export const unavailableExplanation = (s: {
  provenance?: ScenarioProvenance | null;
  basis?: string | null;
}): string =>
  s.provenance?.unavailableReason ||
  (s.provenance && s.basis ? s.basis : null) ||
  GENERIC_UNAVAILABLE_NOTE;

/** The first reason the backend recorded across a run's scenarios (they all share one provenance). */
export const runUnavailableReason = (scenarios: { provenance?: ScenarioProvenance | null }[]): string | null =>
  scenarios.map((s) => s.provenance?.unavailableReason).find((r): r is string => Boolean(r)) ?? null;

export type InputRow = { label: string; value: string | null };

const text = (v: unknown, suffix = ""): string | null =>
  v === null || v === undefined || v === "" ? null : `${v}${suffix}`;

/**
 * "Inputs used" rows. `provenance.inputs` is the exact twin state the projection ran on; `null` here means the value
 * was genuinely absent (rendered "Not available"), never a default. Runs stored before inputs were recorded simply
 * have no `inputs`, and every row is then null.
 */
export const inputRows = (
  provenance: ScenarioProvenance | null | undefined,
  extra: { twinVersion?: string | null; model?: string | null } = {},
): InputRow[] => {
  const i = provenance?.inputs ?? null;
  return [
    { label: "Tumor size", value: text(i?.tumorSizeMm, " mm") },
    { label: "Ki-67", value: text(i?.ki67, "%") },
    { label: "ER", value: text(i?.ER) },
    { label: "PR", value: text(i?.PR) },
    { label: "HER2", value: text(i?.HER2) },
    { label: "Baseline survival", value: text(i?.baselineSurvival, "%") },
    { label: "Baseline risk", value: text(i?.baselineRisk) },
    { label: "Requested regimen", value: text(provenance?.requestedRegimen) },
    { label: "Twin version", value: text(extra.twinVersion) },
    { label: "Parameter table", value: text(provenance?.parametersVersion) },
    { label: "Model", value: text(extra.model ?? provenance?.model) },
  ];
};

/** Confidence is null for a kinetic projection: say "Not applicable", never "0%". */
export const confidenceLabel = (confidence: number | null | undefined): string =>
  confidence === null || confidence === undefined ? CONFIDENCE_NOT_APPLICABLE : `${confidence}%`;

type RunLike = { id: string; date: string; scenarios?: Scenario[] | null };

/**
 * The previous run whose stored scenarios carry real numbers, for showing next to a latest run that has none.
 * `current` is the run being shown; only runs other than it, and strictly older than it, qualify. The returned run
 * is the stored record untouched: its numbers are never merged into the current one.
 */
export const previousRunWithResults = <T extends RunLike>(runs: readonly T[], currentId: string | null): T | null => {
  const current = runs.find((r) => r.id === currentId);
  const currentTime = current ? Date.parse(current.date) : Number.POSITIVE_INFINITY;
  const older = runs
    .filter((r) => r.id !== currentId && (Number.isNaN(currentTime) || Date.parse(r.date) < currentTime))
    .filter((r) => (r.scenarios ?? []).some(hasOutcomes))
    .sort((a, b) => Date.parse(b.date) - Date.parse(a.date));
  return older[0] ?? null;
};
