// Production same-origin API proxy (H3). Nitro's Vercel preset turns an external `proxy` route rule into a
// Vercel rewrite in `.vercel/output/config.json`, so `/api/auth/login` is forwarded to `<target>/auth/login`
// at Vercel's edge (the backend mounts its routes WITHOUT an `/api` prefix). The browser only ever sees the
// frontend origin, which makes the httpOnly refresh cookie first-party.
//
// `API_PROXY_TARGET` is the backend's public base URL (a hostname, not a secret). Set it as a Vercel
// *build* environment variable. A Vercel production build without it fails here instead of shipping a
// frontend whose `/api` goes nowhere.
import { defineNitroConfig } from "nitro/config";

const target = process.env.API_PROXY_TARGET?.trim().replace(/\/+$/, "");

if (process.env.VERCEL && !target) {
  throw new Error("API_PROXY_TARGET must be set for Vercel builds (the backend base URL, e.g. https://<service>.onrender.com).");
}
if (target && !/^https:\/\//.test(target)) {
  throw new Error("API_PROXY_TARGET must be an https:// URL.");
}

export default defineNitroConfig({
  routeRules: target ? { "/api/**": { proxy: `${target}/**` } } : {},
});
