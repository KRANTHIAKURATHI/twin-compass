import { createFileRoute } from "@tanstack/react-router";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export const Route = createFileRoute("/_shell/settings")({
  head: () => ({
    meta: [
      { title: "Settings — OncoTwin" },
      { name: "description", content: "General, appearance, notification, security, language, privacy and API settings." },
      { property: "og:title", content: "Settings — OncoTwin" },
      { property: "og:description", content: "General, appearance, notification, security, language, privacy and API settings." },
    ],
  }),
  component: SettingsPage,
});

function Row({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-6 py-4">
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {children}
    </div>
  );
}

function SettingsPage() {
  const saved = () => toast.success("Setting saved", { description: "TODO: persist via /api/settings" });

  return (
    <div className="mx-auto max-w-[1000px]">
      <PageHeader
        title="Settings"
        description="Configure the workspace, alerts and clinical data handling."
        crumbs={[{ label: "Home", to: "/" }, { label: "Settings" }]}
      />

      <Tabs defaultValue="general">
        <TabsList className="flex-wrap">
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="appearance">Appearance</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="privacy">Privacy</TabsTrigger>
          <TabsTrigger value="api">API</TabsTrigger>
        </TabsList>

        <TabsContent value="general" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>General</CardTitle>
              <CardDescription>Workspace defaults for your department.</CardDescription>
            </CardHeader>
            <CardContent className="divide-y divide-border">
              <Row title="Default landing page" description="Where you start after signing in.">
                <Select defaultValue="dashboard">
                  <SelectTrigger className="w-44" aria-label="Default landing page">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="dashboard">Dashboard</SelectItem>
                    <SelectItem value="patients">Patients</SelectItem>
                    <SelectItem value="twins">Digital Twins</SelectItem>
                  </SelectContent>
                </Select>
              </Row>
              <Row title="Language" description="Interface language for your account.">
                <Select defaultValue="en">
                  <SelectTrigger className="w-44" aria-label="Language">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English (US)</SelectItem>
                    <SelectItem value="de">Deutsch</SelectItem>
                    <SelectItem value="fr">Français</SelectItem>
                    <SelectItem value="ar">العربية</SelectItem>
                  </SelectContent>
                </Select>
              </Row>
              <Row title="Measurement units" description="Tumor size and lab value formatting.">
                <Select defaultValue="metric">
                  <SelectTrigger className="w-44" aria-label="Units">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="metric">Metric (mm)</SelectItem>
                    <SelectItem value="imperial">Imperial (in)</SelectItem>
                  </SelectContent>
                </Select>
              </Row>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="appearance" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Appearance</CardTitle>
              <CardDescription>Visual density and motion preferences.</CardDescription>
            </CardHeader>
            <CardContent className="divide-y divide-border">
              <Row title="Compact tables" description="Reduce row height in patient tables.">
                <Switch onCheckedChange={saved} aria-label="Compact tables" />
              </Row>
              <Row title="Reduced motion" description="Minimise animations across the app.">
                <Switch onCheckedChange={saved} aria-label="Reduced motion" />
              </Row>
              <Row title="High contrast charts" description="Stronger colour separation for clinical displays.">
                <Switch defaultChecked onCheckedChange={saved} aria-label="High contrast charts" />
              </Row>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Notifications</CardTitle>
              <CardDescription>Choose which clinical events reach you.</CardDescription>
            </CardHeader>
            <CardContent className="divide-y divide-border">
              {[
                ["New patient assigned", "Email + in-app when a patient is assigned to you."],
                ["Prediction completed", "When a model run finishes for your patients."],
                ["High-risk threshold crossed", "Immediate alert for risk escalation."],
                ["Weekly cohort digest", "Summary of your cohort every Monday."],
              ].map(([t, d]) => (
                <Row key={t} title={t} description={d}>
                  <Switch defaultChecked onCheckedChange={saved} aria-label={t} />
                </Row>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Security</CardTitle>
              <CardDescription>Protect access to patient data.</CardDescription>
            </CardHeader>
            <CardContent className="divide-y divide-border">
              <Row title="Two-factor authentication" description="Require an authenticator code at sign-in.">
                <Switch defaultChecked onCheckedChange={saved} aria-label="Two-factor authentication" />
              </Row>
              <Row title="Session timeout" description="Automatically sign out after inactivity.">
                <Select defaultValue="30">
                  <SelectTrigger className="w-44" aria-label="Session timeout">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="15">15 minutes</SelectItem>
                    <SelectItem value="30">30 minutes</SelectItem>
                    <SelectItem value="60">1 hour</SelectItem>
                  </SelectContent>
                </Select>
              </Row>
              <Row title="Active devices" description="3 devices currently signed in.">
                <Button variant="outline" onClick={saved}>
                  Sign out others
                </Button>
              </Row>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="privacy" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Privacy</CardTitle>
              <CardDescription>Data residency and de-identification.</CardDescription>
            </CardHeader>
            <CardContent className="divide-y divide-border">
              <Row title="De-identify exports" description="Strip direct identifiers from PDF and CSV exports.">
                <Switch defaultChecked onCheckedChange={saved} aria-label="De-identify exports" />
              </Row>
              <Row title="Share anonymised data for research" description="Contribute to model improvement studies.">
                <Switch onCheckedChange={saved} aria-label="Share anonymised data" />
              </Row>
              <Row title="Audit log retention" description="How long access logs are kept.">
                <Select defaultValue="24">
                  <SelectTrigger className="w-44" aria-label="Audit log retention">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="12">12 months</SelectItem>
                    <SelectItem value="24">24 months</SelectItem>
                    <SelectItem value="60">5 years</SelectItem>
                  </SelectContent>
                </Select>
              </Row>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="api" className="pt-4">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <CardTitle>API configuration</CardTitle>
                <StatusChip tone="warning">Placeholder</StatusChip>
              </div>
              <CardDescription>Endpoints for the FastAPI inference service and Supabase backend.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="api-base">Inference API base URL</Label>
                <Input id="api-base" placeholder="https://api.oncotwin.health/v1" />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="api-model">Default model version</Label>
                <Input id="api-model" defaultValue="digital-twin-v2.4" />
              </div>
              <Separator />
              <p className="text-xs text-muted-foreground">
                TODO(backend): keys are never stored in the frontend — they will live in Lovable Cloud secrets and be used
                server-side only.
              </p>
              <Button onClick={saved}>Save configuration</Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
