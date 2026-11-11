// Run with: node --experimental-strip-types --test src/services/auth-signout.guard.test.mjs
// H5.2 guards: one centralised sign-out that always clears local state, cannot be undone by an automatic
// refresh while the server revocation is unconfirmed, and signs out the other tabs without sharing any secret.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { createLogoutMarker, createSignOutBus, LOGOUT_PENDING_KEY, SIGNED_OUT_CHANNEL } from "./auth-signout.ts";
import { createSessionController } from "./session-controller.ts";

const tick = () => new Promise((r) => setTimeout(r, 0));
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => ((resolve = a), (reject = b))); return { promise, resolve, reject }; };

// --- fakes -----------------------------------------------------------------------------------------

/** A browser: shared storage, a shared refresh cookie on a fake server, and a BroadcastChannel hub. */
function makeBrowser({ channels = true } = {}) {
  const store = new Map();
  const storage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) };
  const server = { cookieValid: true, logoutFails: false, refreshCalls: 0, logoutCalls: 0 };
  const hub = { channels: [], messages: [] };
  const factory = channels
    ? (name) => {
        const ch = { name, onmessage: null, closed: false,
          postMessage(data) {
            const wire = JSON.parse(JSON.stringify(data)); // structured-clone stand-in
            hub.messages.push({ name, data: wire });
            for (const other of hub.channels) if (other !== ch && !other.closed && other.name === name) queueMicrotask(() => other.onmessage?.({ data: wire }));
          },
          close() { ch.closed = true; } };
        hub.channels.push(ch);
        return ch;
      }
    : null;
  return { store, storage, server, hub, factory };
}

/** A tab on that browser. `refreshOnce` stands in for api-client's shared single-flight refresh. */
function openTab(b, { refresh } = {}) {
  const state = { session: null, token: null, role: null };
  const marker = createLogoutMarker(b.storage);
  const bus = createSignOutBus(b.factory);
  const c = createSessionController({
    refresh: refresh ?? (async () => {
      b.server.refreshCalls += 1; await tick();
      if (!b.server.cookieValid) throw new Error("401 expired/revoked");
      return { accessToken: `tok${b.server.refreshCalls}`, user: { role: "doctor" } };
    }),
    logout: async () => {
      b.server.logoutCalls += 1; await tick();
      if (b.server.logoutFails) throw new Error("network down");
      b.server.cookieValid = false; // server revokes + clears cookie; an already-revoked session is still success
    },
    apply: (s) => { state.session = s; state.token = s?.accessToken ?? null; },
    getToken: () => state.token,
    refreshOnce: () => c.refreshHandler(),
    marker, bus, onRefreshed: (s) => { state.role = s.user.role; },
  });
  const stop = c.start();
  return { c, state, marker, bus, stop };
}

// --- baseline: normal users are unaffected ----------------------------------------------------------

test("normal startup restores the session with exactly one refresh, and 401 recovery still works", async () => {
  const b = makeBrowser(); const t = openTab(b);
  await t.c.boot();
  assert.equal(t.state.token, "tok1"); assert.equal(t.state.role, "doctor");
  assert.equal(b.server.refreshCalls, 1);
  assert.equal(await t.c.refreshHandler(), "tok2", "a 401 recovers through the same refresh");
  assert.equal(b.storage.getItem(LOGOUT_PENDING_KEY), null);
});

test("expired or revoked refresh token leaves the user signed out, without throwing", async () => {
  const b = makeBrowser(); b.server.cookieValid = false;
  const t = openTab(b);
  await t.c.boot();
  assert.equal(t.state.session, null);
  assert.equal(await t.c.refreshHandler(), null);
  assert.equal(t.c.isSignedOut(), false, "that is a normal failed restore, not an intentional sign-out");
});

// --- logout: success ----------------------------------------------------------------------------------

