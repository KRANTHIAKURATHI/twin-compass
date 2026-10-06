// The backend labels a run with no regimen "Current treatment" and, having no
// kinetic parameters for it, returns no outcomes. That label is a placeholder,
// never a regimen, so it must not be sent back as one.
const isPlaceholder = (value: string | null | undefined): boolean => {
  const v = (value ?? "").trim().toLowerCase();
  return v === "" || v === "current treatment";
};

/** The value if it names a real regimen, else undefined. */
export const realRegimen = (value: string | null | undefined): string | undefined =>
  isPlaceholder(value) ? undefined : (value as string).trim();

/**
 * The regimen a run should evaluate, in order: the Scenario Builder entry, a
 * real regimen recorded on the displayed run, the patient's recorded treatment.
 * Undefined when none is usable — nothing is invented.
 */
export const resolveRunRegimen = (
  builderRegimen: string,
  displayedRequested: (string | null | undefined)[],
  patientTreatment: string | null | undefined,
): string | undefined =>
  realRegimen(builderRegimen) ??
  displayedRequested.map(realRegimen).find(Boolean) ??
  realRegimen(patientTreatment);
