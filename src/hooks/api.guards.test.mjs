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

// --- no fixture / mock data anywhere in the frontend ------------------------------------------------------------

import { existsSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

test("the frontend ships no fixture data and no fixture fallback", () => {
  const root = new URL("../", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
  for (const gone of ["services/data.ts", "services/fixtures.ts", "lib/mock-data.ts", "lib/mock-extra.ts", "lib/mock-lifecycle.ts"]) {
    assert.ok(!existsSync(join(root, gone)), `${gone} must stay deleted`);
  }
  const walk = (dir) =>
    readdirSync(dir).flatMap((n) => {
      const p = join(dir, n);
      return statSync(p).isDirectory() ? walk(p) : /\.(ts|tsx)$/.test(n) ? [p] : [];
    });
  for (const file of walk(root)) {
    const text = readFileSync(file, "utf8");
    assert.ok(!/from "@\/services\/(data|fixtures)"|from "@\/lib\/mock/.test(text), `${file} imports fixture data`);
  }
  const client = readFileSync(join(root, "services/api-client.ts"), "utf8");
  assert.ok(!client.includes("withFallback") && !client.includes("mockResolve"), "no fixture fallback in the API client");
  assert.ok(!readFileSync(join(root, "services/index.ts"), "utf8").includes("withFallback"), "services call the API directly");
});

// --- patient edit / create routes ----------------------------------------------------------------------------------

test("the edit route is a sibling of the patient detail route, not its child, so it renders the form", () => {
  const tree = readFileSync(new URL("../routeTree.gen.ts", import.meta.url), "utf8");
  // A child of `/patients/$patientId` would never render: the detail page has no <Outlet />.
  assert.ok(!tree.includes("ShellPatientsPatientIdRouteWithChildren"), "the detail route must have no children");
  assert.match(tree, /id: '\/patients_\/\$patientId\/edit',\s*path: '\/patients\/\$patientId\/edit',\s*getParentRoute: \(\) => ShellRoute/);
  const edit = readFileSync(new URL("../routes/_shell.patients_.$patientId.edit.tsx", import.meta.url), "utf8");
  assert.ok(edit.includes('createFileRoute("/_shell/patients_/$patientId/edit")'));
  assert.ok(edit.includes('<PatientForm mode="edit" patient={patient} />'), "the existing form, no second one");
  assert.ok(edit.includes("patientService.get(params.patientId)"), "loads the current patient");
});

test("PatientForm loads the patient, saves through useUpdatePatient and returns to the detail page", () => {
  const form = readFileSync(new URL("../components/patients/PatientForm.tsx", import.meta.url), "utf8");
  assert.ok(form.includes("useState<FormState>(() => initial(patient))"), "edit mode starts from the patient's values");
  assert.ok(form.includes("useUpdatePatient(patient?.id") && form.includes("await updatePatient.mutateAsync(payload)"));
  assert.ok(form.includes('navigate({ to: "/patients/$patientId", params: { patientId: patient!.id } })'));
  assert.ok(/useUpdatePatient[\s\S]*patientService\.update\(id, payload\)/.test(readFileSync(new URL("./api.ts", import.meta.url), "utf8")));
});

test("Add patient opens the full PatientForm route and keeps no second, minimal form", () => {
  const index = readFileSync(new URL("../routes/_shell.patients.index.tsx", import.meta.url), "utf8");
  assert.ok(index.includes('to="/patients/new"'));
  assert.ok(!index.includes("useCreatePatient") && !index.includes("DialogContent") && !index.includes("newHer2"), "no duplicate dialog");
  const route = readFileSync(new URL("../routes/_shell.patients.new.tsx", import.meta.url), "utf8");
  assert.ok(route.includes('<PatientForm mode="create" />'));
  const form = readFileSync(new URL("../components/patients/PatientForm.tsx", import.meta.url), "utf8");
  // Every input the prediction pipeline needs, and blank fields are omitted rather than defaulted.
  for (const field of ["age", "tumorSizeMm", "nodesInvolved", "grade", "ki67", "stage", "erStatus", "prStatus", "her2Status"]) {
    assert.ok(new RegExp(`${field}:`).test(form.split("function toPayload")[1].split("export function PatientForm")[0]), `payload sends ${field}`);
  }
  assert.ok(form.includes('value.trim() === "" ? undefined'));
  assert.ok(form.includes("navigate(newId ? { to: \"/patients/$patientId\", params: { patientId: newId } }"), "create -> patient detail");
});
