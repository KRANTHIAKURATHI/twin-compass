// Run with: node --test src/lib/provenance.guard.test.mjs   (no dependencies)
// Guards Phase 5 labelling: no UI text may claim a quantity the underlying model does not produce.
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const SKIP = /(mock-|fixtures|routeTree|\.test\.|[\/]types[\/]|[\/]contracts)/;
function files(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? files(p) : /\.(tsx?|mjs)$/.test(n) && !SKIP.test(p) ? [p] : [];
  });
}
const sources = files(root).map((p) => [p, readFileSync(p, "utf8")]);

const FORBIDDEN = [
  [/5-year survival(?! prediction\b)/i, "claims a 5-year survival the data does not carry (stored survival value / model estimate at N years)"],
  [/survival probability(?! recorded)/i, "'survival probability' - say what it is (stored value, heuristic estimate, model estimate)"],
  [/calibrated/i, "no model here has assessed calibration"],
  [/Recurrence risk \(5y\)/i, "the heuristic recurrence value is not a 5-year risk"],
  [/Northfield longitudinal/i, "invented cohort / AUC claim"],
];

test("no misleading prediction terminology in the UI source", () => {
  const hits = [];
  for (const [path, text] of sources) {
    for (const [re, why] of FORBIDDEN) {
      // allow the explicit disclaimer "Not a 5-year prediction"
      const cleaned = text.replace(/Not a 5-year prediction/g, "");
      if (re.test(cleaned)) hits.push(`${path.replace(root, "src")}: ${why}`);
    }
  }
  assert.deepEqual(hits, []);
});

test("nullable values render as 'Not available', never an em dash helper or a zero", () => {
  const bad = sources.filter(([, t]) => /const show = [^;]*"—"/.test(t)).map(([p]) => p);
  assert.deepEqual(bad, []);
});

test("every model family has its required provenance label", () => {
  const lib = readFileSync(join(root, "lib", "provenance.ts"), "utf8");
  for (const s of ["Heuristic estimate", "Research model — Overall Survival", "Research model — Recurrence-Free Survival",
    "Projected scenario", "Research / experimental",
    "Not clinically validated", "Recorded value", "Not available"]) assert.ok(lib.includes(s), s);
  const pred = readFileSync(join(root, "routes", "_shell.predictions.tsx"), "utf8");
  assert.ok(pred.includes("PROVENANCE.os") && pred.includes("PROVENANCE.rfs") && pred.includes("NOT_VALIDATED"));
  const sim = readFileSync(join(root, "routes", "_shell.simulator.tsx"), "utf8");
  assert.ok(sim.includes("Projected scenario") && sim.includes("Research / experimental"));
});

test("the pCR model is not shown anywhere in the UI", () => {
  const hits = sources.filter(([p, t]) => !/provenance\.ts|guard/.test(p) && /pCR|GSE163882/i.test(t)).map(([p]) => p);
  assert.deepEqual(hits, []);
});
