import { createFileRoute, Outlet } from "@tanstack/react-router";
import { Building2, ScrollText, ShieldCheck, Stethoscope, Users, Network } from "lucide-react";

import { PortalShell } from "@/components/layout/PortalShell";
import { RequireRole } from "@/components/auth/RequireRole";

export const Route = createFileRoute("/_admin")({
  component: AdminLayout,
});

const nav = [
  { label: "Hospitals", to: "/admin/hospitals", icon: Building2 },
  { label: "Doctors", to: "/admin/doctors", icon: Stethoscope },
  { label: "Departments", to: "/admin/departments", icon: Network },
  { label: "Users", to: "/admin/users", icon: Users },
  { label: "Audit Logs", to: "/admin/audit", icon: ScrollText },
  { label: "Permissions", to: "/admin/permissions", icon: ShieldCheck },
];

function AdminLayout() {
  return (
    <PortalShell brand="OncoTwin" tagline="Admin Portal" icon={ShieldCheck} nav={nav}>
      <RequireRole roles={["admin"]}>
        <Outlet />
      </RequireRole>
    </PortalShell>
  );
}
