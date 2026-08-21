import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";

import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { authService } from "@/services";

export const Route = createFileRoute("/register")({
  head: () => ({
    meta: [
      { title: "Create account — OncoTwin Clinical Platform" },
      { name: "description", content: "Register as an oncologist, researcher or administrator on the OncoTwin platform." },
      { property: "og:title", content: "Create account — OncoTwin Clinical Platform" },
      { property: "og:description", content: "Register as an oncologist, researcher or administrator on the OncoTwin platform." },
    ],
  }),
  component: RegisterPage,
});

const ROLE_OPTIONS = [
  { value: "doctor", label: "Doctor" },
  { value: "researcher", label: "Medical researcher" },
  { value: "admin", label: "Hospital administrator" },
] as const;

import { useAuth } from "@/components/auth/AuthProvider";

function RegisterPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [loading, setLoading] = useState(false);
  const [role, setRole] = useState<(typeof ROLE_OPTIONS)[number]["value"]>("doctor");

  return (
    <AuthLayout
      title="Create your clinician account"
      subtitle="Requests are verified against your hospital directory."
      footer={
        <>
          Already registered?{" "}
          <Link to="/login" className="font-medium text-primary underline-offset-4 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={async (e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          setLoading(true);
          const email = String(form.get("email") ?? "");
          const password = String(form.get("password") ?? "");
          try {
            await authService.register({
              name: String(form.get("name") ?? ""),
              email,
              password,
              role,
              hospital: String(form.get("hospital") ?? "") || undefined,
              specialization: String(form.get("specialization") ?? "") || undefined,
            });
            const session = await login({ email, password });
            setLoading(false);
            toast.success("Account created and signed in");
            if (session.user.role === "patient") {
              navigate({ to: "/portal" });
            } else {
              navigate({ to: "/" });
            }
          } catch (err: any) {
            setLoading(false);
            toast.error(err?.message || "Failed to create account");
          }
        }}
      >
        <div className="grid gap-2 sm:col-span-2">
          <Label htmlFor="r-name">Doctor name</Label>
          <Input id="r-name" name="name" placeholder="Dr. Sarah Whitmore" autoComplete="name" required />
        </div>
        <div className="grid gap-2 sm:col-span-2">
          <Label htmlFor="r-email">Work email</Label>
          <Input id="r-email" name="email" type="email" autoComplete="email" placeholder="name@hospital.health" required />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="r-hospital">Hospital</Label>
          <Input id="r-hospital" name="hospital" placeholder="Northfield Oncology Center" required />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="r-spec">Specialization</Label>
          <Input id="r-spec" name="specialization" placeholder="Breast oncology" required />
        </div>
        <div className="grid gap-2 sm:col-span-2">
          <Label htmlFor="r-role">Role</Label>
          <Select value={role} onValueChange={(value) => setRole(value as typeof role)}>
            <SelectTrigger id="r-role">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ROLE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-2 sm:col-span-2">
          <Label htmlFor="r-password">Password</Label>
          <Input id="r-password" name="password" type="password" autoComplete="new-password" placeholder="••••••••" required />
        </div>
        <div className="flex items-start gap-2 sm:col-span-2">
          <Checkbox id="r-terms" className="mt-0.5" required />
          <Label htmlFor="r-terms" className="text-sm font-normal text-muted-foreground">
            I confirm I am a licensed healthcare professional and accept the data processing terms.
          </Label>
        </div>
        <div className="sm:col-span-2">
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Creating account…" : "Create account"}
          </Button>
        </div>
      </form>
    </AuthLayout>
  );
}
