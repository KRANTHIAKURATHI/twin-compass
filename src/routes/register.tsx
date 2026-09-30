import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";

import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { authService } from "@/services";
import { ApiError } from "@/services/api-client";

export const Route = createFileRoute("/register")({
  head: () => ({
    meta: [
      { title: "Create account — OncoTwin Clinical Platform" },
      {
        name: "description",
        content: "Register as an oncologist, researcher or administrator on the OncoTwin platform.",
      },
      { property: "og:title", content: "Create account — OncoTwin Clinical Platform" },
      {
        property: "og:description",
        content: "Register as an oncologist, researcher or administrator on the OncoTwin platform.",
      },
    ],
  }),
  component: RegisterPage,
});

function RegisterPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The Select's own value stays distinct per option (Radix requires unique
  // values); only the value actually sent to the API is normalized, via
  // `roleForSubmit` below — no visible option/label changes.
  const [selectedRole, setSelectedRole] = useState("doctor");

  // The Select's own value stays distinct per option (Radix requires unique
  // values); "oncologist" is a friendlier label for the same "doctor"
  // permission set and is normalized here. "admin" is sent through
  // unmodified on purpose — the backend rejects it with a clear message
  // (surfaced below), which is more honest than silently downgrading a
  // genuine admin registration attempt to a doctor account.
  const roleForSubmit = (value: string): "doctor" | "patient" | "researcher" | "admin" =>
    value === "oncologist" ? "doctor" : (value as "doctor" | "researcher" | "admin");

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
          setError(null);
          try {
            const result = await authService.register({
              name: String(form.get("name") ?? ""),
              email: String(form.get("email") ?? ""),
              password: String(form.get("password") ?? ""),
              // @ts-expect-error — role/hospital/title are accepted by the
              // backend's RegisterRequest but not yet part of the narrower
              // shared Credentials & { name } contract type; widening that
              // type is a follow-up, not a UI change.
              role: roleForSubmit(selectedRole),
              hospital: String(form.get("hospital") ?? ""),
              title: String(form.get("specialization") ?? ""),
            });
            if (!result.ok) {
              setError(result.message ?? "Unable to create your account.");
              return;
            }
            toast.success("Account created", {
              description: result.message ?? "Check your email to verify your address.",
            });
            navigate({ to: "/login" });
          } catch (err) {
            const message =
              err instanceof ApiError
                ? err.message
                : "Unable to create your account. Please try again.";
            setError(message);
          } finally {
            setLoading(false);
          }
        }}
      >
        <div className="grid gap-2 sm:col-span-2">
          <Label htmlFor="r-name">Doctor name</Label>
          <Input
            id="r-name"
            name="name"
            placeholder="Dr. Sarah Whitmore"
            autoComplete="name"
            required
          />
        </div>
        <div className="grid gap-2 sm:col-span-2">
          <Label htmlFor="r-email">Work email</Label>
          <Input
            id="r-email"
            name="email"
            type="email"
            autoComplete="email"
            placeholder="name@hospital.health"
            required
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="r-hospital">Hospital</Label>
          <Input
            id="r-hospital"
            name="hospital"
            placeholder="Northfield Oncology Center"
            required
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="r-spec">Specialization</Label>
          <Input id="r-spec" name="specialization" placeholder="Breast oncology" required />
        </div>
        <div className="grid gap-2 sm:col-span-2">
          <Label htmlFor="r-role">Role</Label>
          <Select value={selectedRole} onValueChange={setSelectedRole}>
            <SelectTrigger id="r-role">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {/* "Oncologist" maps to the backend's "doctor" role — same
                  clinician permission set, friendlier label (see
                  roleForSubmit above). "Hospital administrator" is
                  intentionally left selectable: the backend rejects
                  self-registered admin accounts (an existing admin must
                  grant that role after account creation), and the resulting
                  error is surfaced below rather than hidden by removing the
                  option, which would be a UI change. */}
              <SelectItem value="doctor">Doctor</SelectItem>
              <SelectItem value="oncologist">Oncologist</SelectItem>
              <SelectItem value="researcher">Medical researcher</SelectItem>
              <SelectItem value="admin">Hospital administrator</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-2 sm:col-span-2">
          <Label htmlFor="r-password">Password</Label>
          <Input
            id="r-password"
            name="password"
            type="password"
            autoComplete="new-password"
            placeholder="••••••••"
            required
            minLength={8}
          />
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive sm:col-span-2">
            {error}
          </p>
        )}
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
