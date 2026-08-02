import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { Check, Minus, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { permissionMatrix } from "@/services/data";

export const Route = createFileRoute("/_admin/admin/permissions")({
  head: () => ({
    meta: [
      { title: "Permissions — OncoTwin Admin" },
      { name: "description", content: "Role-based capability matrix for doctors, patients, technicians and administrators." },
      { property: "og:title", content: "Permissions — OncoTwin Admin" },
      { property: "og:description", content: "Role-based capability matrix for doctors, patients, technicians and administrators." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(PermissionsPage, { variant: "list" }),
});

const roles = ["doctor", "patient", "technician", "admin"] as const;

function Cell({ on }: { on: boolean }) {
  return on ? (
    <span className="flex size-6 items-center justify-center rounded-full bg-success-soft text-success">
      <Check className="size-3.5" aria-hidden="true" />
      <span className="sr-only">Allowed</span>
    </span>
  ) : (
    <span className="flex size-6 items-center justify-center rounded-full bg-muted text-muted-foreground">
      <Minus className="size-3.5" aria-hidden="true" />
      <span className="sr-only">Denied</span>
    </span>
  );
}

function PermissionsPage() {
  return (
    <div className="mx-auto max-w-[1000px]">
      <PageHeader
        title="Permissions"
        description="What each role can do. Roles are enforced server-side, never in the browser."
        actions={
          <Button onClick={() => toast.success("Roles saved", { description: "TODO: wire PUT /api/admin/permissions" })}>
            <ShieldCheck className="size-4" aria-hidden="true" /> Save matrix
          </Button>
        }
      />
      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle>Capability matrix</CardTitle>
          <CardDescription>Applies across every hospital tenant</CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Capability</TableHead>
                {roles.map((r) => (
                  <TableHead key={r} className="capitalize">
                    {r}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {permissionMatrix.map((row) => (
                <TableRow key={row.capability}>
                  <TableCell className="font-medium">{row.capability}</TableCell>
                  {roles.map((r) => (
                    <TableCell key={r}>
                      <Cell on={row[r]} />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