test("logout clears local state on a successful server logout, and refresh can no longer restore it", async () => {
  const b = makeBrowser(); const t = openTab(b);
  await t.c.boot();
  assert.ok(t.state.token);
  const r = await t.c.logout();
  assert.deepEqual(r, { serverRevoked: true });
  assert.equal(t.state.session, null); assert.equal(t.state.token, null);
  assert.equal(b.storage.getItem(LOGOUT_PENDING_KEY), null, "confirmed by the server: nothing pending");
  const before = b.server.refreshCalls;
  assert.equal(await t.c.refreshHandler(), null, "401 recovery does not bring the session back");
  assert.equal(b.server.refreshCalls, before, "and sends no request");
  // a reload: the cookie is gone, so the normal startup refresh is rejected and the user stays signed out
  const reloaded = openTab(b); await reloaded.c.boot();
  assert.equal(reloaded.state.session, null);
});

// --- logout: server failure -----------------------------------------------------------------------------

test("logout clears local state even when the server request fails", async () => {
  const b = makeBrowser(); const t = openTab(b);
  await t.c.boot();
  b.server.logoutFails = true;
  const r = await t.c.logout();
  assert.deepEqual(r, { serverRevoked: false });
  assert.equal(t.state.session, null); assert.equal(t.state.token, null);
  assert.equal(b.storage.getItem(LOGOUT_PENDING_KEY), "1", "unconfirmed: remembered across reloads");
});

test("a failed logout does NOT automatically restore the session (401 recovery and reload)", async () => {
  const b = makeBrowser(); const t = openTab(b);
  await t.c.boot();
  b.server.logoutFails = true;
  await t.c.logout();
  assert.equal(b.server.cookieValid, true, "the HttpOnly cookie is still valid - the page cannot delete it");
  const refreshes = b.server.refreshCalls;

  assert.equal(await t.c.refreshHandler(), null, "401 recovery stays off");
  assert.equal(t.state.session, null);

  const reload = openTab(b); await reload.c.boot();           // same browser storage, fresh page
  assert.equal(reload.state.session, null, "reload does not sign the user back in");
  assert.equal(b.server.refreshCalls, refreshes, "no /auth/refresh was sent");
  assert.ok(b.server.logoutCalls >= 2, "startup retried the logout instead");
});

test("the pending logout is retried at startup and, once confirmed, normal startup behaviour returns", async () => {
  const b = makeBrowser(); const t = openTab(b);
  await t.c.boot();
  b.server.logoutFails = true; await t.c.logout();

  b.server.logoutFails = false;                                 // network is back
  const next = openTab(b); await next.c.boot();
  assert.equal(next.state.session, null);
  assert.equal(b.storage.getItem(LOGOUT_PENDING_KEY), null, "server confirmed the revocation");
  assert.equal(b.server.cookieValid, false);

  const later = openTab(b); await later.c.boot();               // marker gone: ordinary startup attempt
  assert.equal(later.state.session, null, "the cookie is gone, so the user is simply signed out");
});

test("signing in again ends the pending sign-out and re-enables refresh", async () => {
  const b = makeBrowser(); const t = openTab(b);
  await t.c.boot(); b.server.logoutFails = true; await t.c.logout();
  assert.equal(await t.c.refreshHandler(), null);
  t.c.signedIn({ accessToken: "fresh-login", user: { role: "doctor" } });
  assert.equal(t.state.token, "fresh-login");
  assert.equal(b.storage.getItem(LOGOUT_PENDING_KEY), null);
  assert.ok(await t.c.refreshHandler(), "refresh works again after a real login");
});

// --- idempotency ---------------------------------------------------------------------------------------

test("repeated logout is safe: concurrent calls share one request, later calls do not error", async () => {
  const b = makeBrowser(); const t = openTab(b);
  await t.c.boot();
  const [x, y] = await Promise.all([t.c.logout(), t.c.logout()]);
  assert.deepEqual(x, y);
  assert.equal(b.server.logoutCalls, 1, "the second call joined the first");
  const z = await t.c.logout();                                 // already revoked server-side: still success
  assert.deepEqual(z, { serverRevoked: true });
  assert.equal(t.state.session, null);
});

