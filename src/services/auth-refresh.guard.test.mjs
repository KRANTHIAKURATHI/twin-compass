// Run with: node --experimental-strip-types --test src/services/auth-refresh.guard.test.mjs   (no extra dependencies)
// H5 guards: single-flight refresh (refresh tokens are single-use) and "no access token in browser storage".
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { createRefreshCoordinator } from "./auth-refresh.ts";

const deferred = () => {
  let resolve, reject;
  const promise = new Promise((res, rej) => ((resolve = res), (reject = rej)));
  return { promise, resolve, reject };
};
const tick = () => new Promise((r) => setTimeout(r, 0));

/** A coordinator whose refresh handler counts calls and is resolved/rejected by the test. */
function setup() {
  const c = createRefreshCoordinator();
  const pending = [];
  const state = { calls: 0 };
  c.setHandler(() => {
    state.calls += 1;
    const d = deferred();
    pending.push(d);
    return d.promise;
  });
  return { c, state, pending };
}
const res = (status) => ({ status });

// --- single-flight ---------------------------------------------------------------------------------

test("boot refresh and a second caller share ONE request and the same result", async () => {
  const { c, state, pending } = setup();
  const boot = c.refresh();
  const other = c.refresh(); // e.g. an API 401 retry arriving while boot restoration is running
  assert.equal(c.isRefreshing(), true);
  pending[0].resolve("fresh-token");
  assert.deepEqual(await Promise.all([boot, other]), ["fresh-token", "fresh-token"]);
  assert.equal(state.calls, 1, "exactly one /auth/refresh");
});

test("a refresh failure is shared by every waiter", async () => {
  const { c, state, pending } = setup();
  const a = c.refresh();
  const b = c.refresh();
  const settled = Promise.allSettled([a, b]);
  pending[0].reject(new Error("401"));
  const [ra, rb] = await settled;
  assert.equal(ra.status, "rejected");
  assert.equal(rb.status, "rejected");
  assert.equal(ra.reason, rb.reason, "the very same failure");
  assert.equal(state.calls, 1);
});

test("once finished, a later legitimate refresh starts a new request", async () => {
  const { c, state, pending } = setup();
  const first = c.refresh();
  pending[0].resolve("t1");
  await first;
  assert.equal(c.isRefreshing(), false);
  const second = c.refresh();
  pending[1].resolve("t2");
  assert.equal(await second, "t2");
  assert.equal(state.calls, 2);
});

test("after a failure the next refresh is allowed again", async () => {
  const { c, state, pending } = setup();
  const first = c.refresh();
  pending[0].reject(new Error("x"));
  await first.catch(() => {});
  const second = c.refresh();
  pending[1].resolve("ok");
  assert.equal(await second, "ok");
  assert.equal(state.calls, 2);
});

test("without a handler refresh resolves null and sends nothing", async () => {
  const c = createRefreshCoordinator();
  assert.equal(await c.refresh(), null);
});

test("five simultaneous 401s cause exactly one refresh", async () => {
  const { c, state, pending } = setup();
  const send = async (t) => res(t === "old" ? 401 : 200);
  const runs = Array.from({ length: 5 }, () => c.run(send, () => "old", { allowRefresh: true }));
  await tick();
  assert.equal(state.calls, 1);
  pending[0].resolve("new");
  const out = await Promise.all(runs);
  assert.ok(out.every((r) => r.status === 200));
  assert.equal(state.calls, 1);
});

// --- 401 retry -------------------------------------------------------------------------------------

test("API 401 -> refresh -> retry exactly once with the new token", async () => {
  const { c, state, pending } = setup();
  const sent = [];
  const send = async (t) => (sent.push(t), res(t === "new" ? 200 : 401));
  const run = c.run(send, () => "old", { allowRefresh: true });
  await tick();
  pending[0].resolve("new");
  assert.equal((await run).status, 200);
  assert.deepEqual(sent, ["old", "new"]);
  assert.equal(state.calls, 1);
});

test("API 401 while a refresh is already running awaits it instead of starting another", async () => {
  const { c, state, pending } = setup();
  const boot = c.refresh(); // boot restoration in flight
  const sent = [];
  const send = async (t) => (sent.push(t), res(t === "new" ? 200 : 401));
  const run = c.run(send, () => "old", { allowRefresh: true });
  await tick();
  assert.equal(state.calls, 1, "the 401 joined the boot refresh");
  pending[0].resolve("new");
  await boot;
  assert.equal((await run).status, 200);
  assert.deepEqual(sent, ["old", "new"]);
  assert.equal(state.calls, 1);
});

test("a request made with no token yet waits for the in-flight restoration (no pointless 401)", async () => {
  const { c, state, pending } = setup();
  let token = null;
  const boot = c.refresh().then((t) => (token = t));
  const sent = [];
  const send = async (t) => (sent.push(t), res(t ? 200 : 401));
  const run = c.run(send, () => token, { allowRefresh: true });
  await tick();
  assert.deepEqual(sent, [], "nothing was sent before the token existed");
  pending[0].resolve("fresh");
  await boot;
  assert.equal((await run).status, 200);
  assert.deepEqual(sent, ["fresh"]);
  assert.equal(state.calls, 1);
});

