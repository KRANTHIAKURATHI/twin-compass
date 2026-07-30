import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/_research/research/")({
  beforeLoad: () => {
    throw redirect({ to: "/research/models" });
  },
});
