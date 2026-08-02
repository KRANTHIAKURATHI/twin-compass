import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";

import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authService } from "@/services";

export const Route = createFileRoute("/patient-login")({
  head: () => ({
    meta: [
      { title: "Patient Sign in — OncoTwin Portal" },
      { name: "description", content: "Sign in to view your reports, treatment plan and appointments." },
      { property: "og:title", content: "Patient Sign in — OncoTwin Portal" },
      { property: "og:description", content: "Sign in to view your reports, treatment plan and appointments." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: PatientLogin,
});

function PatientLogin() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  return (
    <AuthLayout
      title="Patient sign in"
      subtitle="Access your reports, treatment plan and appointments."
      footer={
        <>
          Are you a clinician?{" "}
          <Link to="/login" className="font-medium text-primary underline-offset-4 hover:underline">
            Use the doctor portal
          </Link>
        </>
      }
    >
      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          setLoading(true);
          await authService.login({
            email: String(form.get("email") ?? ""),
            password: String(form.get("password") ?? ""),
          });
          setLoading(false);
          toast.success("Signed in", { description: "TODO: wire patient auth" });
          navigate({ to: "/portal" });
        }}
      >
        <div className="grid gap-2">
          <Label htmlFor="pemail">Email</Label>
          <Input id="pemail" name="email" type="email" autoComplete="email" placeholder="amelia.hart@mail.health" required />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="ppassword">Password</Label>
          <Input id="ppassword" name="password" type="password" autoComplete="current-password" placeholder="••••••••" required />
        </div>
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          Trouble signing in?{" "}
          <Link to="/forgot-password" className="text-primary underline-offset-4 hover:underline">
            Reset your password
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}
