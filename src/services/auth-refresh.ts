/**
 * Single-flight session refresh + one-shot 401 retry. No browser or framework dependencies (unit-tested in Node).
 *
 * Refresh tokens are single-use and rotated on every `/auth/refresh`, so a page must never send two refreshes
 * with the same cookie. Boot-time session restoration and an API call that happens to get a 401 at the same
 * moment therefore share ONE in-flight refresh promise: later callers await it instead of starting another.
 *
 * Cross-tab: the cookie jar is shared by every tab of the browser, so two tabs that start at the same instant
 * would each send a refresh with the same cookie, and the loser of that race looks like a token replay (which
 * revokes every session). Where the Web Locks API exists, the refresh REQUEST runs inside one origin-wide
 * exclusive lock: tabs refresh one after another, and each later tab sends its request only after the earlier
 * one has finished, so the browser attaches the freshly rotated cookie. Only the right to send the request is
 * coordinated - no token, session or message is ever passed between tabs; every tab still obtains its own
 * access token from its own refresh response and keeps it in its own memory.
 *
 * Without `navigator.locks` (very old browsers, or a non-secure context) the refresh simply runs unlocked,
 * exactly as before this coordination existed: same-tab single-flight still applies, cross-tab simultaneous
 * starts remain a possible race. No token-sharing fallback is attempted.
 */
export type RefreshHandler = () => Promise<string | null>;

/** The subset of the Web Locks `LockManager` that is used here (so tests can supply a fake). */
export interface LockManagerLike {
  request<T>(
    name: string,
    options: { mode?: "exclusive" | "shared"; signal?: AbortSignal },
    callback: () => Promise<T>,
  ): Promise<T>;
}

export interface CoordinatorOptions {
  /** Defaults to `globalThis.navigator?.locks`; pass `null` to disable cross-tab coordination. */
  locks?: LockManagerLike | null;
  /** Lock name shared by all tabs of the origin. */
  lockName?: string;
  /** How long to wait for another tab's refresh before proceeding unlocked (a hung tab must not block us). */
  lockWaitMs?: number;
}

export const REFRESH_LOCK_NAME = "oncotwin:auth-refresh";

export interface RetryOptions {
  /** False for the auth endpoints themselves (login, refresh, logout, ...): a 401 there is not a stale token. */
  allowRefresh: boolean;
}

export function createRefreshCoordinator(options: CoordinatorOptions = {}) {
  let handler: RefreshHandler | null = null;
  let inFlight: Promise<string | null> | null = null;
  const lockName = options.lockName ?? REFRESH_LOCK_NAME;
  const lockWaitMs = options.lockWaitMs ?? 30_000;

  function getLocks(): LockManagerLike | null {
    if (options.locks !== undefined) return options.locks;
    const nav = (globalThis as { navigator?: { locks?: LockManagerLike } }).navigator;
    return nav?.locks ?? null;
  }

  /**
   * Runs `fn` under the cross-tab exclusive lock. The lock is released when `fn` settles, whether it resolved or
   * threw, so a failed refresh never blocks the next tab. If the lock cannot be acquired (waited too long for a
   * stuck holder, or the browser refuses locks here) `fn` runs unlocked - the pre-coordination behaviour.
   */
  async function withCrossTabLock<T>(fn: () => Promise<T>): Promise<T> {
    const locks = getLocks();
    if (!locks) return fn();

    let entered = false;
    const abort = typeof AbortController === "function" ? new AbortController() : null;
    const timer = abort ? setTimeout(() => abort.abort(), lockWaitMs) : null;
    try {
      return await locks.request(lockName, { mode: "exclusive", ...(abort ? { signal: abort.signal } : {}) }, () => {
        entered = true;
        if (timer) clearTimeout(timer);
        return fn();
      });
    } catch (err) {
      if (entered) throw err; // the refresh itself failed: report that, do not retry it
      return fn(); // never got the lock (timeout / unsupported): proceed as before
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  function refresh(): Promise<string | null> {
    if (!handler) return Promise.resolve(null);
    if (inFlight) return inFlight; // someone is already refreshing: share that request, send nothing
    let started: Promise<string | null>;
    try {
      const run = handler;
      started = withCrossTabLock(() => Promise.resolve(run())); // same-tab single-flight is set up below
    } catch (err) {
      started = Promise.reject(err);
    }
    const p: Promise<string | null> = started.finally(() => {
      if (inFlight === p) inFlight = null; // a later, legitimate refresh may start again
    });
    inFlight = p;
    return p;
  }

  /**
   * Sends a request with the current in-memory token. On a 401 it refreshes (shared) and retries exactly once;
   * the retry's response is returned as is - it never triggers another refresh, so there is no loop.
   */
  async function run<R extends { status: number }>(
    send: (token: string | null) => Promise<R>,
    getToken: () => string | null,
    { allowRefresh }: RetryOptions,
  ): Promise<R> {
    let token = getToken();
    // No token yet but the session is being restored: wait for it instead of firing a request that must 401.
    if (!token && allowRefresh && inFlight) token = await inFlight.catch(() => null);

    const response = await send(token);
    if (response.status !== 401 || !allowRefresh || !handler) return response;

    // The token we used may already be stale because a refresh finished while this request was in flight.
    const current = getToken();
    if (current && current !== token) return send(current);

    const refreshed = await refresh().catch(() => null);
    return refreshed ? send(refreshed) : response;
  }

  return {
    setHandler(fn: RefreshHandler | null) {
      handler = fn;
    },
    refresh,
    run,
    isRefreshing: () => inFlight !== null,
  };
}

export type RefreshCoordinator = ReturnType<typeof createRefreshCoordinator>;