test("no refresh loop: a 401 after the retry is returned as is, and refresh ran once", async () => {
  const { c, state, pending } = setup();
  const sent = [];
  const send = async (t) => (sent.push(t), res(401)); // server keeps saying 401
  const run = c.run(send, () => "old", { allowRefresh: true });
  await tick();
  pending[0].resolve("new");
  assert.equal((await run).status, 401);
  assert.deepEqual(sent, ["old", "new"], "retried once, not again");
  assert.equal(state.calls, 1);
});

test("a failed refresh returns the original 401 with no retry and no second refresh", async () => {
  const { c, state, pending } = setup();
  const sent = [];
  const send = async (t) => (sent.push(t), res(401));
  const run = c.run(send, () => "old", { allowRefresh: true });
  await tick();
  pending[0].reject(new Error("401"));
  assert.equal((await run).status, 401);
  assert.deepEqual(sent, ["old"]);
  assert.equal(state.calls, 1);
});

test("a token that was already replaced is simply retried, without another refresh", async () => {
  const { c, state } = setup();
  let token = "old";
  const sent = [];
  const send = async (t) => {
    sent.push(t);
    if (t === "old") { token = "newer"; return res(401); } // a refresh finished while this request was in flight
    return res(200);
  };
  assert.equal((await c.run(send, () => token, { allowRefresh: true })).status, 200);
  assert.deepEqual(sent, ["old", "newer"]);
  assert.equal(state.calls, 0);
});

test("auth endpoints (allowRefresh: false) never trigger a refresh", async () => {
  const { c, state } = setup();
  const r = await c.run(async () => res(401), () => null, { allowRefresh: false });
  assert.equal(r.status, 401);
  assert.equal(state.calls, 0);
});

// --- storage rules (source guards) -----------------------------------------------------------------

const src = fileURLToPath(new URL("..", import.meta.url));
function files(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return files(p);
    return /\.(tsx?|mjs)$/.test(n) && !/\.test\.mjs$|routeTree\.gen/.test(n) ? [p] : [];
  });
}
const sources = files(src).map((p) => [p.slice(src.length), readFileSync(p, "utf8")]);
const provider = readFileSync(join(src, "components/auth/AuthProvider.tsx"), "utf8");
const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");

test("oncotwin.session is neither written nor read anywhere in the frontend", () => {
  for (const [file, text] of sources) {
    assert.ok(!/oncotwin\.session|SESSION_KEY|readStoredSession/.test(strip(text)), `${file} still references the stored session`);
  }
});

test("browser storage is used only for the UI-only role preference", () => {
  for (const [file, text] of sources) {
    const code = strip(text);
    assert.ok(!/sessionStorage|indexedDB/.test(code), `${file} uses sessionStorage/indexedDB`);
    // The shadcn sidebar remembers its open/closed state in a UI cookie; nothing else may touch cookies from JS.
    if (!/components[\\/]ui[\\/]sidebar\.tsx$/.test(file)) assert.ok(!/document\.cookie/.test(code), `${file} uses document.cookie`);
    for (const m of code.matchAll(/localStorage\.(getItem|setItem|removeItem)\(([^)]*)\)/g)) {
      assert.match(m[2], /^ROLE_KEY\b/, `${file}: localStorage.${m[1]}(${m[2]}) is not the role preference`);
    }
  }
});

test("no token or session object is passed to storage", () => {
  const code = strip(provider);
  assert.ok(!/localStorage\.setItem\([^)]*(session|token|JSON\.stringify)/i.test(code));
});

test("the provider has exactly one refresh path, shared with the API client, and no localStorage gate", () => {
  const code = strip(provider);
  assert.equal((code.match(/authService\.refresh\(/g) ?? []).length, 1, "only the shared handler may call authService.refresh");
  assert.match(code, /refreshSessionOnce\(\)/);
  assert.ok(!/stored\s*\)|if \(!stored/.test(code), "refresh must not depend on a stored session");
});

test("logout clears in-memory auth state unconditionally (centralised in the session controller)", () => {
  // H5.2 moved the logic out of the provider; the guarantee is unchanged: local state is cleared even when the
  // server request fails, and the provider just delegates.
  const code = strip(provider);
  assert.match(code, /const logout = useCallback\(\(\) => getController\(\)\.logout\(\)/);
  const controller = strip(readFileSync(join(src, "services/session-controller.ts"), "utf8"));
  const m = /function logout\(\)[\s\S]*?\n  \}\n/.exec(controller);
  assert.ok(m, "controller logout not found");
  const applyAt = m[0].indexOf("deps.apply(null)");
  const serverAt = m[0].indexOf("await deps.logout()");
  assert.ok(applyAt > 0 && serverAt > applyAt, "local state must be cleared before the server call, not after it");
  assert.match(m[0], /catch \{[\s\S]*serverRevoked: false/);
});

test("the access token is held in memory only (ref + state), read by the API client through a getter", () => {
  const code = strip(provider);
  assert.match(code, /useRef<string \| null>\(null\)/);
  assert.match(code, /setAuthTokenGetter\(\(\) => tokenRef\.current\)/);
  const client = strip(readFileSync(join(src, "services/api-client.ts"), "utf8"));
  assert.ok(!/localStorage|sessionStorage/.test(client));
  assert.match(client, /Authorization: `Bearer \$\{token\}`/);
});
