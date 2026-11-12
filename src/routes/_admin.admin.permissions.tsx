import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { ShieldCheck } from "lucide-react";

import { NotConnectedPage } from "@/components/common/NotConnectedPage";

export const Route = createFileRoute("/_admin/admin/permissions")({
  head: () => ({
    meta: [
      { title: "Permissions — OncoTwin Admin" },
      { name: "description", content: "Role-based capability matrix for doctors, patients, technicians and administrators." },
      { property: "og:title", content: "Permissions — OncoTwin Admin" },
      { property: "og:description", content: "Role-based capability matrix for doctors, patients, technicians and administrators." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(PermissionsPage, { variant: "list" }),
});

function PermissionsPage() {
  return (
    <NotConnectedPage
      title="Permissions"
      description="What each role can do. Roles are enforced server-side, never in the browser."
      icon={ShieldCheck}
      what="The permission matrix"
    />
  );
}
