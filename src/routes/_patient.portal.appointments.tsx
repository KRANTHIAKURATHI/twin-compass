import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { CalendarDays } from "lucide-react";

import { NotConnectedPage } from "@/components/common/NotConnectedPage";

export const Route = createFileRoute("/_patient/portal/appointments")({
  head: () => ({
    meta: [
      { title: "My Appointments — OncoTwin Patient Portal" },
      { name: "description", content: "Upcoming and past visits, infusions and imaging appointments with your care team." },
      { property: "og:title", content: "My Appointments — OncoTwin Patient Portal" },
      { property: "og:description", content: "Upcoming and past visits, infusions and imaging appointments with your care team." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(MyAppointments, { variant: "list" }),
});

function MyAppointments() {
  return (
    <NotConnectedPage
      title="My Appointments"
      description="Your scheduled visits and treatment sessions."
      icon={CalendarDays}
      what="Appointments"
    />
  );
}
