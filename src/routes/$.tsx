import { createFileRoute, Link } from "@tanstack/react-router";
import { Home, Search, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/$")({
  head: () => ({
    meta: [
      { title: "Page not found — OncoTwin" },
      { name: "description", content: "The page you were looking for does not exist on the OncoTwin platform." },
      { name: "robots", content: "noindex" },
      { property: "og:title", content: "Page not found — OncoTwin" },
      { property: "og:description", content: "The page you were looking for does not exist on the OncoTwin platform." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: NotFoundPage,
});

function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-surface px-4 text-center">
      <span className="flex size-14 items-center justify-center rounded-2xl bg-warning-soft text-warning-foreground">
        <TriangleAlert className="size-7" aria-hidden="true" />
      </span>
      <p className="mt-6 font-display text-5xl font-semibold tracking-tight">404</p>
      <h1 className="mt-2 text-xl font-semibold">Page not found</h1>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
        The page you were looking for has moved or never existed. Check the address or head back to your dashboard.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Button asChild>
          <Link to="/">
            <Home className="size-4" aria-hidden="true" /> Back to dashboard
          </Link>
        </Button>
        <Button variant="outline" asChild>
          <Link to="/search" search={{ q: "" }}>
            <Search className="size-4" aria-hidden="true" /> Search
          </Link>
        </Button>
      </div>
    </div>
  );
}
