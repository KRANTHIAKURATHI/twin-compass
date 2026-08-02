import { useMemo, useState } from "react";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowUpDown, Filter, Plus, Search, Trash2, Pencil, Users } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { RiskChip, StatusChip, type ChipTone } from "@/components/common/StatusChip";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { patients, type Patient, type PatientStatus } from "@/lib/mock-data";
import { patientService } from "@/services";

export const Route = createFileRoute("/_shell/patients/")({
  head: () => ({
    meta: [
      { title: "Patient Management — OncoTwin" },
      { name: "description", content: "Search, filter and manage breast cancer patients, biomarkers and treatment status." },
      { property: "og:title", content: "Patient Management — OncoTwin" },
      { property: "og:description", content: "Search, filter and manage breast cancer patients, biomarkers and treatment status." },
    ],
  }),
  errorComponent: RouteErrorState,
  component: withPageStates(PatientsPage, { variant: "list" }),
});

const statusTone: Record<PatientStatus, ChipTone> = {
  "In Treatment": "primary",
  Remission: "success",
  Monitoring: "neutral",
  Critical: "risk",
};

const PAGE_SIZE = 8;

function PatientsPage() {
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState("all");
  const [status, setStatus] = useState("all");
  const [sortAsc, setSortAsc] = useState(true);
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);

  const filtered = useMemo(() => {
    const rows = patients.filter((p) => {
      const q = query.trim().toLowerCase();
      const matchQ = !q || p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q);
      return matchQ && (stage === "all" || p.stage === stage) && (status === "all" || p.status === status);
    });
    return [...rows].sort((a, b) => (sortAsc ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name)));
  }, [query, stage, status, sortAsc]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pageCount);
  const rows = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  const remove = async (p: Patient) => {
    await patientService.remove(p.id);
    toast.success(`${p.name} removed`, { description: "TODO: wire DELETE /api/patients/{id}" });
  };

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Patients"
        description="All patients under your care, with biomarkers, treatment and twin status."
        crumbs={[{ label: "Home", to: "/" }, { label: "Patients" }]}
        actions={
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="size-4" aria-hidden="true" /> Add patient
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>Create patient</DialogTitle>
                <DialogDescription>Register a new patient and generate their digital twin.</DialogDescription>
              </DialogHeader>
              <form
                className="grid gap-4 sm:grid-cols-2"
                onSubmit={async (e) => {
                  e.preventDefault();
                  await patientService.create({});
                  setCreateOpen(false);
                  toast.success("Patient created", { description: "TODO: wire POST /api/patients" });
                }}
              >
                <div className="grid gap-2 sm:col-span-2">
                  <Label htmlFor="p-name">Full name</Label>
                  <Input id="p-name" placeholder="Jane Doe" required />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="p-age">Age</Label>
                  <Input id="p-age" type="number" min={18} max={110} placeholder="52" required />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="p-tumor">Tumor size (mm)</Label>
                  <Input id="p-tumor" type="number" min={1} placeholder="22" />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="p-stage">Cancer stage</Label>
                  <Select defaultValue="II">
                    <SelectTrigger id="p-stage">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {["0", "I", "II", "III", "IV"].map((s) => (
                        <SelectItem key={s} value={s}>
                          Stage {s}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="p-her2">HER2 status</Label>
                  <Select defaultValue="Negative">
                    <SelectTrigger id="p-her2">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Positive">Positive</SelectItem>
                      <SelectItem value="Negative">Negative</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <DialogFooter className="sm:col-span-2">
                  <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit">Create patient</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      <Card className="gap-0 overflow-hidden p-0">
        <div className="flex flex-col gap-3 border-b border-border p-4 md:flex-row md:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
              placeholder="Search by name or patient ID…"
              aria-label="Search patients"
              className="pl-9"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Select value={stage} onValueChange={(v) => { setStage(v); setPage(1); }}>
              <SelectTrigger className="w-[150px]" aria-label="Filter by stage">
                <Filter className="size-4" aria-hidden="true" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All stages</SelectItem>
                {["0", "I", "II", "III", "IV"].map((s) => (
                  <SelectItem key={s} value={s}>
                    Stage {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={status} onValueChange={(v) => { setStatus(v); setPage(1); }}>
              <SelectTrigger className="w-[160px]" aria-label="Filter by status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                {Object.keys(statusTone).map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => setSortAsc((v) => !v)}>
              <ArrowUpDown className="size-4" aria-hidden="true" /> Name {sortAsc ? "A–Z" : "Z–A"}
            </Button>
          </div>
        </div>

        {rows.length === 0 ? (
          <div className="p-6">
            <EmptyState
              icon={Users}
              title="No patients match your filters"
              description="Try adjusting your search terms or clearing the stage and status filters."
              action={
                <Button variant="outline" onClick={() => { setQuery(""); setStage("all"); setStatus("all"); }}>
                  Clear filters
                </Button>
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Patient ID</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Age</TableHead>
                  <TableHead>Stage</TableHead>
                  <TableHead>Tumor</TableHead>
                  <TableHead>ER</TableHead>
                  <TableHead>PR</TableHead>
                  <TableHead>HER2</TableHead>
                  <TableHead>Treatment</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Risk</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((p) => (
                  <TableRow key={p.id} className="transition-colors">
                    <TableCell className="font-mono text-xs text-muted-foreground">{p.id}</TableCell>
                    <TableCell>
                      <Link
                        to="/patients/$patientId"
                        params={{ patientId: p.id }}
                        className="font-medium text-foreground underline-offset-4 hover:text-primary hover:underline"
                      >
                        {p.name}
                      </Link>
                    </TableCell>
                    <TableCell>{p.age}</TableCell>
                    <TableCell>
                      <StatusChip tone="neutral">Stage {p.stage}</StatusChip>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">{p.tumorSizeMm} mm</TableCell>
                    <TableCell className={p.erStatus === "Positive" ? "text-success" : "text-muted-foreground"}>
                      {p.erStatus === "Positive" ? "+" : "−"}
                    </TableCell>
                    <TableCell className={p.prStatus === "Positive" ? "text-success" : "text-muted-foreground"}>
                      {p.prStatus === "Positive" ? "+" : "−"}
                    </TableCell>
                    <TableCell className={p.her2Status === "Positive" ? "text-warning-foreground" : "text-muted-foreground"}>
                      {p.her2Status === "Positive" ? "+" : "−"}
                    </TableCell>
                    <TableCell className="max-w-[180px] truncate text-sm">{p.currentTreatment}</TableCell>
                    <TableCell>
                      <StatusChip tone={statusTone[p.status]}>{p.status}</StatusChip>
                    </TableCell>
                    <TableCell>
                      <RiskChip level={p.risk} />
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{p.lastUpdated}</TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" aria-label={`Edit ${p.name}`} asChild>
                          <Link to="/patients/$patientId" params={{ patientId: p.id }}>
                            <Pencil className="size-4" aria-hidden="true" />
                          </Link>
                        </Button>
                        <Button variant="ghost" size="icon" aria-label={`Delete ${p.name}`} onClick={() => remove(p)}>
                          <Trash2 className="size-4 text-risk" aria-hidden="true" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <div className="flex flex-col items-center justify-between gap-3 border-t border-border p-4 sm:flex-row">
          <p className="text-xs text-muted-foreground">
            Showing {rows.length} of {filtered.length} patients
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={current === 1} onClick={() => setPage(current - 1)}>
              Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              Page {current} / {pageCount}
            </span>
            <Button variant="outline" size="sm" disabled={current === pageCount} onClick={() => setPage(current + 1)}>
              Next
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
