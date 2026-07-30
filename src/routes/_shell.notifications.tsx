import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Bell, BellOff, Boxes, Brain, FlaskConical, ServerCog, UserPlus } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { notifications as seed } from "@/lib/mock-data";

export const Route = createFileRoute("/_shell/notifications")({
  head: () => ({
    meta: [
      { title: "Notifications — OncoTwin" },
      { name: "description", content: "Alerts for new patients, completed predictions, twin updates and system events." },
      { property: "og:title", content: "Notifications — OncoTwin" },
      { property: "og:description", content: "Alerts for new patients, completed predictions, twin updates and system events." },
    ],
  }),
  component: NotificationsPage,
});

const typeMeta = {
  patient: { icon: UserPlus, tone: "primary" as const, label: "Patient" },
  prediction: { icon: Brain, tone: "success" as const, label: "Prediction" },
  twin: { icon: Boxes, tone: "primary" as const, label: "Digital twin" },
  simulation: { icon: FlaskConical, tone: "warning" as const, label: "Simulation" },
  system: { icon: ServerCog, tone: "risk" as const, label: "System" },
};

function NotificationsPage() {
  const [items, setItems] = useState(seed);
  const unread = items.filter((n) => n.unread);

  const list = (rows: typeof items) =>
    rows.length === 0 ? (
      <EmptyState icon={BellOff} title="You're all caught up" description="No notifications in this view right now." />
    ) : (
      <div className="space-y-2">
        {rows.map((n) => {
          const meta = typeMeta[n.type as keyof typeof typeMeta];
          return (
            <Card key={n.id} className={n.unread ? "border-primary/30 bg-primary-soft/30 p-0" : "p-0"}>
              <CardContent className="flex items-start gap-3 p-4">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-muted text-foreground">
                  <meta.icon className="size-[18px]" aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium">{n.title}</p>
                    <StatusChip tone={meta.tone}>{meta.label}</StatusChip>
                  </div>
                  <p className="mt-0.5 text-sm text-muted-foreground">{n.body}</p>
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">{n.time}</span>
              </CardContent>
            </Card>
          );
        })}
      </div>
    );

  return (
    <div className="mx-auto max-w-[900px]">
      <PageHeader
        title="Notifications"
        description={`${unread.length} unread of ${items.length} events.`}
        crumbs={[{ label: "Home", to: "/" }, { label: "Notifications" }]}
        actions={
          <Button variant="outline" onClick={() => setItems((v) => v.map((n) => ({ ...n, unread: false })))}>
            <Bell className="size-4" aria-hidden="true" /> Mark all as read
          </Button>
        }
      />

      <Tabs defaultValue="all">
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="unread">Unread</TabsTrigger>
          <TabsTrigger value="system">System</TabsTrigger>
        </TabsList>
        <TabsContent value="all" className="pt-4">
          {list(items)}
        </TabsContent>
        <TabsContent value="unread" className="pt-4">
          {list(unread)}
        </TabsContent>
        <TabsContent value="system" className="pt-4">
          {list(items.filter((n) => n.type === "system"))}
        </TabsContent>
      </Tabs>
    </div>
  );
}
