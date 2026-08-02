/**
 * Role guard (UI level).
 *
 * Wraps a portal layout and renders the existing "permission denied" state
 * for the wrong role. Enforcement is off while the app runs on fixtures
 * (`AUTH_ENFORCED === false`) so nothing about the demo experience changes;
 * the day a backend session exists, guards activate with no restructuring.
 */
import { Link } from "@tanstack/react-router";
import { ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";

import { AUTH_ENFORCED, useAuth } from "@/components/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import type { UserRole } from "@/types/models";

export function RequireRole({ roles, children }: { roles: UserRole[]; children: ReactNode }) {
  const { isLoading, isAuthenticated, hasAnyRole } = useAuth();

  if (!AUTH_ENFORCED) return <>{children}</>;
  if (isLoading) return null;

  if (!isAuthenticated || !hasAnyRole(roles)) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center px-4">
        <div className="max-w-md text-center">
          <ShieldAlert className="mx-auto h-10 w-10 text-muted-foreground" aria-hidden="true" />
          <h1 className="mt-4 text-xl font-semibold text-foreground">Permission denied</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Your account doesn't have access to this area. Contact an administrator if you believe this is a mistake.
          </p>
          <Button asChild className="mt-6">
            <Link to={isAuthenticated ? "/" : "/login"}>{isAuthenticated ? "Go to dashboard" : "Sign in"}</Link>
          </Button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
