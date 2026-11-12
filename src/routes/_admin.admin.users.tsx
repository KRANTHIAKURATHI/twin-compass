import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Users } from "lucide-react";

import { NotConnectedPage } from "@/components/common/NotConnectedPage";

export const Route = createFileRoute("/_admin/admin/users")({
  head: () => ({
    meta: [
      { title: "Users — OncoTwin Admin" },
      { name: "description", content: "All platform accounts — doctors, patients, technicians and service identities." },
      { property: "og:title", content: "Users — OncoTwin Admin" },
      { property: "og:description", content: "All platform accounts — doctors, patients, technicians and service identities." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(UsersPage, { variant: "table" }),
});

function UsersPage() {
  return (
    <NotConnectedPage
      title="Users"
      description="Every account with access to the platform."
      icon={Users}
      what="Platform users"
    />
  );
}
