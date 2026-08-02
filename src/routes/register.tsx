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

function RegisterPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

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
          await authService.register({
            name: String(form.get("name") ?? ""),
            email: String(form.get("email") ?? ""),
            password: String(form.get("password") ?? ""),
          });
          setLoading(false);
          toast.success("Account created", { description: "TODO: wire Supabase signUp" });
          navigate({ to: "/" });
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
          <Input id="r-hospital" placeholder="Northfield Oncology Center" required />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="r-spec">Specialization</Label>
          <Input id="r-spec" placeholder="Breast oncology" required />
        </div>
        <div className="grid gap-2 sm:col-span-2">
          <Label htmlFor="r-role">Role</Label>
          <Select defaultValue="oncologist">
            <SelectTrigger id="r-role">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="doctor">Doctor</SelectItem>
              <SelectItem value="oncologist">Oncologist</SelectItem>
              <SelectItem value="researcher">Medical researcher</SelectItem>
              <SelectItem value="admin">Hospital administrator</SelectItem>
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
