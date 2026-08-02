import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";

import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authService } from "@/services";

export const Route = createFileRoute("/reset-password")({
  head: () => ({
    meta: [
      { title: "Set a new password — OncoTwin" },
      { name: "description", content: "Choose a new password for your OncoTwin clinician account." },
      { property: "og:title", content: "Set a new password — OncoTwin" },
      { property: "og:description", content: "Choose a new password for your OncoTwin clinician account." },
    ],
  }),
  component: ResetPasswordPage,
});

function ResetPasswordPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  return (
    <AuthLayout
      title="Set a new password"
      subtitle="Use at least 12 characters with letters, numbers and a symbol."
      footer={
        <Link to="/login" className="font-medium text-primary underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      }
    >
      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          setLoading(true);
          await authService.resetPassword({
            token: String(form.get("token") ?? ""),
            password: String(form.get("password") ?? ""),
          });
          setLoading(false);
          toast.success("Password updated", { description: "TODO: wire Supabase updateUser" });
          navigate({ to: "/login" });
        }}
      >
        <div className="grid gap-2">
          <Label htmlFor="rp-password">New password</Label>
          <Input id="rp-password" name="password" type="password" autoComplete="new-password" placeholder="••••••••" required />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="rp-confirm">Confirm new password</Label>
          <Input id="rp-confirm" type="password" autoComplete="new-password" placeholder="••••••••" required />
        </div>
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Updating…" : "Update password"}
        </Button>
      </form>
    </AuthLayout>
  );
}
