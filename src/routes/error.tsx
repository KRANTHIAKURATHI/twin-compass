import { createFileRoute, Link } from "@tanstack/react-router";
import { Home, RefreshCw, ServerCrash } from "lucide-react";

import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/error")({
  head: () => ({
    meta: [
      { title: "Something went wrong — OncoTwin" },
      { name: "description", content: "An unexpected server error occurred while loading the OncoTwin platform." },
      { name: "robots", content: "noindex" },
      { property: "og:title", content: "Something went wrong — OncoTwin" },
      { property: "og:description", content: "An unexpected server error occurred while loading the OncoTwin platform." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ServerErrorPage,
});

function ServerErrorPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-surface px-4 text-center">
      <span className="flex size-14 items-center justify-center rounded-2xl bg-risk-soft text-risk">
        <ServerCrash className="size-7" aria-hidden="true" />
      </span>
      <p className="mt-6 font-display text-5xl font-semibold tracking-tight">500</p>
      <h1 className="mt-2 text-xl font-semibold">Something went wrong on our side</h1>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
        No patient data was lost. Our team has been notified — try again in a moment.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Button onClick={() => window.location.reload()}>
          <RefreshCw className="size-4" aria-hidden="true" /> Retry
        </Button>
        <Button variant="outline" asChild>
          <Link to="/">
            <Home className="size-4" aria-hidden="true" /> Dashboard
          </Link>
        </Button>
      </div>
    </div>
  );
}
