import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Building2 } from "lucide-react";

import { NotConnectedPage } from "@/components/common/NotConnectedPage";

export const Route = createFileRoute("/_admin/admin/hospitals")({
  head: () => ({
    meta: [
      { title: "Hospital Management — OncoTwin Admin" },
      { name: "description", content: "Manage hospital tenants, capacity and onboarding status across the OncoTwin network." },
      { property: "og:title", content: "Hospital Management — OncoTwin Admin" },
      { property: "og:description", content: "Manage hospital tenants, capacity and onboarding status across the OncoTwin network." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(HospitalsPage, { variant: "table" }),
});

function HospitalsPage() {
  return (
    <NotConnectedPage
      title="Hospital management"
      description="Tenants connected to the OncoTwin platform."
      icon={Building2}
      what="Hospitals"
    />
  );
}
