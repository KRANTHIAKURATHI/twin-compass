/**
 * HTTP client placeholder for the future backend.
 *
 * Every service method routes through `apiRequest`. While
 * `VITE_API_BASE_URL` is unset the client stays in mock mode and the service
 * layer resolves local fixtures instead of issuing network calls — flipping
 * the env var is the only change needed to go live.
 */

export const API_BASE_URL: string = (import.meta.env["VITE_API_BASE_URL"] as string | undefined) ?? "";

/** True while no backend is configured. Services fall back to fixtures. */
export const USING_MOCKS = API_BASE_URL.length === 0;

export class ApiError extends Error {
  status: number;
  code?: string;
  /** Field-level errors, ready to feed into react-hook-form `setError`. */
  fieldErrors?: Record<string, string>;

  constructor(message: string, status = 500, options?: { code?: string; fieldErrors?: Record<string, string> }) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = options?.code;
    this.fieldErrors = options?.fieldErrors;
  }
}

type TokenGetter = () => string | null;

let getToken: TokenGetter = () => null;

/** Plug the auth provider in without touching call sites. */
export function setAuthTokenGetter(fn: TokenGetter) {
  getToken = fn;
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
    throw new ApiError(`No API base URL configured — ${path} is served from fixtures.`, 503, {
      code: "MOCK_MODE",
    });
  }

  const token = getToken();
  const response = await fetch(buildUrl(path, options.query), {
    method: options.method ?? "GET",
    signal: options.signal,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? ((await response.json().catch(() => null)) as Record<string, any> | null) : null;

  if (!response.ok) {
    throw new ApiError(payload?.["message"] ?? payload?.["detail"] ?? response.statusText, response.status, {
      code: payload?.["code"],
      fieldErrors: payload?.["errors"] ?? payload?.["fieldErrors"],
    });
  }

  return payload as T;
}

/** Simulated latency used by the mock adapters so loading states are real. */
export const MOCK_LATENCY = 220;

export function mockResolve<T>(data: T, ms = MOCK_LATENCY): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(data), ms));
}

/**
 * Runs the real request when a backend is configured, otherwise the fixture
 * fallback. Service methods stay one-liners and the swap is invisible to UI.
 */
export async function withFallback<T>(
  request: () => Promise<T>,
  fallback: () => T | Promise<T>,
  ms = MOCK_LATENCY,
): Promise<T> {
  if (USING_MOCKS) return mockResolve(await fallback(), ms);
  return request();
}
