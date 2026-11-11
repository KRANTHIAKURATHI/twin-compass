/**
 * Session lifecycle rules, kept free of React/browser imports so they can be unit-tested in Node.
 *
 * Normal users: startup restores the session through one single-flight `/auth/refresh`, and a 401 recovers
 * through the same refresh (see auth-refresh.ts). None of that changes.
 *
 * A user who INTENTIONALLY signs out is different. Local state is cleared immediately and unconditionally, the
 * other tabs are told to sign out, and the server logout (which revokes the refresh token and clears the
 * HttpOnly cookie) is attempted. If that request fails the cookie may still be valid and cannot be removed by
 * script, so a persistent "logout pending" marker (see auth-signout.ts) keeps every automatic refresh -
 * startup and 401 recovery - switched off, and the next startup retries the logout instead. Signing in again
 * clears it.
 */
import type { LogoutMarker, SignOutBus } from "./auth-signout";

export interface SessionLike {
  accessToken: string;
}

export interface SessionDeps<S extends SessionLike> {
  /** Calls `/auth/refresh` (one request; the single-flight/lock wrapper is `refreshOnce`). */
  refresh: () => Promise<S>;
  /** Calls `/auth/logout`. The server treats an unknown/revoked/missing refresh token as success. */
  logout: () => Promise<unknown>;
  /** Replace the in-memory session (state + token). `null` signs out locally. */
  apply: (session: S | null) => void;
  getToken: () => string | null;
  /** Shared single-flight refresh (same-tab promise + cross-tab lock) used for startup. */
  refreshOnce: () => Promise<string | null>;
  marker: LogoutMarker;
  bus: SignOutBus;
  onRefreshed?: (session: S) => void;
}

export interface LogoutResult {
  /** True once the server confirmed the refresh session is revoked; false if it could not be reached. */
  serverRevoked: boolean;
}

export function createSessionController<S extends SessionLike>(deps: SessionDeps<S>) {
  // Survives a reload through the marker: a failed logout must not be undone by the next startup.
  let signedOut = deps.marker.isSet();
  let logoutInFlight: Promise<LogoutResult> | null = null;

  /** The handler the API client calls for its single shared refresh (startup and 401 recovery). */
  async function refreshHandler(): Promise<string | null> {
    if (signedOut) return null; // intentional sign-out: never resurrect the session from the cookie
    const startedWith = deps.getToken();
    try {
      const refreshed = await deps.refresh();
      if (signedOut) return null; // signed out while this refresh was in flight: discard its result
      deps.apply(refreshed);
      deps.onRefreshed?.(refreshed);
      return refreshed.accessToken;
    } catch {
      // Expired / revoked / no cookie: stay signed out. Only drop a session if nothing signed in meanwhile.
      if (!signedOut && deps.getToken() === startedWith) deps.apply(null);
      return null;
    }
  }

  async function retryPendingLogout(): Promise<void> {
    try {
      await deps.logout();
      deps.marker.clear(); // server confirmed; the cookie is gone
    } catch {
      /* still pending: stays signed out, will retry on the next startup */
    }
  }

  /** Startup: restore from the refresh cookie, unless the user had intentionally signed out. */
  async function boot(): Promise<void> {
    if (signedOut) {
      await retryPendingLogout();
      return;
    }
    await deps.refreshOnce().catch(() => null);
  }

  /** A successful login (or registration auto-login) ends any pending sign-out. */
  function signedIn(session: S): void {
    signedOut = false;
    deps.marker.clear();
    deps.apply(session);
  }

  /**
   * Intentional sign-out. Idempotent and never rejects: local state is cleared first, whatever the server says,
   * and a repeated call joins the one in flight.
   */
  function logout(): Promise<LogoutResult> {
    if (logoutInFlight) return logoutInFlight;
    signedOut = true;
    deps.marker.set(); // before the request, so a closed tab or failed request leaves it set
    deps.apply(null);
    deps.bus.broadcastSignedOut(); // data-free event; other tabs clear their own memory
    const p: Promise<LogoutResult> = (async () => {
      try {
        await deps.logout();
        deps.marker.clear();
        return { serverRevoked: true };
      } catch {
        return { serverRevoked: false }; // cookie may remain valid: marker stays, refreshes stay off
      }
    })().finally(() => {
      if (logoutInFlight === p) logoutInFlight = null;
    });
    logoutInFlight = p;
    return p;
  }

  /** Listen for another tab's sign-out. Returns the unsubscribe function. */
  function start(): () => void {
    return deps.bus.onSignedOut(() => {
      signedOut = true;
      deps.apply(null);
    });
  }

  return { refreshHandler, boot, signedIn, logout, start, isSignedOut: () => signedOut };
}

export type SessionController<S extends SessionLike> = ReturnType<typeof createSessionController<S>>;
