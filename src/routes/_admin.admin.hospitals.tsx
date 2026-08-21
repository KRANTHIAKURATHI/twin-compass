import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RouteErrorState } from "@/components/common/PageState";
import { Building2, Plus } from "lucide-react";
import { toast } from "sonner";

import { Column, DataTablePage } from "@/components/common/DataTablePage";
import { StatCard } from "@/components/common/StatCard";
import { StatusChip } from "@/components/common/StatusChip";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCreateHospital, useHospitals } from "@/hooks/api";
import type { Hospital } from "@/types/models";

export const Route = createFileRoute("/_admin/admin/hospitals")({
  head: () => ({
    meta: [
      { title: "Hospital Management — OncoTwin Admin" },
      { name: "description", content: "Manage hospital tenants, capacity and onboarding status across the OncoTwin network." },
      { property: "og:title", content: "Hospital Management — OncoTwin Admin" },
      { property: "og:description", content: "Manage hospital tenants, capacity and onboarding status across the OncoTwin network." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: HospitalsPage,
});

type Row = Hospital;

const columns: Column<Row>[] = [
  { key: "name", header: "Hospital", cell: (r) => <span className="font-medium">{r.name}</span> },
  { key: "city", header: "Location", cell: (r) => r.city },
  { key: "beds", header: "Beds", cell: (r) => r.beds },
  { key: "doctors", header: "Doctors", cell: (r) => r.doctors },
  { key: "patients", header: "Patients", cell: (r) => r.patients },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusChip tone={r.status === "Active" ? "success" : "warning"}>{r.status}</StatusChip>,
  },
];

function HospitalsPage() {
  const { data, isLoading, isError, refetch } = useHospitals();
  const createHospital = useCreateHospital();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [city, setCity] = useState("");
  const [beds, setBeds] = useState("100");
  const [status, setStatus] = useState("Active");

  const hospitals = data ?? [];

  const handleAddHospital = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      toast.error("Hospital name is required");
      return;
    }

    try {
      await createHospital.mutateAsync({
        name: name.trim(),
        city: city.trim(),
        beds: Number(beds) || 0,
        status,
      });
      setOpen(false);
      setName("");
      setCity("");
      setBeds("100");
      setStatus("Active");
    } catch {
      // Error handled by mutation
    }
  };

  return (
    <DataTablePage
      title="Hospital management"
      description="Tenants connected to the OncoTwin platform."
      columns={columns}
      rows={hospitals}
      loading={isLoading}
      error={isError}
      onRetry={() => refetch()}
      actions={
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="size-4" aria-hidden="true" /> Add hospital
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Hospital Tenant</DialogTitle>
              <DialogDescription>
                Register a new hospital network or medical center on the OncoTwin platform.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleAddHospital} className="space-y-4 py-2">
              <div className="space-y-2">
                <Label htmlFor="h-name">Hospital Name</Label>
                <Input
                  id="h-name"
                  placeholder="e.g. Memorial Sloan Oncology Center"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="h-city">Location / City</Label>
                  <Input
                    id="h-city"
                    placeholder="e.g. Boston, MA"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="h-beds">Total Beds</Label>
                  <Input
                    id="h-beds"
                    type="number"
                    min="0"
                    placeholder="250"
                    value={beds}
                    onChange={(e) => setBeds(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="h-status">Onboarding Status</Label>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger id="h-status">
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Active">Active</SelectItem>
                    <SelectItem value="Onboarding">Onboarding</SelectItem>
                    <SelectItem value="Pending">Pending</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <DialogFooter className="pt-4">
                <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createHospital.isPending}>
                  {createHospital.isPending ? "Creating..." : "Create Hospital"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      }
    >
      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        <StatCard icon={Building2} label="Hospitals" value={String(hospitals.length)} />
        <StatCard icon={Building2} label="Total doctors" value={String(hospitals.reduce((a, h) => a + h.doctors, 0))} />
        <StatCard icon={Building2} label="Total patients" value={String(hospitals.reduce((a, h) => a + h.patients, 0))} />
      </div>
    </DataTablePage>
  );
}
