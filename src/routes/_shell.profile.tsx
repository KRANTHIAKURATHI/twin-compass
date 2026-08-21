import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Building2, Mail } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useChangePassword, useMe, useUpdateProfile } from "@/hooks/api";

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
  const { data: me } = useMe();
  const updateProfile = useUpdateProfile();
  const changePassword = useChangePassword();

  const displayName = me?.name ?? "";
  const displayEmail = me?.email ?? "";
  const displayRole = me?.role ?? "";
  const displayHospital = me?.hospital ?? "";
  const initials =
    displayName
      .split(" ")
      .map((part) => part[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || "DR";

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
                {initials}
              </AvatarFallback>
            </Avatar>
            <h2 className="mt-4 text-lg font-semibold">{displayName}</h2>
            <p className="text-sm text-muted-foreground">{displayRole}</p>
            <StatusChip tone="success" dot className="mt-3">
              Verified clinician
            </StatusChip>

            <dl className="mt-6 w-full space-y-3 text-left text-sm">
              {[
                { icon: Building2, label: displayHospital },
                { icon: Mail, label: displayEmail },
              ]
                .filter((row) => row.label)
                .map((row, i) => (
                  <div key={i} className="flex items-start gap-2.5">
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
                  const form = e.currentTarget;
                  const name = (form.elements.namedItem("pf-name") as HTMLInputElement).value;
                  const hospital = (form.elements.namedItem("pf-hospital") as HTMLInputElement).value;
                  updateProfile.mutate({ name, hospital });
                }}
              >
                <div className="grid gap-2">
                  <Label htmlFor="pf-name">Doctor name</Label>
                  <Input id="pf-name" name="pf-name" defaultValue={displayName} />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pf-email">Email</Label>
                  <Input id="pf-email" name="pf-email" type="email" defaultValue={displayEmail} disabled />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pf-hospital">Hospital</Label>
                  <Input id="pf-hospital" name="pf-hospital" defaultValue={displayHospital} />
                </div>
                <div className="sm:col-span-2">
                  <Button type="submit" disabled={updateProfile.isPending}>
                    Save changes
                  </Button>
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
                  const form = e.currentTarget;
                  const currentPassword = (form.elements.namedItem("pw-current") as HTMLInputElement).value;
                  const newPassword = (form.elements.namedItem("pw-new") as HTMLInputElement).value;
                  const confirmPassword = (form.elements.namedItem("pw-confirm") as HTMLInputElement).value;
                  if (newPassword !== confirmPassword) {
                    toast.error("Passwords do not match", { description: "New password and confirmation must match." });
                    return;
                  }
                  changePassword.mutate(
                    { currentPassword, newPassword },
                    { onSuccess: () => form.reset() },
                  );
                }}
              >
                <div className="grid gap-2">
                  <Label htmlFor="pw-current">Current password</Label>
                  <Input id="pw-current" name="pw-current" type="password" autoComplete="current-password" />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pw-new">New password</Label>
                  <Input id="pw-new" name="pw-new" type="password" autoComplete="new-password" />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pw-confirm">Confirm password</Label>
                  <Input id="pw-confirm" name="pw-confirm" type="password" autoComplete="new-password" />
                </div>
                <div className="sm:col-span-3">
                  <Button type="submit" variant="outline" disabled={changePassword.isPending}>
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
