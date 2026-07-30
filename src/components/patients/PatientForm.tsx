import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import type { Patient } from "@/lib/mock-data";
import { patientService } from "@/services";

const stages = ["0", "I", "II", "III", "IV"];
const receptors = ["Positive", "Negative"];
const treatments = [
  "AC-T Chemotherapy",
  "Tamoxifen (Endocrine)",
  "Trastuzumab + Chemo",
  "Letrozole + CDK4/6",
  "Neoadjuvant Chemo",
  "Radiotherapy",
];
const statuses = ["In Treatment", "Remission", "Monitoring", "Critical"];

export function PatientForm({ patient, mode }: { patient?: Patient; mode: "create" | "edit" }) {
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [ki67, setKi67] = useState(patient?.ki67 ?? 20);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    // TODO(backend): POST /api/patients or PATCH /api/patients/{id}
    if (mode === "create") await patientService.create({ name: "New patient" });
    else await patientService.update(patient!.id, { ki67 });
    setSaving(false);
    toast.success(mode === "create" ? "Patient created" : "Patient updated", {
      description: "TODO: wire to the clinical records API",
    });
    navigate({ to: mode === "edit" ? "/patients/$patientId" : "/patients", params: { patientId: patient?.id ?? "" } });
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Demographics</CardTitle>
          <CardDescription>Basic identity and contact details</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-1.5">
            <Label htmlFor="name">Full name</Label>
            <Input id="name" defaultValue={patient?.name} placeholder="Jane Doe" required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="age">Age</Label>
            <Input id="age" type="number" min={18} max={110} defaultValue={patient?.age ?? 52} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="gender">Gender</Label>
            <Select defaultValue={patient?.gender ?? "Female"}>
              <SelectTrigger id="gender">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["Female", "Male", "Other"].map((g) => (
                  <SelectItem key={g} value={g}>
                    {g}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" defaultValue={patient?.email} placeholder="jane.doe@mail.health" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="phone">Phone</Label>
            <Input id="phone" defaultValue={patient?.phone} placeholder="+1 (415) 555-0000" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="hospital">Hospital</Label>
            <Input id="hospital" defaultValue={patient?.hospital ?? "Northfield Oncology Center"} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Clinical & biomarkers</CardTitle>
          <CardDescription>These values drive the digital twin and prediction models</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-1.5">
            <Label htmlFor="stage">Cancer stage</Label>
            <Select defaultValue={patient?.stage ?? "II"}>
              <SelectTrigger id="stage">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {stages.map((s) => (
                  <SelectItem key={s} value={s}>
                    Stage {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="tumor">Tumor size (mm)</Label>
            <Input id="tumor" type="number" min={1} max={200} defaultValue={patient?.tumorSizeMm ?? 22} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="nodes">Nodes involved</Label>
            <Input id="nodes" type="number" min={0} max={40} defaultValue={patient?.nodesInvolved ?? 0} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="grade">Histologic grade</Label>
            <Select defaultValue={String(patient?.grade ?? 2)}>
              <SelectTrigger id="grade">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[1, 2, 3].map((g) => (
                  <SelectItem key={g} value={String(g)}>
                    G{g}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {[
            { id: "er", label: "ER status", value: patient?.erStatus },
            { id: "pr", label: "PR status", value: patient?.prStatus },
            { id: "her2", label: "HER2 status", value: patient?.her2Status },
          ].map((r) => (
            <div key={r.id} className="space-y-1.5">
              <Label htmlFor={r.id}>{r.label}</Label>
              <Select defaultValue={r.value ?? "Positive"}>
                <SelectTrigger id={r.id}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {receptors.map((v) => (
                    <SelectItem key={v} value={v}>
                      {v}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ))}
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="ki67">Ki-67 proliferation index — {ki67}%</Label>
            <Slider id="ki67" value={[ki67]} min={0} max={100} step={1} onValueChange={(v) => setKi67(v[0])} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Treatment & status</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="treatment">Current treatment</Label>
            <Select defaultValue={patient?.currentTreatment ?? treatments[0]}>
              <SelectTrigger id="treatment">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {treatments.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="status">Health status</Label>
            <Select defaultValue={patient?.status ?? "In Treatment"}>
              <SelectTrigger id="status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {statuses.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="diagnosed">Diagnosed on</Label>
            <Input id="diagnosed" type="date" defaultValue={patient?.diagnosedOn ?? "2026-01-15"} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="notes">Clinical notes</Label>
            <Textarea id="notes" rows={4} defaultValue={patient?.notes} placeholder="Observations, comorbidities, plan…" />
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : mode === "create" ? "Create patient" : "Save changes"}
        </Button>
        <Button type="button" variant="outline" onClick={() => navigate({ to: "/patients" })}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
