import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { MailCheck } from "lucide-react";

import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authService } from "@/services";

export const Route = createFileRoute("/forgot-password")({
  head: () => ({
    meta: [
      { title: "Reset your password — OncoTwin" },
      { name: "description", content: "Request a secure password reset link for your OncoTwin clinician account." },
      { property: "og:title", content: "Reset your password — OncoTwin" },
      { property: "og:description", content: "Request a secure password reset link for your OncoTwin clinician account." },
    ],
  }),
  component: ForgotPasswordPage,
});

function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  return (
    <AuthLayout
      title="Forgot your password?"
      subtitle="We'll email you a secure link to set a new one."
      footer={
        <Link to="/login" className="font-medium text-primary underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      }
    >
      {sent ? (
        <div className="rounded-xl border border-success/30 bg-success-soft/60 p-5 text-center">
          <MailCheck className="mx-auto size-8 text-success" aria-hidden="true" />
          <p className="mt-3 text-sm font-medium">Reset link sent</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Check your inbox and follow the link to choose a new password.
          </p>
          <Button variant="outline" className="mt-4" asChild>
            <Link to="/reset-password">Open reset form</Link>
          </Button>
        </div>
      ) : (
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setLoading(true);
            await authService.forgotPassword("demo");
            setLoading(false);
            setSent(true);
          }}
        >
          <div className="grid gap-2">
            <Label htmlFor="fp-email">Work email</Label>
            <Input id="fp-email" type="email" autoComplete="email" placeholder="name@hospital.health" required />
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Sending link…" : "Send reset link"}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
