// Run with: node --experimental-strip-types --test src/services/auth-refresh-crosstab.guard.test.mjs
// H5.1 guards: tabs coordinate refresh through the Web Locks API so simultaneous page loads cannot race the
// single-use, atomic refresh-token rotation. No token is ever shared between tabs.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { createRefreshCoordinator } from "./auth-refresh.ts";

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

/** A faithful-enough stand-in for navigator.locks: exclusive, FIFO, abortable while queued. One instance = one browser. */
class FakeLocks {
  constructor() { this.queues = new Map(); this.held = new Set(); this.log = []; this.requests = []; }
  request(name, options, callback) {
    this.requests.push({ name, options: { ...options, signal: options.signal ? "AbortSignal" : undefined } });
    return new Promise((resolve, reject) => {
      const q = this.queues.get(name) ?? [];
      this.queues.set(name, q);
      const entry = { callback, resolve, reject, started: false };
      options.signal?.addEventListener("abort", () => {
        if (entry.started) return; // a granted lock is unaffected by a later abort
        const i = q.indexOf(entry);
        if (i >= 0) q.splice(i, 1);
        reject(new DOMException("The request was aborted.", "AbortError"));
      });
      q.push(entry);
      this.#pump(name);
    });
  }
  #pump(name) {
    const q = this.queues.get(name);
    if (this.held.has(name) || !q.length) return;
    const entry = q.shift();
    entry.started = true;
    this.held.add(name);
    this.log.push("acquire");
    Promise.resolve()
      .then(() => entry.callback())
      .then(entry.resolve, entry.reject)
      .finally(() => { this.held.delete(name); this.log.push("release"); this.#pump(name); });
  }
}

/** A backend with a browser-shared cookie jar, single-use rotation and replay => revoke-all (like local_provider). */
function makeServer() {
  let cookie = "c0", counter = 0, inflight = 0;
  const used = new Set();
  const s = { requests: 0, maxInflight: 0, revoked: false, failNext: 0,
    get cookie() { return cookie; },
    async refresh() {
      s.requests += 1; inflight += 1; s.maxInflight = Math.max(s.maxInflight, inflight);
      const sent = cookie;            // the browser attaches the cookie jar's value at send time
      try {
        await delay(10);              // network + server time
        if (s.failNext > 0) { s.failNext -= 1; throw new Error("network down"); }
        if (s.revoked || used.has(sent)) { s.revoked = true; throw new Error("401 replay -> all sessions revoked"); }
        used.add(sent);               // atomic claim
        const next = `c${++counter}`;
        await delay(5);
        cookie = next;                // Set-Cookie applied when the response arrives
        return `access-for-${sent}`;
      } finally { inflight -= 1; }
    } };
  return s;
}

function makeTab(server, locks, extra = {}) {
  const tab = { token: null };
  tab.c = createRefreshCoordinator({ locks, ...extra });
  tab.c.setHandler(async () => (tab.token = await server.refresh())); // the token stays in THIS tab's memory
  return tab;
}

// --- the race itself, and the fix ---------------------------------------------------------------

test("WITHOUT coordination, two tabs starting together race the single-use token (the bug)", async () => {
  const server = makeServer();
  const [a, b] = [makeTab(server, null), makeTab(server, null)];
  const out = await Promise.allSettled([a.c.refresh(), b.c.refresh()]);
  assert.deepEqual(out.map((o) => o.status).sort(), ["fulfilled", "rejected"]);
  assert.equal(server.revoked, true, "the loser is treated as a replay and revokes everything");
  assert.equal(server.maxInflight, 2);
});

test("WITH Web Locks, simultaneous tab startup never races: both succeed, one request at a time", async () => {
  const server = makeServer();
  const locks = new FakeLocks();
  const [a, b] = [makeTab(server, locks), makeTab(server, locks)];
  const [ta, tb] = await Promise.all([a.c.refresh(), b.c.refresh()]);
  assert.equal(server.revoked, false);
  assert.equal(server.maxInflight, 1, "never two /auth/refresh in flight at once");
  assert.equal(server.requests, 2, "one refresh per tab (each tab needs its own access token)");
  assert.ok(ta && tb);
  assert.notEqual(ta, tb, "the second tab used the cookie rotated by the first");
});

test("many tabs at once (browser session restore) are serialised without a replay", async () => {
  const server = makeServer();
  const locks = new FakeLocks();
  const tabs = Array.from({ length: 6 }, () => makeTab(server, locks));
  const tokens = await Promise.all(tabs.map((t) => t.c.refresh()));
  assert.equal(server.revoked, false);
  assert.equal(server.maxInflight, 1);
  assert.equal(new Set(tokens).size, 6);
});

// --- same-tab single-flight is unchanged --------------------------------------------------------

test("same-tab single-flight still holds with locks: three callers, one request, one lock acquisition", async () => {
  const server = makeServer();
  const locks = new FakeLocks();
  const tab = makeTab(server, locks);
  const [x, y, z] = await Promise.all([tab.c.refresh(), tab.c.refresh(), tab.c.refresh()]);
  assert.equal(x, y); assert.equal(y, z);
  assert.equal(server.requests, 1);
  assert.equal(locks.log.filter((l) => l === "acquire").length, 1);
});

// --- lock lifecycle -------------------------------------------------------------------------------

test("the lock is released after a successful refresh, and a later refresh proceeds", async () => {
  const server = makeServer();
  const locks = new FakeLocks();
  const a = makeTab(server, locks), b = makeTab(server, locks);
  await a.c.refresh();
  assert.equal(locks.held.size, 0, "released");
  assert.deepEqual(locks.log, ["acquire", "release"]);
  assert.ok(await b.c.refresh(), "a later refresh (another tab) proceeds");
  assert.ok(await a.c.refresh(), "and so does a later refresh in the first tab");
  assert.equal(server.revoked, false);
});

test("the lock is released after a FAILED refresh, which is not retried, and the next tab proceeds", async () => {
  const server = makeServer();
  const locks = new FakeLocks();
  const a = makeTab(server, locks), b = makeTab(server, locks);
  server.failNext = 1;
  const failing = a.c.refresh();
  const waiting = b.c.refresh(); // queued behind a's lock
  await assert.rejects(failing, /network down/);
  assert.equal(await waiting.then((t) => typeof t), "string", "the waiting tab still gets to refresh");
  assert.equal(locks.held.size, 0);
  assert.equal(server.requests, 2, "the failure was reported, not retried unlocked");
  assert.equal(server.revoked, false);
});

// --- nothing crosses tabs -------------------------------------------------------------------------

test("no access token crosses tabs: tokens are per tab and the lock manager only ever sees the lock name", async () => {
  const server = makeServer();
  const locks = new FakeLocks();
  const a = makeTab(server, locks), b = makeTab(server, locks);
  await Promise.all([a.c.refresh(), b.c.refresh()]);
  assert.notEqual(a.token, b.token);
  assert.ok(locks.requests.length === 2 && locks.requests.every((r) => r.name === "oncotwin:auth-refresh"));
  assert.ok(locks.requests.every((r) => Object.keys(r.options).every((k) => ["mode", "signal"].includes(k))));
});

test("the coordinator uses no storage or messaging channel at all (source guard)", () => {
  const src = readFileSync(fileURLToPath(new URL("./auth-refresh.ts", import.meta.url)), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
  assert.ok(!/localStorage|sessionStorage|BroadcastChannel|postMessage|MessageChannel|SharedWorker|indexedDB|document\.cookie/.test(src));
});

// --- 401 retry unchanged ---------------------------------------------------------------------------

test("401 -> refresh -> retry once still works with locks, and there is no loop", async () => {
  const locks = new FakeLocks();
  let calls = 0;
  const c = createRefreshCoordinator({ locks });
  c.setHandler(async () => (calls += 1, "new"));
  const sent = [];
  const send = async (t) => (sent.push(t), { status: 401 }); // the server keeps saying 401
  const r = await c.run(send, () => "old", { allowRefresh: true });
  assert.equal(r.status, 401);
  assert.deepEqual(sent, ["old", "new"]);
  assert.equal(calls, 1);
  assert.equal(locks.held.size, 0);
});

test("a 401 while this tab's refresh is queued behind another tab's still sends only one refresh", async () => {
  const server = makeServer();
  const locks = new FakeLocks();
  const other = makeTab(server, locks), mine = makeTab(server, locks);
  const otherRefresh = other.c.refresh();
  const boot = mine.c.refresh();                // this tab's boot refresh is waiting for the lock
  const sent = [];
  const send = async (t) => (sent.push(t), { status: t === mine.token && t ? 200 : 401 });
  const run = mine.c.run(send, () => mine.token, { allowRefresh: true }); // waits for the in-flight boot refresh
  await Promise.all([otherRefresh, boot]);
  assert.equal((await run).status, 200);
  assert.equal(server.requests, 2, "one per tab, none extra");
  assert.equal(server.revoked, false);
});

// --- graceful degradation ----------------------------------------------------------------------------

test("without navigator.locks the refresh runs unlocked and still single-flight", async () => {
  const server = makeServer();
  const tab = makeTab(server, null);
  const [x, y] = await Promise.all([tab.c.refresh(), tab.c.refresh()]);
  assert.equal(x, y);
  assert.equal(server.requests, 1);
});

test("the default (no option) uses globalThis.navigator.locks when present and runs unlocked when absent", async () => {
  const had = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  try {
    for (const navigatorValue of [undefined, {}]) {
      Object.defineProperty(globalThis, "navigator", { value: navigatorValue, configurable: true });
      const c = createRefreshCoordinator();
      c.setHandler(async () => "t");
      assert.equal(await c.refresh(), "t");
    }
    const locks = new FakeLocks();
    Object.defineProperty(globalThis, "navigator", { value: { locks }, configurable: true });
    const c = createRefreshCoordinator();
    c.setHandler(async () => "t");
    assert.equal(await c.refresh(), "t");
    assert.deepEqual(locks.log, ["acquire", "release"], "the real navigator.locks is picked up by default");
  } finally {
    if (had) Object.defineProperty(globalThis, "navigator", had); else delete globalThis.navigator;
  }
});

test("if the browser refuses locks, the refresh falls back to unlocked and runs exactly once", async () => {
  const refusing = { request: async () => { throw new DOMException("locks unavailable", "SecurityError"); } };
  let calls = 0;
  const c = createRefreshCoordinator({ locks: refusing });
  c.setHandler(async () => (calls += 1, "t"));
  assert.equal(await c.refresh(), "t");
  assert.equal(calls, 1);
});

test("a stuck lock holder cannot block this tab forever: after the wait limit it proceeds unlocked", async () => {
  const locks = new FakeLocks();
  const stuck = createRefreshCoordinator({ locks });
  stuck.setHandler(() => new Promise(() => {})); // a hung tab: never settles
  void stuck.refresh();
  await delay(5);
  let calls = 0;
  const mine = createRefreshCoordinator({ locks, lockWaitMs: 40 });
  mine.setHandler(async () => (calls += 1, "mine"));
  assert.equal(await mine.refresh(), "mine");
  assert.equal(calls, 1);
});
