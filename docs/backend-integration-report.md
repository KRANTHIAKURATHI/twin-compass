# OncoTwin — Backend Integration Readiness Report

_Last updated: frontend integration-prep pass. No UI was redesigned; no backend was implemented._

## How the data flow works now

```text
page/component
   └─ hooks (src/hooks/api.ts, TanStack Query)
        └─ services (src/services/index.ts, typed by src/services/contracts.ts)
             ├─ apiRequest()  → real backend when VITE_API_BASE_URL is set
             └─ fixtures.ts   → typed mock snapshots while it is not
```

Set `VITE_API_BASE_URL` and every read/write switches to HTTP. Nothing in
`src/routes/` or `src/components/` needs to change.

## New / key files

| File | Purpose |
| --- | --- |
| `src/types/models.ts` | Single source of truth for all backend entities |
| `src/services/api-client.ts` | fetch wrapper, `ApiError`, bearer-token hook, mock/real switch |
| `src/services/endpoints.ts` | Full endpoint registry — the API surface spec for backend teams |
| `src/services/contracts.ts` | Typed service interfaces (14 services) |
| `src/services/index.ts` | Implementations: real request + fixture fallback per method |
| `src/services/fixtures.ts` | The ONLY module importing `src/lib/mock-*` |
| `src/services/data.ts` | Typed data surface pages import from |
| `src/hooks/query-keys.ts` | Centralized cache keys |
| `src/hooks/api.ts` | Reusable query/mutation hooks (loading, success, error, optimistic) |
| `src/components/auth/AuthProvider.tsx` | Pluggable session + role state, token injection |
| `src/components/auth/RequireRole.tsx` | Doctor / Patient / Researcher / Admin guards |

## Remaining mock data

All of it is isolated behind the fixture layer:

- `src/lib/mock-data.ts`, `src/lib/mock-extra.ts`, `src/lib/mock-lifecycle.ts` —
  re-exported only by `src/services/fixtures.ts`. Delete once every endpoint
  is live.
- No route or component imports `@/lib/mock-*` any more.

## Files that will require backend implementation

Endpoints are enumerated in `src/services/endpoints.ts`. Grouped:

- Auth: login, register, logout, forgot/reset password, `me`
- Patients: CRUD, labs, imaging, timeline
- Digital twins: list, versions, snapshots, resync, restore, archive
- Predictions: latest, history, confidence trend, explainability, run
- Simulations: list, detail, run, save, duplicate, promote
- Documents: list, detail, upload, versions, timeline, links
- OCR: extract, fields, approve, reject
- Reports: list, versions, downloads, generate, export
- Appointments, treatment plan, notifications
- Analytics: dashboard, cohort, accuracy
- Admin: hospitals, doctors, departments, users, audit logs, permissions
- Research: models, datasets, training runs, model versions, performance

## Missing API integrations (frontend side)

- File upload is modelled as JSON metadata (`documentService.upload`); switch to
  `multipart/form-data` once storage exists.
- Report export returns a descriptor, not a binary stream — needs a blob
  download once `/reports/export` is real.
- Realtime (notification badge, twin recalculation status) currently polls via
  Query defaults; swap for websockets/subscriptions if the backend offers them.
- Server-side pagination/sorting is typed (`ListQuery`, `Paginated<T>`) but the
  tables still filter client-side.

## Missing backend dependencies

- `VITE_API_BASE_URL` environment variable
- Auth token issuance/refresh (the client reads `session.accessToken`)
- Role claims per user (`doctor | patient | researcher | admin`)
- File storage for documents/reports
- Model registry + inference service for predictions and simulations
- OCR service for clinical document extraction

## Production-ready components

- Services, contracts, endpoints, api-client, fixtures, data surface
- Query keys + all hooks in `src/hooks/api.ts` (loading/success/error built in,
  optimistic patient updates)
- `AuthProvider`, `RequireRole`, sidebar role switching
- Page state layer: `PageState.tsx`, `DataTablePage.tsx`, per-route
  `errorComponent`s, skeletons and empty states
- Auth forms now submit real field values (`email`, `password`, `name`, token)

## Components that still require work

- Most pages render the typed fixture snapshots from `@/services/data` rather
  than the hooks; converting each page to its hook is a mechanical swap and
  gives live refetch/mutation wiring per page.
- Forms use native validation; adding zod resolvers per form will let backend
  `fieldErrors` from `ApiError` map straight into `setError`.
- Guards enforce only when a backend is configured (`AUTH_ENFORCED`), so the
  demo experience is unchanged — verify the redirect UX once auth is live.
