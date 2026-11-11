/**
 * One vocabulary for what a number on screen IS. Every prediction, estimate or projection shown to a user states
 * whether it is recorded, a heuristic estimate, a research-model output or a projected scenario, and says when it is
 * not available. A null from the API is rendered as NOT_AVAILABLE, never as 0, 0% or "Unknown".
 */
export const NOT_AVAILABLE = "Not available";
export const NOT_VALIDATED = "Not clinically validated";

export const PROVENANCE = {
  recorded: "Recorded value",
  /** A value stored on the patient record whose origin (entered, copied or estimated) is not tracked. */
  stored: "Stored on record — origin not tracked",
  /** The WDBC classifier + heuristic survival/recurrence formulas behind POST /predictions/run. */
  heuristic: "Heuristic estimate",
  os: "Research model — Overall Survival",
  rfs: "Research model — Recurrence-Free Survival",
  projected: "Projected scenario",
  experimental: "Research / experimental",
} as const;

/** Render a nullable value, or NOT_AVAILABLE. */
export const orNotAvailable = (value: unknown, suffix = ""): string =>
  value === null || value === undefined || value === "" ? NOT_AVAILABLE : `${value}${suffix}`;
