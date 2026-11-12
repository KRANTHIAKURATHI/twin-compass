// Run with: node --experimental-strip-types --test src/lib/simulationDisplay.guard.test.mjs
// Guards the simulation UI rules: a null stays null (never a default or an old run's number), the backend's own
// unavailableReason is shown verbatim, placeholder regimens are never sent, and confidence is "Not applicable", not 0%.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  CONFIDENCE_EXPLANATION,
  GENERIC_UNAVAILABLE_NOTE,
  MODEL_STATUS_TITLE,
  REGIMEN_OPTIONS,
  SELECT_REGIMEN_MESSAGE,
  RECOVERY_LABEL,
  RECOVERY_NOTE,
  UNVERIFIED_NOTE,
  confidenceLabel,
  describeRunRegimen,
  supportedRegimen,
  hasOutcomes,
  inputRows,
  previousRunWithResults,
  runUnavailableReason,
  scenarioRisk,
  scenarioStatus,
  unavailableExplanation,
} from "./simulationDisplay.ts";
import { realRegimen, resolveRunRegimen } from "./simulationRegimen.ts";

const NUMBERS = { predictedResponse: 61.5, tumorChange: -42.1, survival5y: 88.2, sideEffectRisk: 33, recoveryWeeks: 14 };
const NONE = { predictedResponse: null, tumorChange: null, survival5y: null, sideEffectRisk: null, recoveryWeeks: null };
const prov = (over = {}) => ({
  kind: "kinetic-projection",
  subtype: null,
  regimenFamily: null,
  source: null,
  parametersVerified: false,
  model: "Log-kill projection with exponential regrowth (unvalidated parameters)",
  unavailableReason: null,
  ...over,
});
const scenario = (id, outcomes, provenance, extra = {}) => ({
  id,
  name: id,
  regimen: "r",
  confidence: null,
  risk: null,
  recommended: false,
  ...outcomes,
  provenance,
  ...extra,
});

// --- placeholder regimens -----------------------------------------------------------------------------------

test("placeholder regimens are not real regimens", () => {
  for (const v of ["Current treatment", "current treatment ", "Not yet started", "NOT YET STARTED", "", "   ", null, undefined]) {
    assert.equal(realRegimen(v), undefined, String(v));
  }
  assert.equal(realRegimen("Endocrine therapy"), "Endocrine therapy");
});

test("with only placeholders or unsupported text there is no regimen to run, and none is inherited", () => {
  assert.equal(SELECT_REGIMEN_MESSAGE, "Select a treatment regimen before running the simulation.");
  for (const v of ["", "Current treatment", "Not yet started", "Letrozole"]) {
    assert.equal(describeRunRegimen(v), null, v);
    assert.equal(supportedRegimen(v), undefined, v);
  }
});

test("only a supported selector value is runnable, and the source is the builder", () => {
  for (const o of REGIMEN_OPTIONS) {
    assert.deepEqual(describeRunRegimen(o.value), { regimen: o.value, source: "builder" });
    assert.equal(supportedRegimen(o.value), o.value);
  }
});

// --- the selector only offers what the backend classifies ------------------------------------------------------