test("logging out while already signed out (no session, no cookie) is a harmless no-op", async () => {
  const b = makeBrowser(); b.server.cookieValid = false;
  const t = openTab(b);
  assert.deepEqual(await t.c.logout(), { serverRevoked: true });
  assert.equal(t.state.session, null);
});

test("a refresh that finishes AFTER the user signed out is discarded", async () => {
  const b = makeBrowser(); const gate = deferred();
  const t = openTab(b, { refresh: () => gate.promise });
  const boot = t.c.boot();
  await t.c.logout();
  gate.resolve({ accessToken: "late", user: { role: "doctor" } });
  await boot;
  assert.equal(t.state.session, null);
  assert.equal(t.state.token, null);
});

// --- cross-tab sign-out ---------------------------------------------------------------------------------

test("signing out in tab A signs out tab B (BroadcastChannel)", async () => {
  const b = makeBrowser(); const A = openTab(b); const B = openTab(b);
  await A.c.boot(); await B.c.boot();
  assert.ok(A.state.token && B.state.token);
  await A.c.logout();
  await tick();
  assert.equal(A.state.session, null);
  assert.equal(B.state.session, null, "tab B cleared its own in-memory state");
  const refreshes = b.server.refreshCalls;
  assert.equal(await B.c.refreshHandler(), null, "and tab B will not refresh its way back in");
  assert.equal(b.server.refreshCalls, refreshes);
});

test("the broadcast contains no token, session, user, cookie or credential - only the event name", async () => {
  const b = makeBrowser(); const A = openTab(b); const B = openTab(b);
  await A.c.boot(); await B.c.boot();
  await A.c.logout(); await tick();
  assert.equal(b.hub.messages.length, 1);
  assert.equal(b.hub.messages[0].name, SIGNED_OUT_CHANNEL);
  assert.deepEqual(b.hub.messages[0].data, { type: "SIGNED_OUT" });
  assert.ok(!/tok\d|access|refresh|cookie|password|session|user/i.test(JSON.stringify(b.hub.messages)));
});

test("other messages on the channel are ignored (a token-bearing or malformed message does not sign anyone out)", async () => {
  const b = makeBrowser(); const B = openTab(b);
  await B.c.boot();
  const spoofer = b.factory(SIGNED_OUT_CHANNEL);
  for (const msg of [{ type: "OTHER" }, { accessToken: "x" }, null, "SIGNED_OUT", 42, {}]) spoofer.postMessage(msg);
  await tick();
  assert.ok(B.state.token, "still signed in");
});

test("without BroadcastChannel sign-out still works locally and nothing throws", async () => {
  const b = makeBrowser({ channels: false }); const A = openTab(b); const B = openTab(b);
  assert.equal(A.bus.available, false);
  await A.c.boot(); await B.c.boot();
  assert.deepEqual(await A.c.logout(), { serverRevoked: true });
  await tick();
  assert.equal(A.state.session, null);
  assert.ok(B.state.token, "documented limitation: no event, so tab B signs out only when its token expires");
});

test("a throwing BroadcastChannel never blocks sign-out", async () => {
  const b = makeBrowser();
  const exploding = createSignOutBus(() => { throw new Error("channel blocked"); });
  assert.doesNotThrow(() => exploding.broadcastSignedOut());
  assert.doesNotThrow(() => exploding.onSignedOut(() => {})());
  const t = openTab(b); await t.c.boot();
  assert.deepEqual(await t.c.logout(), { serverRevoked: true });
});

test("the real BroadcastChannel (Node) delivers SIGNED_OUT between two buses, and only that", async () => {
  const opened = [];
  const real = (name) => { const ch = new BroadcastChannel(name); opened.push(ch); return ch; };
  const received = [];
  const rx = createSignOutBus(real); const tx = createSignOutBus(real);
  const off = rx.onSignedOut(() => received.push("signed-out"));
  tx.broadcastSignedOut();
  await new Promise((r) => setTimeout(r, 50));
  off();
  opened.forEach((c) => c.close());
  assert.deepEqual(received, ["signed-out"]);
});

