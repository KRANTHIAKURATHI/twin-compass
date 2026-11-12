// Run with: node --test src/hooks/api.guards.test.mjs   (Node >= 20, no dependencies)
//
// Guards the "no request until there is a patient id" rule in src/hooks/api.ts. A query keyed by an id that is still
// "" fires a request for `/predictions//history` (a 404) on the first render of a page that picks its patient
// asynchronously. `usePrognosis` is the reference pattern: `{ enabled: Boolean(patientId) }`.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("./api.ts", import.meta.url), "utf8");

/** Every `export const useX = (idParam: string)` hook, with its full source text. */
function idHooks(text) {
  const out = [];
  for (const chunk of text.split(/\n(?=export const use)/)) {
    const m = /^export const (use\w+) = \((\w+)(\??): string/.exec(chunk);
    if (m && !m[3]) out.push({ name: m[1], param: m[2], chunk, guarded: /enabled:\s*Boolean\(/.test(chunk) });
  }
  return out;
}

const hooks = idHooks(source);
const byName = Object.fromEntries(hooks.map((h) => [h.name, h]));

test("the parser finds the hooks it is meant to check", () => {
  assert.ok(hooks.length >= 20, `found only ${hooks.length} id-keyed hooks`);
  assert.ok(byName.usePrognosis?.guarded, "reference pattern usePrognosis must be guarded");
});

test("every prediction hook is disabled until a patientId exists", () => {
  const predictionHooks = ["usePrediction", "usePredictionHistory", "useConfidenceTrend", "useTumorSizeHistory", "useExplainability", "usePrognosis"];
  for (const name of predictionHooks) {
    assert.ok(byName[name], `${name} not found in api.ts`);
    assert.ok(byName[name].guarded, `${name} must use { enabled: Boolean(${byName[name].param}) }`);
    assert.match(byName[name].chunk, new RegExp(`enabled:\\s*Boolean\\(${byName[name].param}\\)`), `${name} must test its own id parameter`);
  }
});

// Existing hooks outside the predictions family that still fire with an empty id. They are recorded here, not fixed
// (out of scope for the predictions fix). New hooks must be guarded; fixing one of these only shrinks the list.
const KNOWN_UNGUARDED = new Set(["usePatientLabs", "usePatientImaging", "useScenarios", "useTreatmentPlan"]);

test("no new unguarded id-keyed hook is added", () => {
  const unguarded = hooks.filter((h) => !h.guarded).map((h) => h.name);
  const unexpected = unguarded.filter((n) => !KNOWN_UNGUARDED.has(n));
  assert.deepEqual(unexpected, [], `add { enabled: Boolean(id) } to: ${unexpected.join(", ")}`);
});

// --- Search page uses the real API hooks, never fixtures --------------------------------------------------------

test("the Search page reads patients and documents through the API hooks and has no fixture fallback", () => {
  const page = readFileSync(new URL("../routes/_shell.search.tsx", import.meta.url), "utf8");
  assert.ok(!/from "@\/services\/(data|fixtures)"|from "@\/lib\/mock/.test(page), "no direct fixture/mock import");
  assert.ok(page.includes("usePatients()") && page.includes("useDocuments()"), "uses the shared hooks");
  assert.ok(!page.includes("withPageStates"), "no simulated loading wrapper");
  assert.ok(page.includes("isError") && page.includes("PageErrorState"), "failures surface an error state");
  assert.ok(page.includes("PageSkeleton"), "real loading state");
});