test("every Scenario Builder choice classifies to its own family in the backend keyword table", () => {
  const py = readFileSync(new URL("../../backend/app/services/response_model.py", import.meta.url), "utf8");
  const constants = Object.fromEntries([...py.matchAll(/^([A-Z0-9_]+) = "([^"]+)"$/gm)].map((m) => [m[1], m[2]]));
  const block = py.slice(py.indexOf("_REGIMEN_KEYWORDS"), py.indexOf("\n]\n", py.indexOf("_REGIMEN_KEYWORDS")));
  const table = [...block.matchAll(/\((\w+),\s*\(((?:\s*"[^"]*",?)+)\s*\)\)/g)].map((m) => [
    constants[m[1]],
    [...m[2].matchAll(/"([^"]*)"/g)].map((k) => k[1]),
  ]);
  assert.equal(table.length, 5, "parsed the backend keyword table");
  const classify = (text) => {
    const lower = text.toLowerCase();
    return table.find(([, words]) => words.some((w) => lower.includes(w)))?.[0] ?? null;
  };
  assert.equal(REGIMEN_OPTIONS.length, table.length);
  for (const o of REGIMEN_OPTIONS) {
    const family = classify(o.value);
    assert.ok(family, `backend would not classify "${o.value}"`);
    assert.ok(o.label.startsWith(family), `"${o.label}" is labelled as ${family}`);
  }
  assert.deepEqual(new Set(REGIMEN_OPTIONS.map((o) => classify(o.value))).size, table.length);
});

// --- unavailable / available / investigational -----------------------------------------------------------------

test("a scenario with numbers is available; the same scenario without them is not", () => {
  assert.equal(hasOutcomes(NUMBERS), true);
  assert.equal(hasOutcomes(NONE), false);
  assert.equal(scenarioStatus({ ...NUMBERS, provenance: prov() }), "available");
  // one real number is enough to call it available; the missing ones stay "Not available" individually
  assert.equal(scenarioStatus({ ...NONE, predictedResponse: 0, provenance: prov() }), "available");
});

test("no numbers plus a backend reason is unavailable, and the reason is shown exactly as sent", () => {
  const reason = 'No parameters for the regimen on file ("Not yet started · lower toxicity").';
  const s = scenario("a", NONE, prov({ unavailableReason: reason }), { basis: reason });
  assert.equal(scenarioStatus(s), "unavailable");
  assert.equal(unavailableExplanation(s), reason);
  assert.equal(runUnavailableReason([scenario("x", NONE, prov()), s]), reason);
});

test("no numbers, no reason, with provenance is the investigational case, explained by the backend's basis", () => {
  const basis = "Investigational protocol — no established effect size.";
  const s = scenario("t", NONE, prov(), { basis });
  assert.equal(scenarioStatus(s), "investigational");
  assert.equal(unavailableExplanation(s), basis);
});

test("the generic note appears only when the backend sent nothing", () => {
  assert.equal(GENERIC_UNAVAILABLE_NOTE, "Not calculated — this scenario has not been evaluated with the required inputs.");
  assert.equal(unavailableExplanation({ provenance: null, basis: null }), GENERIC_UNAVAILABLE_NOTE);
  assert.equal(scenarioStatus(scenario("old", NONE, null)), "unavailable");
  // a backend reason always beats the generic text
  assert.notEqual(unavailableExplanation({ provenance: prov({ unavailableReason: "X" }) }), GENERIC_UNAVAILABLE_NOTE);
});

test("a queued draft is neither available nor unavailable", () => {
  assert.equal(scenarioStatus({ ...NONE, evaluated: false, provenance: null }), "draft");
});

// --- inputs used --------------------------------------------------------------------------------------------------

test("inputs used come from provenance; only genuinely absent values are null", () => {
  const rows = Object.fromEntries(
    inputRows(
      prov({
        requestedRegimen: "Endocrine therapy",
        parametersVersion: "kinetic-regimen-parameters-v1",
        inputs: { tumorSizeMm: 22, ki67: 18, ER: "Positive", PR: "Positive", HER2: "Negative", baselineSurvival: 0, baselineRisk: "low" },
      }),
      { twinVersion: "v3", model: null },
    ).map((r) => [r.label, r.value]),
  );
  assert.equal(rows["Tumor size"], "22 mm");
  assert.equal(rows["Ki-67"], "18%");
  assert.equal(rows["HER2"], "Negative");
  assert.equal(rows["Baseline survival"], "0%", "a recorded 0 is a value, not an absence");
  const p976 = inputRows(prov({ inputs: { baselineSurvival: 0.9762 } }), {});
  assert.equal(Object.fromEntries(p976.map((r) => [r.label, r.value]))["Baseline survival"], "97.62%", "0-1 probability shown as a percentage");
  assert.equal(rows["Baseline risk"], "low");
  assert.equal(rows["Requested regimen"], "Endocrine therapy");
  assert.equal(rows["Twin version"], "v3");
  assert.equal(rows["Parameter table"], "kinetic-regimen-parameters-v1");
});

test("missing inputs are null (rendered Not available), never defaulted", () => {
  const rows = inputRows(prov({ inputs: { tumorSizeMm: null, ki67: null, ER: null, PR: "", HER2: undefined } }));
  for (const label of ["Tumor size", "Ki-67", "ER", "PR", "HER2", "Baseline survival", "Baseline risk", "Requested regimen", "Twin version"]) {
    assert.equal(rows.find((r) => r.label === label).value, null, label);
  }
  assert.ok(inputRows(null).every((r) => r.value === null || r.label === "Model"));
});

// --- confidence and model status ----------------------------------------------------------------------------------

test("a null confidence is Not applicable, never 0%", () => {
  assert.equal(confidenceLabel(null), "Not applicable");
  assert.equal(confidenceLabel(undefined), "Not applicable");
  assert.ok(!/0\s*%/.test(confidenceLabel(null)));
  assert.equal(confidenceLabel(87), "87%");
  assert.equal(CONFIDENCE_EXPLANATION, "This is a deterministic kinetic projection, not a trained predictive model.");
});

test("the model status wording is the required one", () => {
  assert.equal(MODEL_STATUS_TITLE, "Kinetic projection using unvalidated parameters");
  assert.equal(UNVERIFIED_NOTE, "Research / experimental — parameters have not been clinically verified.");
});

// --- historical results stay separate ---------------------------------------------------------------------------

test("the latest run's nulls are never filled from an older run; the older run is returned untouched", () => {
  const latest = { id: "r3", date: "2026-11-10T10:00:00Z", scenarios: [scenario("a", NONE, prov({ unavailableReason: "no params" }))] };
  const older = { id: "r2", date: "2026-11-05T10:00:00Z", scenarios: [scenario("b", NUMBERS, prov())] };
  const oldest = { id: "r1", date: "2026-10-01T10:00:00Z", scenarios: [scenario("c", { ...NUMBERS, predictedResponse: 10 }, prov())] };
  const before = JSON.stringify(latest);
  const prev = previousRunWithResults([latest, older, oldest], "r3");
  assert.equal(prev.id, "r2", "newest older run that has numbers, with its own date");
  assert.equal(prev.date, "2026-11-05T10:00:00Z");
  assert.equal(prev.scenarios[0].predictedResponse, 61.5);
  assert.equal(JSON.stringify(latest), before, "latest run is unchanged");
  assert.equal(latest.scenarios[0].predictedResponse, null);
});

test("no previous results when no older run has numbers, and newer runs never count as previous", () => {
  const latest = { id: "r2", date: "2026-11-10T10:00:00Z", scenarios: [scenario("a", NONE, prov())] };
  const olderNone = { id: "r1", date: "2026-11-01T10:00:00Z", scenarios: [scenario("b", NONE, prov())] };
  assert.equal(previousRunWithResults([latest, olderNone], "r2"), null);
  const newer = { id: "r9", date: "2026-11-11T10:00:00Z", scenarios: [scenario("c", NUMBERS, prov())] };
  assert.equal(previousRunWithResults([newer, latest, olderNone], "r2"), null);
  assert.equal(previousRunWithResults([], null), null);
});

// --- the screens use these rules (string guards: the route files are .tsx and are not loaded here) ----------------

test("the simulator and run pages route their wording through the shared rules", () => {
  const sim = readFileSync(new URL("../routes/_shell.simulator.tsx", import.meta.url), "utf8");
  const detail = readFileSync(new URL("../routes/_shell.simulations.$runId.tsx", import.meta.url), "utf8");
  for (const needle of ["SELECT_REGIMEN_MESSAGE", "Latest simulation", "Previous simulation results", "ConfidenceBadge", "InputsUsedCard", "ModelStatusNotice", "unavailableExplanation"]) {
    assert.ok(sim.includes(needle), `simulator: ${needle}`);
  }
  for (const needle of ["InputsUsedCard", "ModelStatusNotice", "CONFIDENCE_NOT_APPLICABLE"]) assert.ok(detail.includes(needle), `detail: ${needle}`);
  assert.ok(!/show\(s\.confidence/.test(sim + detail), "confidence is never rendered through the numeric helper");
  assert.ok(!sim.includes("Projected scenario · no model confidence"));
});

// --- scenario risk is never the patient's baseline risk --------------------------------------------------------

const withBaseline = (baselineRisk) => prov({ inputs: { baselineRisk } });

test("scenario risk: a value distinct from the baseline is shown as the scenario's own", () => {
  assert.equal(scenarioRisk("moderate", withBaseline("low")), "moderate");
});

test("scenario risk: absent risk is not assessed", () => {
  assert.equal(scenarioRisk(null, withBaseline("low")), null);
  assert.equal(scenarioRisk(undefined, withBaseline(null)), null);
});

test("scenario risk: the baseline risk echoed into a scenario is NOT scenario risk", () => {
  assert.equal(scenarioRisk("low", withBaseline("low")), null);
  assert.equal(scenarioRisk("Low", withBaseline("low")), null);
  assert.equal(scenarioRisk("low", prov()), null, "no baseline to compare against: cannot show it as scenario-specific");
  assert.equal(scenarioRisk("low", null), null);
});

test("a draft scenario (no risk, no provenance) renders as Risk not assessed; confidence stays Not applicable", () => {
  assert.equal(scenarioRisk(null, null), null);
  const chip = readFileSync(new URL("../components/common/StatusChip.tsx", import.meta.url), "utf8");
  assert.ok(chip.includes('if (!level) return <StatusChip tone="neutral">Risk not assessed</StatusChip>'));
  const page = readFileSync(new URL("../routes/_shell.simulator.tsx", import.meta.url), "utf8");
  assert.ok(page.includes("risk: scenarioRisk(s.risk, s.provenance)"), "API scenarios map risk through scenarioRisk");
  assert.equal(confidenceLabel(null), "Not applicable");
});

// --- recovery is labelled as a regimen-level estimate --------------------------------------------------------

test("recovery wording is honest, values pass through untransformed, and the other labels are unchanged", () => {
  assert.equal(RECOVERY_LABEL, "Estimated recovery");
  assert.equal(RECOVERY_NOTE, "Regimen-level estimate · not patient-specific");
  assert.ok(!/tumou?r|ki-?67|er|her2|risk|duration|cycle|toxicity/i.test(RECOVERY_NOTE), "implies no patient input");
  const page = readFileSync(new URL("../routes/_shell.simulator.tsx", import.meta.url), "utf8");
  assert.ok(page.includes('{show(s.recoveryWeeks, " wks")}'), "recovery value is shown as received");
  assert.ok(page.includes("{RECOVERY_LABEL}") && page.includes("{RECOVERY_NOTE}"));
  assert.ok(page.includes("risk: scenarioRisk(s.risk, s.provenance)"), "risk still goes through scenarioRisk");
  assert.equal(confidenceLabel(null), "Not applicable");
  assert.equal(scenarioRisk("low", prov({ inputs: { baselineRisk: "low" } })), null);
  // A trial/unavailable scenario has no recovery number and the table reports it as not calculated.
  assert.equal(hasOutcomes({ ...NONE }), false);
  assert.equal(scenarioStatus(scenario("t", NONE, prov({ unavailableReason: "x" }))), "unavailable");
});

// --- queued custom scenario reaches the run --------------------------------------------------------------------

test("a queued custom scenario is requested by name only when queued, and its evaluated row is not 'Not yet run'", () => {
  const page = readFileSync(new URL("../routes/_shell.simulator.tsx", import.meta.url), "utf8");
  assert.ok(page.includes("...(pendingDraft ? { name: pendingDraft.name } : {})"), "name is sent only for a queued scenario");
  // The run's own result replaces the displayed set and clears the queue, so Run again cannot duplicate the row.
  assert.ok(page.includes("setRunScenarios(next);") && page.includes("setPendingDraft(null);"));
  // Returned scenarios (custom included) are mapped as evaluated rows, whatever their name.
  assert.ok(page.includes("evaluated: true,") && page.includes("const next = result.scenarios.map(fromApi);"));
  // The row shows its numbers, not the queued placeholder, once the backend returned outcomes.
  const custom = scenario("c", NUMBERS, prov(), { name: "Dose-dense-AC-t", custom: true });
  assert.equal(hasOutcomes(custom), true);
  assert.equal(scenarioStatus(custom), "available");
  assert.equal(custom.name, "Dose-dense-AC-t");
  // An unavailable result keeps its backend reason rather than any placeholder.
  const none = scenario("u", NONE, prov({ unavailableReason: "no regimen" }), { name: "X", custom: true });
  assert.equal(hasOutcomes(none), false);
  assert.equal(runUnavailableReason([none]), "no regimen");
});

test("the selector is pre-filled once from a supported last-run regimen, never from a placeholder", () => {
  const page = readFileSync(new URL("../routes/_shell.simulator.tsx", import.meta.url), "utf8");
  assert.ok(page.includes("supportedRegimen(s.requestedRegimen)") && page.includes("prefilledFor"), "pre-fill uses supportedRegimen, once per patient");
  assert.equal(supportedRegimen("Endocrine therapy"), "Endocrine therapy");
  for (const v of ["Not yet started", "Current treatment", "", null, "Letrozole"]) assert.equal(supportedRegimen(v), undefined, String(v));
  // Run itself still sends only what the selector holds.
  assert.ok(page.includes("const regimen = regimenToRun?.regimen;"));
});
