import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { z } from "zod";

import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authService } from "@/services";
import { ApiError } from "@/services/api-client";

// Supabase's password-recovery email links to this page with the recovery
// session's access_token as a query/hash param (`?token=...` here — the
// exact param name depends on how PASSWORD_RESET_REDIRECT_URL is
// configured on the backend, see backend/.env.example). We read it once on
// load rather than expecting the user to type it into a form field, which
// is what this page did before (a `token` field that was never rendered,
// so every reset silently failed).
const searchSchema = z.object({ token: z.string().optional() });

export const Route = createFileRoute("/reset-password")({
  validateSearch: searchSchema,
  head: () => ({
    meta: [
      { title: "Set a new password — OncoTwin" },
      {
        name: "description",
        content: "Choose a new password for your OncoTwin clinician account.",
      },
      { property: "og:title", content: "Set a new password — OncoTwin" },
      {
        property: "og:description",
        content: "Choose a new password for your OncoTwin clinician account.",
      },
    ],
  }),
  component: ResetPasswordPage,
});

function ResetPasswordPage() {
  const navigate = useNavigate();
  const { token } = Route.useSearch();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      {!token && (
        <p role="alert" className="mb-4 text-sm text-destructive">
          This reset link is missing or invalid. Request a new one from the sign-in page.
        </p>
      )}
      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          const password = String(form.get("password") ?? "");
          const confirm = String(form.get("confirm") ?? "");
          if (password !== confirm) {
            setError("Passwords do not match.");
            return;
          }
          setLoading(true);
          setError(null);
          try {
            await authService.resetPassword({ token: token ?? "", password });
            toast.success("Password updated");
            navigate({ to: "/login" });
          } catch (err) {
            const message =
              err instanceof ApiError
                ? err.message
                : "Unable to update password. Request a new reset link.";
            setError(message);
          } finally {
            setLoading(false);
          }
        }}
      >
        <div className="grid gap-2">
          <Label htmlFor="rp-password">New password</Label>
          <Input
            id="rp-password"
            name="password"
            type="password"
            autoComplete="new-password"
            placeholder="••••••••"
            required
            minLength={8}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="rp-confirm">Confirm new password</Label>
          <Input
            id="rp-confirm"
            name="confirm"
            type="password"
            autoComplete="new-password"
            placeholder="••••••••"
            required
            minLength={8}
          />
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={loading || !token}>
          {loading ? "Updating…" : "Update password"}
        </Button>
      </form>
    </AuthLayout>
  );
}
