import { createFileRoute, Outlet } from "@tanstack/react-router";
import { Activity, Bell, CalendarDays, FileText, HeartPulse, LayoutDashboard, Upload, User } from "lucide-react";

import { PortalShell } from "@/components/layout/PortalShell";
import { RequireRole } from "@/components/auth/RequireRole";

export const Route = createFileRoute("/_patient")({
  component: PatientLayout,
});

const nav = [
  { label: "Dashboard", to: "/portal", icon: LayoutDashboard },
  { label: "Upload Reports", to: "/portal/upload", icon: Upload },
  { label: "My Reports", to: "/portal/reports", icon: FileText },
  { label: "My Treatment", to: "/portal/treatment", icon: HeartPulse },
  { label: "My Appointments", to: "/portal/appointments", icon: CalendarDays },
  { label: "Profile", to: "/portal/profile", icon: User },
  { label: "Notifications", to: "/portal/notifications", icon: Bell },
];

function PatientLayout() {
  return (
    <PortalShell brand="OncoTwin" tagline="Patient Portal" icon={Activity} nav={nav}>
      <RequireRole roles={["patient"]}>
        <Outlet />
      </RequireRole>
    </PortalShell>
  );
}
