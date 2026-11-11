/**
 * The one sign-out action used by every "Sign out" / "Logout" control (top bar, sidebar, all portals).
 * Calls the real logout flow, then goes to the login page whether or not the server could be reached.
 */
import { useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/AuthProvider";

export function useSignOut(): () => Promise<void> {
  const { logout } = useAuth();
  const navigate = useNavigate();
  return useCallback(async () => {
    const { serverRevoked } = await logout(); // never rejects; local state is already cleared
    await navigate({ to: "/login" });
    if (!serverRevoked) {
      toast.warning(
        "Signed out on this device, but the server could not be reached. We will finish signing you out the next time you open the app.",
      );
    }
  }, [logout, navigate]);
}
