// Run with: node --experimental-strip-types --test src/services/api-proxy.guard.test.mjs   (no extra dependencies)
// H3 guard: production reaches the backend only through the same-origin `/api` rewrite, which must strip `/api`.
// It runs a real Vercel-preset build and inspects the route table Vercel will actually use.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { resolveApiBase } from "./api-base.ts";

const root = fileURLToPath(new URL("../..", import.meta.url));
const TARGET = "https://backend.example.onrender.com";

function build(env) {
  rmSync(join(root, ".vercel"), { recursive: true, force: true });
  const clean = { ...process.env };
  delete clean.API_PROXY_TARGET;
  delete clean.VERCEL;
  return spawnSync(process.execPath, [join(root, "node_modules/vite/bin/vite.js"), "build"], {
    cwd: root,
    env: { ...clean, NITRO_PRESET: "vercel", ...env },
    encoding: "utf8",
  });
}

test("production API base is always the same-origin /api, ignoring a cross-origin URL", () => {
  assert.equal(resolveApiBase(undefined, true), "/api");
  assert.equal(resolveApiBase("", true), "/api");
  assert.equal(resolveApiBase("https://backend.onrender.com", true), "/api");
  assert.equal(resolveApiBase("//backend.onrender.com", true), "/api");
  assert.equal(resolveApiBase("/api", true), "/api");
});

test("development keeps its own setting (direct URL, /api via the dev proxy, or mock mode)", () => {
  assert.equal(resolveApiBase("http://localhost:8000", false), "http://localhost:8000");
  assert.equal(resolveApiBase("/api", false), "/api");
  assert.equal(resolveApiBase(undefined, false), "");
});

test("Vercel route table rewrites /api/* to the backend WITHOUT the /api prefix", () => {
  try {
    const r = build({ VERCEL: "1", API_PROXY_TARGET: TARGET });
    assert.equal(r.status, 0, r.stdout + r.stderr);
    const routes = JSON.parse(readFileSync(join(root, ".vercel/output/config.json"), "utf8")).routes;
    const rule = routes.find((x) => x.src === "/api/(.*)");
    assert.ok(rule, "no /api rewrite in the Vercel route table");
    assert.equal(rule.dest, `${TARGET}/$1`);
    // The route must come before the SSR catch-all or the page server would swallow /api/*.
    assert.ok(routes.indexOf(rule) < routes.findIndex((x) => x.dest === "/__server"));

    const map = (path) => {
      const m = new RegExp(`^${rule.src}$`).exec(path);
      return m ? rule.dest.replace("$1", m[1]) : null;
    };
    assert.equal(map("/api/auth/login"), `${TARGET}/auth/login`);
    assert.equal(map("/api/auth/refresh"), `${TARGET}/auth/refresh`);
    assert.equal(map("/api/auth/logout"), `${TARGET}/auth/logout`);
    assert.equal(map("/api/patients/PT-1000"), `${TARGET}/patients/PT-1000`);
    assert.equal(map("/api/ocr/extract"), `${TARGET}/ocr/extract`);
    assert.equal(map("/authors"), null, "non-/api paths must not be proxied");
  } finally {
    rmSync(join(root, ".vercel"), { recursive: true, force: true });
  }
});

test("a Vercel build without API_PROXY_TARGET, or with a non-https one, fails instead of shipping a dead /api", () => {
  try {
    assert.notEqual(build({ VERCEL: "1" }).status, 0);
    assert.notEqual(build({ VERCEL: "1", API_PROXY_TARGET: "http://backend.example.com" }).status, 0);
    assert.equal(existsSync(join(root, ".vercel/output/config.json")), false);
  } finally {
    rmSync(join(root, ".vercel"), { recursive: true, force: true });
  }
});
