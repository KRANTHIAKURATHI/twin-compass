/**
 * Pluggable auth layer.
 *
 * Today the session is resolved from the (mock) `authService` and persisted in
 * local storage. When the backend arrives, only `authService` changes — the
 * provider, the `useAuth` hook, and the route guards stay identical.
 */
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useRouterState } from "@tanstack/react-router";

import { authService, USING_MOCKS } from "@/services";
import { setAuthTokenGetter, setUnauthorizedHandler } from "@/services/api-client";
import type { AuthSession, AuthUser, Credentials, UserRole } from "@/types/models";

const SESSION_KEY = "oncotwin.session";

/** Guards only enforce once a real backend is wired up. */
export const AUTH_ENFORCED = !USING_MOCKS;

interface AuthContextValue {
  user: AuthUser | null;
  /** Always the authenticated account's real role — never a UI-only override. */
  role: UserRole;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: Credentials) => Promise<AuthSession>;
  logout: () => Promise<void>;
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
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [session, setSession] = useState<AuthSession | null>(null);
  const role = session?.user.role ?? "doctor";

  /**
   * useLayoutEffect (not useEffect), and wiring the token getter directly off
   * the locally-read `stored` value (not the `session` state), so the getter
   * is correct synchronously right after mount — before React Query's own
   * passive-effect-triggered fetches run. Passive effects (where those fetches
   * originate) only start once every layout effect in the tree has finished,
   * so this closes the race that otherwise sent the first authenticated
   * request with no token. The initial render still matches the server (null
   * session) so this doesn't reintroduce a hydration mismatch.
   */
  useLayoutEffect(() => {
    const stored = readStoredSession();
    setAuthTokenGetter(() => stored?.accessToken ?? null);
    if (stored) setSession(stored);
  }, []);

  useEffect(() => {
    setAuthTokenGetter(() => session?.accessToken ?? null);
  }, [session]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setSession(null);
      window.localStorage.removeItem(SESSION_KEY);
      queryClient.clear();
      navigate({ to: pathname.startsWith("/portal") ? "/patient-login" : "/login" });
    });
  }, [pathname, navigate, queryClient]);

  const login = useCallback(
    async (credentials: Credentials) => {
      await queryClient.cancelQueries();
      queryClient.clear();
      const next = await authService.login(credentials);
      setSession(next);
      window.localStorage.setItem(SESSION_KEY, JSON.stringify(next));
      return next;
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    await authService.logout();
    setSession(null);
    window.localStorage.removeItem(SESSION_KEY);
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      role,
      isAuthenticated: Boolean(session),
      isLoading: false,
      login,
      logout,
      hasRole: (r) => role === r,
      hasAnyRole: (roles) => roles.includes(role),
    }),
    [session, role, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
