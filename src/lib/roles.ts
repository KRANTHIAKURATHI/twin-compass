import type { UserRole } from "@/types/models";

/**
 * Role metadata for navigation. The role VALUE now lives in the auth session
 * (`useAuth()` from `@/components/auth/AuthProvider`) — this module only holds
 * presentation labels so there is a single source of truth for role state.
 */
export const ROLES: readonly UserRole[] = ["doctor", "patient", "researcher", "admin"];

export type Role = UserRole;

export const roleLabels: Record<UserRole, string> = {
  doctor: "Doctor",
  patient: "Patient",
  researcher: "Researcher",
  admin: "Admin",
};
