import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Building2, Mail, Phone, ShieldCheck, Stethoscope } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { userService } from "@/services";
import { ApiError } from "@/services/api-client";
import { doctor } from "@/services/data";

export const Route = createFileRoute("/_shell/profile")({
  head: () => ({
    meta: [
      { title: "Doctor Profile — OncoTwin" },
      {
        name: "description",
        content: "Manage your clinician profile, hospital details, specialization and password.",
      },
      { property: "og:title", content: "Doctor Profile — OncoTwin" },
      {
        property: "og:description",
        content: "Manage your clinician profile, hospital details, specialization and password.",
      },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(ProfilePage, { variant: "detail" }),
});

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return (
    parts
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase() ?? "")
      .join("") || "?"
  );
}

function ProfilePage() {
  const { user, setUser } = useAuth();
  // `phone` and `experience` are not part of Module 1's profile contract
  // (AuthUser / PATCH /users/profile only cover name, title, hospital,
  // department, avatarUrl) — they remain fixture-backed display fields
  // rather than silently accepting edits that wouldn't actually persist.
  // A future Doctor-directory module is the natural home for them.
  const displayName = user?.name ?? doctor.name;
  const displayEmail = user?.email ?? doctor.email;
  const displayHospital = user?.hospital ?? doctor.hospital;
  const displaySpecialization = user?.title ?? doctor.specialization;

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
                {initialsOf(displayName)}
              </AvatarFallback>
            </Avatar>
            <h2 className="mt-4 text-lg font-semibold">{displayName}</h2>
            <p className="text-sm text-muted-foreground capitalize">{user?.role ?? doctor.role}</p>
            <StatusChip tone="success" dot className="mt-3">
              Verified clinician
            </StatusChip>

            <dl className="mt-6 w-full space-y-3 text-left text-sm">
              {[
                { icon: Building2, label: displayHospital },
                { icon: Stethoscope, label: displaySpecialization },
                { icon: Mail, label: displayEmail },
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
                onSubmit={async (e) => {
                  e.preventDefault();
                  const form = new FormData(e.currentTarget);
                  try {
                    const updated = await userService.updateProfile({
                      name: String(form.get("name") ?? ""),
                      hospital: String(form.get("hospital") ?? ""),
                      department: String(form.get("department") ?? ""),
                      // "Specialization" in this UI maps to the profile's
                      // `title` field (e.g. "Chief Oncologist") — the same
                      // field TopBar/AuthUser already display.
                      title: String(form.get("specialization") ?? ""),
                    });
                    setUser(updated);
                    toast.success("Profile updated");
                  } catch (err) {
                    toast.error(
                      err instanceof ApiError ? err.message : "Unable to update your profile.",
                    );
                  }
                }}
              >
                <div className="grid gap-2">
                  <Label htmlFor="pf-name">Doctor name</Label>
                  <Input id="pf-name" name="name" defaultValue={displayName} />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pf-email">Email</Label>
                  {/* Email changes go through Supabase's own re-verification
                      flow, not this endpoint — read-only here on purpose. */}
                  <Input id="pf-email" type="email" defaultValue={displayEmail} disabled />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pf-hospital">Hospital</Label>
                  <Input id="pf-hospital" name="hospital" defaultValue={displayHospital} />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pf-dept">Department</Label>
                  <Input id="pf-dept" name="department" defaultValue={doctor.department} />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pf-spec">Specialization</Label>
                  <Input id="pf-spec" name="specialization" defaultValue={displaySpecialization} />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="pf-phone">Phone</Label>
                  <Input id="pf-phone" defaultValue={doctor.phone} disabled />
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
              <CardDescription>
                Use at least 12 characters with a mix of letters and numbers.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form
                className="grid gap-4 sm:grid-cols-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  // Password changes for an already-authenticated user go
                  // through Supabase's `updateUser({ password })` directly
                  // from the client (the same mechanism the reset-password
                  // page uses for a *logged-out* recovery session) — out of
                  // Module 1's REST-endpoint scope (only the 8 listed
                  // endpoints were implemented), tracked as a follow-up.
                  toast.info("Password changes are coming in a follow-up release.");
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
