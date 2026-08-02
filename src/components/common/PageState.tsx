import type { ComponentType, ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

import { CardGridSkeleton, ChartSkeleton, DetailSkeleton, ListSkeleton, TableSkeleton } from "@/components/common/Skeletons";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export type SkeletonVariant = "cards" | "table" | "list" | "detail" | "chart";

/** Full page skeleton: header placeholder plus a body matching the page shape. */
export function PageSkeleton({ variant = "list" }: { variant?: SkeletonVariant }) {
  return (
    <div className="mx-auto max-w-[1300px]" aria-busy="true" aria-live="polite">
      <div className="mb-6 space-y-3">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-7 w-64" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </div>
      <div className="space-y-4">
        {variant === "cards" && (
          <>
            <CardGridSkeleton />
            <ChartSkeleton />
          </>
        )}
        {variant === "table" && <TableSkeleton />}
        {variant === "list" && <ListSkeleton />}
        {variant === "detail" && <DetailSkeleton />}
        {variant === "chart" && <ChartSkeleton />}
      </div>
      <span className="sr-only">Loading page content</span>
    </div>
  );
}

/** Inline, retryable error block. Same card language as the rest of the app. */
export function PageErrorState({
  title = "Something went wrong",
  description = "We could not load this data. This is usually temporary — try again.",
  onRetry,
  action,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  action?: ReactNode;
}) {
  return (
    <Card className="border-destructive/30 bg-destructive/5 shadow-none">
      <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
        <span className="flex size-11 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
          <AlertTriangle className="size-5" aria-hidden="true" />
        </span>
        <div>
          <p className="text-base font-medium">{title}</p>
          <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{description}</p>
        </div>
        <div className="flex items-center gap-2 pt-1">
          {onRetry && (
            <Button variant="outline" onClick={onRetry}>
              <RotateCcw className="size-4" aria-hidden="true" /> Try again
            </Button>
          )}
          {action}
        </div>
      </CardContent>
    </Card>
  );
}

/** Page-level error boundary body used by route `errorComponent`. */
export function RouteErrorState({ reset }: { reset?: () => void }) {
  return (
    <div className="mx-auto max-w-[900px] pt-4">
      <PageErrorState onRetry={reset ? () => reset() : () => window.location.reload()} />
    </div>
  );
}

/** Simulated async load so every page exercises loading → success (and retryable error). */
export function useSimulatedLoad(delay = 550) {
  const [status, setStatus] = useState<"loading" | "error" | "success">("loading");
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let active = true;
    setStatus("loading");
    const t = setTimeout(() => {
      if (active) setStatus("success");
    }, delay);
    return () => {
      active = false;
      clearTimeout(t);
    };
  }, [delay, nonce]);

  const retry = useCallback(() => setNonce((n) => n + 1), []);
  return { status, loading: status === "loading", error: status === "error", retry };
}

/**
 * Wraps a page component with a loading skeleton and a retryable error state
 * without touching the page's own layout or design.
 */
export function withPageStates<P extends object>(
  Component: ComponentType<P>,
  options: { variant?: SkeletonVariant; delay?: number } = {},
) {
  function PageWithStates(props: P) {
    const { loading, error, retry } = useSimulatedLoad(options.delay);
    if (loading) return <PageSkeleton variant={options.variant} />;
    if (error)
      return (
        <div className="mx-auto max-w-[900px] pt-4">
          <PageErrorState onRetry={retry} />
        </div>
      );
    return <Component {...props} />;
  }
  PageWithStates.displayName = `withPageStates(${Component.displayName ?? Component.name ?? "Page"})`;
  return PageWithStates;
}
