import { useEffect, useState } from "react";

/**
 * Role-aware navigation (UI only).
 * TODO(backend): resolve the role from the authenticated session instead of local storage.
 */
export const ROLES = ["doctor", "patient", "researcher", "admin"] as const;
export type Role = (typeof ROLES)[number];

export const roleLabels: Record<Role, string> = {
  doctor: "Doctor",
  patient: "Patient",
  researcher: "Researcher",
  admin: "Admin",
};

const STORAGE_KEY = "oncotwin.role";

export function useRole(): [Role, (role: Role) => void] {
  const [role, setRole] = useState<Role>("doctor");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY) as Role | null;
    if (stored && (ROLES as readonly string[]).includes(stored)) setRole(stored);
  }, []);

  const update = (next: Role) => {
    setRole(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  };

  return [role, update];
}
