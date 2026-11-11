/**
 * Pluggable auth layer.
 *
 * The access token lives ONLY in memory (React state + a ref). Nothing that authenticates a request is written
 * to localStorage/sessionStorage, so a script injected into the page cannot lift a stored token. The session
 * survives a reload through the HttpOnly refresh cookie alone: on start the provider calls `/auth/refresh`
 * once (the same single-flight refresh the API client uses for 401s) and keeps the fresh token in memory.
 *
 * Sign-out is a single centralised flow (`logout`, via the session controller): local state is always cleared,
 * other tabs are told with a data-free BroadcastChannel event, and while a sign-out is unconfirmed on the
 * server no automatic refresh is allowed to undo it. See session-controller.ts / auth-signout.ts.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { authService, USING_MOCKS } from "@/services";
import { refreshSessionOnce, setAuthRefreshHandler, setAuthTokenGetter } from "@/services/api-client";
import { createLogoutMarker, createSignOutBus } from "@/services/auth-signout";
import { createSessionController, type LogoutResult, type SessionController } from "@/services/session-controller";
import type { AuthSession, AuthUser, Credentials, UserRole } from "@/types/models";

// UI-only "viewing as" preference. Not a credential: the backend decides what the account may do.
const ROLE_KEY = "oncotwin.role";

/** Guards only enforce once a real backend is wired up. */
export const AUTH_ENFORCED = !USING_MOCKS;

interface AuthContextValue {
  user: AuthUser | null;
  role: UserRole;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: Credentials) => Promise<AuthSession>;
  /** Intentional sign-out. Always clears local auth state and never rejects; `serverRevoked` says whether the
   * server confirmed the refresh session is revoked. */
  logout: () => Promise<LogoutResult>;
  /** UI-only role switch used by the sidebar "Viewing as" control. */
  setRole: (role: UserRole) => void;
  /** Refreshes the cached user in the current session after a profile edit
   * (PATCH /users/profile) — avoids a full re-login just to pick up a
   * changed name/title/hospital. */
  setUser: (user: AuthUser) => void;
  hasRole: (role: UserRole) => boolean;
  hasAnyRole: (roles: UserRole[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [role, setRoleState] = useState<UserRole>("doctor");
  const [isLoading, setIsLoading] = useState(true);
  // The request-time token. Updated synchronously with `session` so a request issued right after a refresh
  // never sees a stale value. Memory only.
  const tokenRef = useRef<string | null>(null);

  const applySession = useCallback((next: AuthSession | null) => {
    tokenRef.current = next?.accessToken ?? null;
    setSession(next);
  }, []);

  // Session rules (boot, 401 recovery, intentional sign-out, cross-tab sign-out) live in one controller.
  const controllerRef = useRef<SessionController<AuthSession> | null>(null);
  const getController = useCallback((): SessionController<AuthSession> => {
    controllerRef.current ??= createSessionController<AuthSession>({
      refresh: () => authService.refresh(),
      logout: () => authService.logout(), // revokes the refresh token and clears the cookie server-side
      apply: applySession,
      getToken: () => tokenRef.current,
      refreshOnce: () => refreshSessionOnce(),
      marker: createLogoutMarker(),
      bus: createSignOutBus(),
      onRefreshed: (refreshed) => setRoleState(refreshed.user.role),
    });
    return controllerRef.current;
  }, [applySession]);

  // API client wiring: the in-memory token, the single refresh shared by boot and 401 retries, and the
  // listener for another tab's sign-out.
  useEffect(() => {
    const controller = getController();
    setAuthTokenGetter(() => tokenRef.current);
    setAuthRefreshHandler(() => controller.refreshHandler());
    const stopListening = controller.start();
    return () => {
      setAuthRefreshHandler(null);
      stopListening();
    };
  }, [getController]);

  // Boot: restore the session from the refresh cookie (unless the user had intentionally signed out). No
  // localStorage session gate and no separate refresh path - `refreshSessionOnce` joins any refresh already
  // running, so a reload sends exactly one `/auth/refresh`.
  useEffect(() => {
    let cancelled = false;
    const storedRole = window.localStorage.getItem(ROLE_KEY) as UserRole | null;
    if (storedRole) setRoleState(storedRole);

    if (USING_MOCKS) {
      // Fixture mode has no backend and no cookie to restore from.
      setIsLoading(false);
      return;
    }
    void getController()
      .boot()
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [getController]);

  const login = useCallback(
    async (credentials: Credentials) => {
      const next = await authService.login(credentials);
      getController().signedIn(next);
      setRoleState(next.user.role);
      return next;
    },
    [getController],
  );

  const logout = useCallback(() => getController().logout(), [getController]);

  const setRole = useCallback((next: UserRole) => {
    setRoleState(next);
    window.localStorage.setItem(ROLE_KEY, next);
  }, []);

  const setUser = useCallback((nextUser: AuthUser) => {
    setSession((prev) => (prev ? { ...prev, user: nextUser } : prev)); // no-op while signed out; token unchanged
    setRoleState(nextUser.role);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      role,
      isAuthenticated: Boolean(session),
      isLoading,
      login,
      logout,
      setRole,
      setUser,
      hasRole: (r) => role === r,
      hasAnyRole: (roles) => roles.includes(role),
    }),
    [session, role, isLoading, login, logout, setRole, setUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
