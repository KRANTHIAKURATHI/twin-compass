import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import type { Patient, PatientInput, PatientStatus, ReceptorStatus, TumorStage } from "@/types/models";
import { useCreatePatient, useUpdatePatient } from "@/hooks/api";

const stages: TumorStage[] = ["0", "I", "II", "III", "IV"];
const receptors: ReceptorStatus[] = ["Positive", "Negative"];
const treatments = [
  "AC-T Chemotherapy",
  "Tamoxifen (Endocrine)",
  "Trastuzumab + Chemo",
  "Letrozole + CDK4/6",
  "Neoadjuvant Chemo",
  "Radiotherapy",
];
const statuses: PatientStatus[] = ["In Treatment", "Remission", "Monitoring", "Critical"];
const genders = ["Female", "Male", "Other"];

export function PatientForm({ patient, mode }: { patient?: Patient; mode: "create" | "edit" }) {
  const navigate = useNavigate();
  const createPatient = useCreatePatient();
  const updatePatient = useUpdatePatient(patient?.id ?? "");
  const saving = createPatient.isPending || updatePatient.isPending;

  const [gender, setGender] = useState(patient?.gender ?? "Female");
  const [stage, setStage] = useState<TumorStage>(patient?.stage ?? "II");
  const [grade, setGrade] = useState(String(patient?.grade ?? 2));
  const [erStatus, setErStatus] = useState<ReceptorStatus>(patient?.erStatus ?? "Positive");
  const [prStatus, setPrStatus] = useState<ReceptorStatus>(patient?.prStatus ?? "Positive");
  const [her2Status, setHer2Status] = useState<ReceptorStatus>(patient?.her2Status ?? "Positive");
  const [ki67, setKi67] = useState(patient?.ki67 ?? 20);
  const [treatment, setTreatment] = useState(patient?.currentTreatment ?? treatments[0]);
  const [status, setStatus] = useState<PatientStatus>(patient?.status ?? "In Treatment");

  const submit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);

    const payload: PatientInput = {
      name: String(form.get("name") ?? ""),
      age: Number(form.get("age") ?? 0),
      gender,
      email: String(form.get("email") ?? ""),
      phone: String(form.get("phone") ?? ""),
      hospital: String(form.get("hospital") ?? ""),
      stage,
      tumorSizeMm: Number(form.get("tumor") ?? 0),
      nodesInvolved: Number(form.get("nodes") ?? 0),
      grade: Number(grade) as 1 | 2 | 3,
      erStatus,
      prStatus,
      her2Status,
      ki67,
      currentTreatment: treatment,
      status,
      diagnosedOn: String(form.get("diagnosed") ?? ""),
      notes: String(form.get("notes") ?? ""),
    };

    const onSuccess = () => {
      navigate({
        to: mode === "edit" ? "/patients/$patientId" : "/patients",
        params: { patientId: patient?.id ?? "" },
      });
    };

    if (mode === "create") {
      createPatient.mutate(payload, { onSuccess });
    } else {
      updatePatient.mutate(payload, { onSuccess });
    }
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
            <Input id="name" name="name" defaultValue={patient?.name} placeholder="Jane Doe" required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="age">Age</Label>
            <Input id="age" name="age" type="number" min={18} max={110} defaultValue={patient?.age ?? 52} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="gender">Gender</Label>
            <Select value={gender} onValueChange={setGender}>
              <SelectTrigger id="gender">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {genders.map((g) => (
                  <SelectItem key={g} value={g}>
                    {g}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" name="email" type="email" defaultValue={patient?.email} placeholder="jane.doe@mail.health" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="phone">Phone</Label>
            <Input id="phone" name="phone" defaultValue={patient?.phone} placeholder="+1 (415) 555-0000" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="hospital">Hospital</Label>
            <Input id="hospital" name="hospital" defaultValue={patient?.hospital ?? "Northfield Oncology Center"} />
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
            <Select value={stage} onValueChange={(v) => setStage(v as TumorStage)}>
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
            <Input id="tumor" name="tumor" type="number" min={1} max={200} defaultValue={patient?.tumorSizeMm ?? 22} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="nodes">Nodes involved</Label>
            <Input id="nodes" name="nodes" type="number" min={0} max={40} defaultValue={patient?.nodesInvolved ?? 0} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="grade">Histologic grade</Label>
            <Select value={grade} onValueChange={setGrade}>
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
            { id: "er", label: "ER status", value: erStatus, onChange: setErStatus },
            { id: "pr", label: "PR status", value: prStatus, onChange: setPrStatus },
            { id: "her2", label: "HER2 status", value: her2Status, onChange: setHer2Status },
          ].map((r) => (
            <div key={r.id} className="space-y-1.5">
              <Label htmlFor={r.id}>{r.label}</Label>
              <Select value={r.value} onValueChange={(v) => r.onChange(v as ReceptorStatus)}>
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
            <Select value={treatment} onValueChange={setTreatment}>
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
            <Select value={status} onValueChange={(v) => setStatus(v as PatientStatus)}>
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
            <Input id="diagnosed" name="diagnosed" type="date" defaultValue={patient?.diagnosedOn ?? "2026-01-15"} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="notes">Clinical notes</Label>
            <Textarea id="notes" name="notes" rows={4} defaultValue={patient?.notes} placeholder="Observations, comorbidities, plan…" />
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
