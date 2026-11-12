/**
 * HTTP client for the backend.
 *
 * Every service method routes through `apiRequest`. There are no fixtures: while
 * no API base URL is configured (`VITE_API_BASE_URL` unset in development) every
 * request fails with a clear error and the UI shows its error state.
 */
import { resolveApiBase } from "@/services/api-base";
import { createRefreshCoordinator } from "@/services/auth-refresh";

export const API_BASE_URL: string = resolveApiBase(
  import.meta.env["VITE_API_BASE_URL"] as string | undefined,
  import.meta.env.PROD,
);

/** True while no backend is configured. Requests then fail with a clear error; nothing is faked. */
export const USING_MOCKS = API_BASE_URL.length === 0;

export class ApiError extends Error {
  status: number;
  code?: string;
  /** Field-level errors, ready to feed into react-hook-form `setError`. */
  fieldErrors?: Record<string, string>;

  constructor(
    message: string,
    status = 500,
    options?: { code?: string; fieldErrors?: Record<string, string> },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = options?.code;
    this.fieldErrors = options?.fieldErrors;
  }
}

type TokenGetter = () => string | null;

let getToken: TokenGetter = () => null;

/** One shared, single-flight refresh for boot restoration AND the 401 retry (refresh tokens are single-use). */
const coordinator = createRefreshCoordinator();

/** Auth endpoints are not retried via refresh: a 401 there is a credential/session answer, not a stale token. */
const NO_REFRESH_PATHS = new Set([
  "/auth/login",
  "/auth/register",
  "/auth/refresh",
  "/auth/logout",
  "/auth/forgot-password",
  "/auth/reset-password",
]);

/** Plug the auth provider in without touching call sites. */
export function setAuthTokenGetter(fn: TokenGetter) {
  getToken = fn;
}

/**
 * Refresh the session now (or join the refresh already in flight). Resolves to the new access token, or null
 * when the session could not be refreshed. Never issues a second `/auth/refresh` while one is running.
 */
export function refreshSessionOnce(): Promise<string | null> {
  return coordinator.refresh();
}

export function setAuthRefreshHandler(fn: (() => Promise<string | null>) | null) {
  coordinator.setHandler(fn);
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

function buildUrl(path: string, query?: RequestOptions["query"]) {
  const url = `${API_BASE_URL.replace(/\/$/, "")}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  Object.entries(query).forEach(([k, v]) => {
    if (v !== undefined && v !== "") params.set(k, String(v));
  });
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

/**
 * Typed request helper. Throws `ApiError` on non-2xx so React Query error
 * states and form field errors work unchanged once the backend exists.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (USING_MOCKS) {
    throw new ApiError(`No API base URL configured — cannot reach ${path}. Set VITE_API_BASE_URL.`, 503, {
      code: "MOCK_MODE",
    });
  }

  // A FormData body (real file uploads) must go over the wire with its own
  // multipart boundary. Setting Content-Type manually here would omit that
  // boundary and the backend would fail to parse the parts, so the browser
  // sets it instead — this is the one body type that skips JSON.stringify.
  const isFormData = options.body instanceof FormData;

  const request = (token: string | null) => fetch(buildUrl(path, options.query), {
    method: options.method ?? "GET",
    signal: options.signal,
    // Required for the httpOnly refresh-token cookie (set by POST
    // /auth/login and /auth/refresh) to be sent on subsequent requests and
    // stored on the login/refresh response — without this, cross-origin
    // requests (Vite dev server -> API) silently drop the cookie.
    credentials: "include",
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    body:
      options.body === undefined
        ? undefined
        : isFormData
          ? (options.body as FormData)
          : JSON.stringify(options.body),
  });
  // 401 -> (shared) refresh -> retry exactly once; see auth-refresh.ts.
  const response = await coordinator.run(request, () => getToken(), {
    allowRefresh: !NO_REFRESH_PATHS.has(path),
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson
    ? ((await response.json().catch(() => null)) as Record<string, any> | null)
    : null;

  if (!response.ok) {
    // Backend envelope (System Architecture Blueprint Section 12.1 /
    // FastAPI Backend Architecture Blueprint Section 16), consistent across
    // every module: { "error": { "code", "message", "field", "request_id" } }.
    const envelope = payload?.["error"] as
      { code?: string; message?: string; field?: string; request_id?: string } | undefined;
    throw new ApiError(
      envelope?.["message"] ?? payload?.["message"] ?? response.statusText,
      response.status,
      {
        code: envelope?.["code"] ?? payload?.["code"],
        fieldErrors: envelope?.["field"]
          ? { [envelope["field"]]: envelope["message"] }
          : (payload?.["errors"] ?? payload?.["fieldErrors"]),
      },
    );
  }

  return payload as T;
}
