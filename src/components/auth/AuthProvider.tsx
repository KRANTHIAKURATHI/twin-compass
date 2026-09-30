/**
 * Pluggable auth layer.
 *
 * Today the session is resolved from the (mock) `authService` and persisted in
 * local storage. When the backend arrives, only `authService` changes — the
 * provider, the `useAuth` hook, and the route guards stay identical.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { authService, USING_MOCKS } from "@/services";
import { setAuthRefreshHandler, setAuthTokenGetter } from "@/services/api-client";
import type { AuthSession, AuthUser, Credentials, UserRole } from "@/types/models";

const SESSION_KEY = "oncotwin.session";
const ROLE_KEY = "oncotwin.role";

/** Guards only enforce once a real backend is wired up. */
export const AUTH_ENFORCED = !USING_MOCKS;

interface AuthContextValue {
  user: AuthUser | null;
  role: UserRole;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: Credentials) => Promise<AuthSession>;
  logout: () => Promise<void>;
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

function readStoredSession(): AuthSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as AuthSession) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [role, setRoleState] = useState<UserRole>("doctor");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const restoreSession = async () => {
      const stored = readStoredSession();
      const storedRole = window.localStorage.getItem(ROLE_KEY) as UserRole | null;
      if (storedRole && !cancelled) setRoleState(storedRole);

      if (!stored) {
        if (!cancelled) setIsLoading(false);
        return;
      }

      try {
        const refreshed = await authService.refresh();
        if (!cancelled) {
          setSession(refreshed);
          setRoleState(refreshed.user.role);
          window.localStorage.setItem(SESSION_KEY, JSON.stringify(refreshed));
        }
      } catch {
        if (!cancelled) {
          setSession(null);
          window.localStorage.removeItem(SESSION_KEY);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setAuthTokenGetter(() => session?.accessToken ?? null);
    setAuthRefreshHandler(async () => {
      try {
        const refreshed = await authService.refresh();
        setSession(refreshed);
        setRoleState(refreshed.user.role);
        window.localStorage.setItem(SESSION_KEY, JSON.stringify(refreshed));
        return refreshed.accessToken;
      } catch {
        setSession(null);
        window.localStorage.removeItem(SESSION_KEY);
        return null;
      }
    });
    return () => setAuthRefreshHandler(null);
  }, [session]);

  const login = useCallback(async (credentials: Credentials) => {
    const next = await authService.login(credentials);
    setSession(next);
    setRoleState(next.user.role);
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(next));
    return next;
  }, []);

  const logout = useCallback(async () => {
    await authService.logout();
    setSession(null);
    window.localStorage.removeItem(SESSION_KEY);
  }, []);

  const setRole = useCallback((next: UserRole) => {
    setRoleState(next);
    window.localStorage.setItem(ROLE_KEY, next);
  }, []);

  const setUser = useCallback((nextUser: AuthUser) => {
    setSession((prev) => {
      if (!prev) return prev; // no-op if somehow called while signed out
      const next = { ...prev, user: nextUser };
      window.localStorage.setItem(SESSION_KEY, JSON.stringify(next));
      return next;
    });
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
