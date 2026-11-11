/**
 * Where the browser sends API calls.
 *
 * Production: always the same-origin `/api` path. Vercel rewrites `/api/*` to the Render backend
 * (see vercel.json), so the httpOnly refresh cookie is first-party for the page. A cross-origin
 * absolute URL baked into a production build would silently put the cookie back on a different
 * site (and the browser would drop or block it), so in production an absolute URL is ignored.
 *
 * Development: `VITE_API_BASE_URL` as before - an absolute URL (e.g. http://localhost:8000), a
 * relative path (e.g. `/api`, served by the Vite dev proxy), or unset for fixture/mock mode.
 */
export function resolveApiBase(configured: string | undefined, isProd: boolean): string {
  const value = (configured ?? "").trim();
  if (!isProd) return value;
  if (value === "" || /^[a-z][a-z0-9+.-]*:\/\//i.test(value) || value.startsWith("//")) return "/api";
  return value;
}
