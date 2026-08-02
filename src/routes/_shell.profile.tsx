import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Building2, Mail, Phone, ShieldCheck, Stethoscope } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { doctor } from "@/services/data";

export const Route = createFileRoute("/_shell/profile")({
  head: () => ({
    meta: [
      { title: "Doctor Profile — OncoTwin" },
      { name: "description", content: "Manage your clinician profile, hospital details, specialization and password." },
      { property: "og:title", content: "Doctor Profile — OncoTwin" },
      { property: "og:description", content: "Manage your clinician profile, hospital details, specialization and password." },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(ProfilePage, { variant: "detail" }),
});

function ProfilePage() {
  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader
        title="Profile"
        description="Your clinician identity across the platform."
        crumbs={[{ label: "Home", to: "/" }, { label: "Profile" }]}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="h-fit">
          <CardContent className="flex flex-col items-center pt-2 text-center">
            <Avatar className="size-24">
              <AvatarFallback className="bg-primary-soft text-2xl font-semibold text-primary">
                {doctor.initials}
              </AvatarFallback>
            </Avatar>
            <h2 className="mt-4 text-lg font-semibold">{doctor.name}</h2>
            <p className="text-sm text-muted-foreground">{doctor.role}</p>
            <StatusChip tone="success" dot className="mt-3">
              Verified clinician
            </StatusChip>

            <dl className="mt-6 w-full space-y-3 text-left text-sm">
              {[
                { icon: Building2, label: doctor.hospital },
                { icon: Stethoscope, label: doctor.specialization },
                { icon: Mail, label: doctor.email },
                { icon: Phone, label: doctor.phone },
                { icon: ShieldCheck, label: `${doctor.experience} experience` },
              ].map((row) => (
                <div key={row.label} className="flex items-start gap-2.5">
                  <row.icon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                  <span className="text-muted-foreground">{row.label}</span>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>

        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Edit profile</CardTitle>
              <CardDescription>Changes sync to your hospital directory.</CardDescription>
            </CardHeader>
            <CardContent>
              <form
                className="grid gap-4 sm:grid-cols-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  toast.success("Profile updated", { description: "TODO: wire PATCH /api/me" });
                }}
              >
                <div className="grid gap-2">
                  <Label htmlFor="pf-name">Doctor name</Label>
                  <Input id="pf-name" defaultValue={doctor.name} />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pf-email">Email</Label>
                  <Input id="pf-email" type="email" defaultValue={doctor.email} />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pf-hospital">Hospital</Label>
                  <Input id="pf-hospital" defaultValue={doctor.hospital} />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pf-dept">Department</Label>
                  <Input id="pf-dept" defaultValue={doctor.department} />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pf-spec">Specialization</Label>
                  <Input id="pf-spec" defaultValue={doctor.specialization} />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pf-phone">Phone</Label>
                  <Input id="pf-phone" defaultValue={doctor.phone} />
                </div>
                <div className="sm:col-span-2">
                  <Button type="submit">Save changes</Button>
                </div>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Change password</CardTitle>
              <CardDescription>Use at least 12 characters with a mix of letters and numbers.</CardDescription>
            </CardHeader>
            <CardContent>
              <form
                className="grid gap-4 sm:grid-cols-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  toast.success("Password updated", { description: "TODO: wire Supabase updateUser" });
                }}
              >
                <div className="grid gap-2">
                  <Label htmlFor="pw-current">Current password</Label>
                  <Input id="pw-current" type="password" autoComplete="current-password" />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pw-new">New password</Label>
                  <Input id="pw-new" type="password" autoComplete="new-password" />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pw-confirm">Confirm password</Label>
                  <Input id="pw-confirm" type="password" autoComplete="new-password" />
                </div>
                <div className="sm:col-span-3">
                  <Button type="submit" variant="outline">
                    Update password
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
