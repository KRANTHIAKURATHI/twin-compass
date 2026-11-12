import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Stethoscope } from "lucide-react";

import { NotConnectedPage } from "@/components/common/NotConnectedPage";

export const Route = createFileRoute("/_admin/admin/doctors")({
  head: () => ({
    meta: [
      { title: "Doctors Directory — OncoTwin Admin" },
      { name: "description", content: "Clinician accounts, departments and caseloads across every connected hospital." },
      { property: "og:title", content: "Doctors Directory — OncoTwin Admin" },
      { property: "og:description", content: "Clinician accounts, departments and caseloads across every connected hospital." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(DoctorsPage, { variant: "table" }),
});

function DoctorsPage() {
  return (
    <NotConnectedPage
      title="Doctors"
      description="Clinician accounts across the network."
      icon={Stethoscope}
      what="Doctor accounts"
    />
  );
}
