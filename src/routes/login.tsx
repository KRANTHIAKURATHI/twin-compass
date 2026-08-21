import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/AuthProvider";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — OncoTwin Clinical Platform" },
      { name: "description", content: "Sign in to the OncoTwin clinical decision support platform for oncologists." },
      { property: "og:title", content: "Sign in — OncoTwin Clinical Platform" },
      { property: "og:description", content: "Sign in to the OncoTwin clinical decision support platform for oncologists." },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [loading, setLoading] = useState(false);

  return (
    <AuthLayout
      title="Sign in to your workspace"
      subtitle="Access your patients, digital twins and predictions."
      footer={
        <>
          New to OncoTwin?{" "}
          <Link to="/register" className="font-medium text-primary underline-offset-4 hover:underline">
            Create an account
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
          try {
            const session = await login({
              email: String(form.get("email") ?? ""),
              password: String(form.get("password") ?? ""),
            });
            setLoading(false);
            toast.success("Signed in");
            if (session.user.role === "patient") {
              navigate({ to: "/portal" });
            } else if (session.user.role === "researcher") {
              navigate({ to: "/research" });
            } else {
              navigate({ to: "/" });
            }
          } catch (err: any) {
            setLoading(false);
            toast.error(err?.message || "Invalid email or password");
          }
        }}
      >
        <div className="grid gap-2">
          <Label htmlFor="email">Work email</Label>
          <Input id="email" name="email" type="email" autoComplete="email" placeholder="s.whitmore@hospital.health" required />
        </div>
        <div className="grid gap-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link to="/forgot-password" className="text-xs text-primary underline-offset-4 hover:underline">
              Forgot password?
            </Link>
          </div>
          <Input id="password" name="password" type="password" autoComplete="current-password" placeholder="••••••••" required />
        </div>
        <div className="flex items-center gap-2">
          <Checkbox id="remember" defaultChecked />
          <Label htmlFor="remember" className="text-sm font-normal text-muted-foreground">
            Remember me on this device
          </Label>
        </div>
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </AuthLayout>
  );
}
