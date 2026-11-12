import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { ScrollText } from "lucide-react";

import { NotConnectedPage } from "@/components/common/NotConnectedPage";

export const Route = createFileRoute("/_admin/admin/audit")({
  head: () => ({
    meta: [
      { title: "Audit Logs — OncoTwin Admin" },
      { name: "description", content: "Immutable record of every clinical and administrative action on the platform." },
      { property: "og:title", content: "Audit Logs — OncoTwin Admin" },
      { property: "og:description", content: "Immutable record of every clinical and administrative action on the platform." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(AuditPage, { variant: "table" }),
});

function AuditPage() {
  return (
    <NotConnectedPage
      title="Audit logs"
      description="Append-only record of clinical and administrative actions."
      icon={ScrollText}
      what="Audit logs"
    />
  );
}
