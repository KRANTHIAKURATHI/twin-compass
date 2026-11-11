// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  // Dev-only: mirrors the production Vercel rewrite (vercel.json) so the browser talks to a same-origin
  // `/api/*` that reaches the backend WITHOUT the `/api` prefix. Run with VITE_API_BASE_URL=/api.
  // The Origin header is left untouched (changeOrigin: false) so the backend's origin check sees the dev origin.
  vite: {
    server: {
      proxy: {
        "/api": {
          target: process.env.API_PROXY_TARGET ?? "http://localhost:8000",
          changeOrigin: false,
          rewrite: (path: string) => path.replace(/^\/api/, ""),
        },
      },
    },
  },
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
});
