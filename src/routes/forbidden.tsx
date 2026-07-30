import { createFileRoute, Link } from "@tanstack/react-router";
import { Home, Lock } from "lucide-react";

import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/forbidden")({
  head: () => ({
    meta: [
      { title: "Permission denied — OncoTwin" },
      { name: "description", content: "You do not have the clinical role required to view this area of OncoTwin." },
      { name: "robots", content: "noindex" },
      { property: "og:title", content: "Permission denied — OncoTwin" },
      { property: "og:description", content: "You do not have the clinical role required to view this area of OncoTwin." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ForbiddenPage,
});

function ForbiddenPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-surface px-4 text-center">
      <span className="flex size-14 items-center justify-center rounded-2xl bg-primary-soft text-primary">
        <Lock className="size-7" aria-hidden="true" />
      </span>
      <p className="mt-6 font-display text-5xl font-semibold tracking-tight">403</p>
      <h1 className="mt-2 text-xl font-semibold">Permission denied</h1>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
        Your role does not include access to this area. Ask a workspace administrator to grant the required permission.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Button asChild>
          <Link to="/">
            <Home className="size-4" aria-hidden="true" /> Back to dashboard
          </Link>
        </Button>
        <Button variant="outline" asChild>
          <Link to="/help">Contact support</Link>
        </Button>
      </div>
    </div>
  );
}
