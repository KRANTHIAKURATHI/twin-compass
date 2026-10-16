import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates, PageErrorState, PageSkeleton } from "@/components/common/PageState";
import { Bell, BellOff, Check } from "lucide-react";

import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useMarkAllNotificationsRead, useNotifications } from "@/hooks/api";

export const Route = createFileRoute("/_patient/portal/notifications")({
  head: () => ({
    meta: [
      { title: "Notifications — OncoTwin Patient Portal" },
      { name: "description", content: "Appointment confirmations, new results and messages from your care team." },
      { property: "og:title", content: "Notifications — OncoTwin Patient Portal" },
      { property: "og:description", content: "Appointment confirmations, new results and messages from your care team." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(PatientNotifications, { variant: "list" }),
});

function PatientNotifications() {
  const { data: notifications = [], isLoading, isError, refetch } = useNotifications("patient");
  const markAllRead = useMarkAllNotificationsRead();
  const hasUnread = notifications.some((n) => n.unread);

  if (isLoading) return <PageSkeleton variant="list" />;
  if (isError)
    return (
      <div className="mx-auto max-w-[800px] pt-4">
        <PageErrorState
          title="Notifications could not be loaded"
          description="We could not load your notifications. This is usually temporary — try again."
          onRetry={() => void refetch()}
        />
      </div>
    );

  return (
    <div className="mx-auto max-w-[800px]">
      <PageHeader
        title="Notifications"
        description="Updates from your care team and the OncoTwin platform."
        actions={
          <Button variant="outline" onClick={() => markAllRead.mutate(undefined)} disabled={!hasUnread || markAllRead.isPending}>
            <Check className="size-4" aria-hidden="true" /> Mark all read
          </Button>
        }
      />

      {notifications.length === 0 ? (
        <EmptyState icon={BellOff} title="You're all caught up" description="No notifications right now." />
      ) : (
        <div className="space-y-3">
          {notifications.map((n) => (
            <Card key={n.id} className={n.unread ? "border-primary/30 bg-primary-soft/30" : "border-transparent"}>
              <CardContent className="flex items-start gap-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                  <Bell className="size-4" aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium">{n.title}</p>
                    {n.unread && <StatusChip tone="primary">New</StatusChip>}
                  </div>
                  <p className="mt-0.5 text-sm text-muted-foreground">{n.body}</p>
                </div>
                <span className="shrink-0 pt-0.5 text-xs text-muted-foreground">{n.time}</span>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
