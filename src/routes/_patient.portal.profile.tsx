import { useEffect, useState, type FormEvent } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { PageErrorState, PageSkeleton, RouteErrorState } from "@/components/common/PageState";
import { Mail, Phone, ShieldCheck } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useMe, usePatients, useUpdateProfile } from "@/hooks/api";

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
  component: PatientProfilePage,
});

function PatientProfilePage() {
  const meQuery = useMe();
  const patientsQuery = usePatients();
  const updateProfile = useUpdateProfile();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");

  const authUser = meQuery.data;
  const patient = patientsQuery.data?.[0];

  useEffect(() => {
    if (authUser) setName(authUser.name);
  }, [authUser]);
  useEffect(() => {
    if (patient) {
      setEmail(patient.email);
      setPhone(patient.phone);
    }
  }, [patient]);

  if (meQuery.isLoading || patientsQuery.isLoading) return <PageSkeleton variant="detail" />;
  if (meQuery.isError || !authUser) {
    return (
      <div className="mx-auto max-w-[900px] pt-4">
        <PageErrorState onRetry={() => meQuery.refetch()} />
      </div>
    );
  }

  const handleSave = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    updateProfile.mutate({ name });
  };

  return (
    <form onSubmit={handleSave} className="mx-auto max-w-[900px]">
      <PageHeader
        title="My Profile"
        description="Keep your details up to date so your care team can reach you."
        actions={
          <Button type="submit" disabled={updateProfile.isPending}>
            {updateProfile.isPending ? "Saving…" : "Save changes"}
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="h-fit text-center">
          <CardContent className="pt-2">
            <span className="mx-auto flex size-20 items-center justify-center rounded-full bg-primary-soft font-display text-2xl font-semibold text-primary">
              {authUser.name
                .split(" ")
                .map((p) => p[0])
                .slice(0, 2)
                .join("")
                .toUpperCase()}
            </span>
            <p className="mt-3 text-base font-semibold">{authUser.name}</p>
            {patient && (
              <>
                <p className="text-xs text-muted-foreground">
                  {patient.id} · {patient.age} years
                </p>
                <StatusChip tone="primary" className="mt-3">
                  Stage {patient.stage}
                </StatusChip>
              </>
            )}
            <p className="mt-4 flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
              <ShieldCheck className="size-3.5 text-success" aria-hidden="true" /> Identity verified
            </p>
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
                <Input id="p-name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="p-email">Email</Label>
                <Input id="p-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} disabled />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="p-phone">Phone</Label>
                <Input id="p-phone" value={phone} onChange={(e) => setPhone(e.target.value)} disabled />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="p-emergency">Emergency contact</Label>
                <Input id="p-emergency" defaultValue="Daniel Hart · +1 (415) 555-0177" disabled />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Privacy & communication</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {[
                { id: "share", label: "Share my data with research programmes", desc: "De-identified data only", icon: ShieldCheck, on: false },
                { id: "email", label: "Email notifications", desc: "Reports, results and reminders", icon: Mail, on: true },
                { id: "sms", label: "SMS appointment reminders", desc: "24 hours before each visit", icon: Phone, on: true },
              ].map((row) => (
                <div key={row.id} className="flex items-center justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <row.icon className="mt-0.5 size-4 text-primary" aria-hidden="true" />
                    <div>
                      <Label htmlFor={row.id} className="text-sm">
                        {row.label}
                      </Label>
                      <p className="text-xs text-muted-foreground">{row.desc}</p>
                    </div>
                  </div>
                  <Switch id={row.id} defaultChecked={row.on} />
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </form>
  );
}