// --- marker robustness -----------------------------------------------------------------------------------

test("the logout-pending marker degrades safely when storage is missing or throws", () => {
  for (const storage of [null, { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }, removeItem() { throw new Error("blocked"); } }]) {
    const m = createLogoutMarker(storage);
    assert.doesNotThrow(() => { m.set(); m.clear(); });
    assert.equal(m.isSet(), false);
  }
});

// --- source guards ---------------------------------------------------------------------------------------

const src = fileURLToPath(new URL("..", import.meta.url));
const read = (p) => readFileSync(join(src, p), "utf8");
const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");

test("PortalShell sign-out calls the real logout flow (not a bare link to /login)", () => {
  const code = strip(read("components/layout/PortalShell.tsx"));
  assert.match(code, /useSignOut\(\)/);
  assert.match(code, /onClick=\{\(\) => void signOut\(\)\}/);
  assert.ok(!/<Link[^>]*to="\/login"[^>]*>\s*Sign out/.test(code), "Sign out must not be a plain navigation link");
});

test("TopBar uses the centralised logout flow and has no logout/redirect logic of its own", () => {
  const code = strip(read("components/layout/TopBar.tsx"));
  assert.match(code, /useSignOut\(\)/);
  assert.ok(!/\blogout\b/.test(code), "TopBar must not call logout directly");
  assert.ok(!/navigate\(\{ to: "\/login" \}\)/.test(code), "the redirect lives in useSignOut");
});

test("the sidebar Logout item (same bug as the portals) also uses the centralised flow", () => {
  const code = strip(read("components/layout/AppSidebar.tsx"));
  assert.match(code, /useSignOut\(\)/);
  assert.match(code, /tooltip="Logout" onClick=\{\(\) => void signOut\(\)\}/);
  assert.ok(!/to="\/login"[\s\S]{0,120}Logout/.test(code));
});

test("useSignOut always redirects after logout, whether or not the server could be reached", () => {
  const code = strip(read("components/auth/useSignOut.ts"));
  const logoutAt = code.indexOf("await logout()");
  const navAt = code.indexOf('navigate({ to: "/login" })');
  assert.ok(logoutAt > 0 && navAt > logoutAt, "navigate must follow logout");
  assert.ok(!/try\s*\{/.test(code) && !/if \(serverRevoked\)[\s\S]*navigate/.test(code), "navigation is unconditional");
});

test("sign-out signalling carries no secrets and stores nothing but the pending marker", () => {
  const bus = strip(read("services/auth-signout.ts"));
  assert.match(bus, /postMessage\(\{ type: SIGNED_OUT_EVENT \}\)/);
  assert.ok(!/accessToken|refreshToken|AuthSession|Authorization|Bearer|password|\buser\b/i.test(bus.replace(/non-credential/gi, "")), "no credentials in the signalling module");
  const keys = [...bus.matchAll(/\?\.(?:getItem|setItem|removeItem)\(([^,)]+)/g)].map((m) => m[1].trim());
  assert.ok(keys.length > 0 && keys.every((k) => k === "LOGOUT_PENDING_KEY"), `unexpected storage keys: ${keys}`);
  const provider = strip(read("components/auth/AuthProvider.tsx"));
  assert.ok(!/oncotwin\.session/.test(provider + bus));
});

test("the provider delegates to the controller and keeps exactly one refresh path", () => {
  const code = strip(read("components/auth/AuthProvider.tsx"));
  assert.match(code, /createSessionController/);
  assert.equal((code.match(/authService\.refresh\(/g) ?? []).length, 1);
  assert.match(code, /refreshOnce: \(\) => refreshSessionOnce\(\)/);
});
