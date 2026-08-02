import { createFileRoute, Outlet } from "@tanstack/react-router";
import { Brain, Database, GitBranch, History, LineChart } from "lucide-react";

import { PortalShell } from "@/components/layout/PortalShell";
import { RequireRole } from "@/components/auth/RequireRole";

export const Route = createFileRoute("/_research")({
  component: ResearchLayout,
});

const nav = [
  { label: "Models", to: "/research/models", icon: Brain },
  { label: "Datasets", to: "/research/datasets", icon: Database },
  { label: "Training History", to: "/research/training", icon: History },
  { label: "Model Versions", to: "/research/versions", icon: GitBranch },
  { label: "Performance", to: "/research/performance", icon: LineChart },
];

function ResearchLayout() {
  return (
    <PortalShell brand="OncoTwin" tagline="Research Portal" icon={Brain} nav={nav}>
      <RequireRole roles={["researcher", "admin"]}>
        <Outlet />
      </RequireRole>
    </PortalShell>
  );
}
