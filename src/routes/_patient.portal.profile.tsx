import { createFileRoute } from "@tanstack/react-router";
import { PageErrorState, PageSkeleton, RouteErrorState, withPageStates } from "@/components/common/PageState";
import { User } from "lucide-react";

import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { usePatients } from "@/hooks/api";

export const Route = createFileRoute("/_patient/portal/profile")({
  head: () => ({
    meta: [
      { title: "My Profile — OncoTwin Patient Portal" },
      { name: "description", content: "Manage your contact details, emergency contact and privacy preferences." },
      { property: "og:title", content: "My Profile — OncoTwin Patient Portal" },
      { property: "og:description", content: "Manage your contact details, emergency contact and privacy preferences." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(PatientProfilePage, { variant: "detail" }),
});

const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");

function PatientProfilePage() {
  const { data, isLoading, isError, refetch } = usePatients();
  const me = data?.[0];
  const header = <PageHeader title="My Profile" description="The details your care team has on record for you." />;

  if (isLoading) return <div className="mx-auto max-w-[900px]">{header}<PageSkeleton variant="list" /></div>;
  if (isError)
    return (
      <div className="mx-auto max-w-[900px]">
        {header}
        <PageErrorState onRetry={() => void refetch()} />
      </div>
    );
  if (!me)
    return (
      <div className="mx-auto max-w-[900px]">
        {header}
        <EmptyState icon={User} title="No patient record found" description="No patient record is linked to your account yet." />
      </div>
    );

  // Read-only: there is no endpoint for a patient to edit their own record, so no save action is offered.
  return (
    <div className="mx-auto max-w-[900px]">
      {header}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="h-fit text-center">
          <CardContent className="pt-2">
            <span className="mx-auto flex size-20 items-center justify-center rounded-full bg-primary-soft font-display text-2xl font-semibold text-primary">
              {initials(me.name)}
            </span>
            <p className="mt-3 text-base font-semibold">{me.name}</p>
            <p className="text-xs text-muted-foreground">
              {me.id}
              {me.age == null ? "" : ` · ${me.age} years`}
            </p>
            {me.stage && (
              <StatusChip tone="primary" className="mt-3">
                Stage {me.stage}
              </StatusChip>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Contact details</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="p-name">Full name</Label>
                <Input id="p-name" value={me.name} readOnly />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="p-email">Email</Label>
                <Input id="p-email" type="email" value={me.email ?? ""} placeholder="Not recorded" readOnly />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="p-phone">Phone</Label>
                <Input id="p-phone" value={me.phone ?? ""} placeholder="Not recorded" readOnly />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="p-hospital">Hospital</Label>
                <Input id="p-hospital" value={me.hospital ?? ""} placeholder="Not recorded" readOnly />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
