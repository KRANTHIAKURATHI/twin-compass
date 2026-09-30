import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import type { Patient, PatientInput } from "@/types/models";
import { useCreatePatient, useUpdatePatient } from "@/hooks/api";

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

/** Radix Select cannot hold an empty string, so "not recorded" is undefined. */
const optional = (value: string | null | undefined) => (value ? value : undefined);

/** Dates arrive as timestamps but `<input type="date">` wants `YYYY-MM-DD`. */
const dateInput = (value?: string | null) => (value ? value.slice(0, 10) : "");

type FormState = {
  name: string;
  age: string;
  gender: string;
  email: string;
  phone: string;
  hospital: string;
  stage: string;
  tumorSizeMm: string;
  nodesInvolved: string;
  grade: string;
  erStatus: string;
  prStatus: string;
  her2Status: string;
  ki67: number | null;
  currentTreatment: string;
  status: string;
  diagnosedOn: string;
  notes: string;
};

const initial = (patient?: Patient): FormState => ({
  name: patient?.name ?? "",
  age: patient?.age == null ? "" : String(patient.age),
  gender: patient?.gender ?? "",
  email: patient?.email ?? "",
  phone: patient?.phone ?? "",
  hospital: patient?.hospital ?? "",
  stage: patient?.stage ?? "",
  tumorSizeMm: patient?.tumorSizeMm == null ? "" : String(patient.tumorSizeMm),
  nodesInvolved: patient?.nodesInvolved == null ? "" : String(patient.nodesInvolved),
  grade: patient?.grade == null ? "" : String(patient.grade),
  erStatus: patient?.erStatus ?? "",
  prStatus: patient?.prStatus ?? "",
  her2Status: patient?.her2Status ?? "",
  ki67: patient?.ki67 ?? null,
  currentTreatment: patient?.currentTreatment ?? "",
  status: patient?.status ?? "",
  diagnosedOn: dateInput(patient?.diagnosedOn),
  notes: patient?.notes ?? "",
});

/**
 * Builds the API payload from the form.
 *
 * Blank fields are omitted rather than sent as 0 or a plausible default. The
 * form used to pre-fill age 52, a hospital name, a 22 mm tumour and grade 2,
 * then submit only `ki67` regardless — so untouched invented values looked
 * saved while real edits were silently dropped. Both halves of that are fixed
 * here: nothing is invented, and everything entered is sent.
 */
function toPayload(f: FormState): PatientInput {
  const num = (value: string) => (value.trim() === "" ? undefined : Number(value));
  const str = (value: string) => (value.trim() === "" ? undefined : value.trim());
  return {
    name: f.name.trim(),
    age: num(f.age),
    gender: str(f.gender),
    email: str(f.email),
    phone: str(f.phone),
    hospital: str(f.hospital),
    stage: str(f.stage) as Patient["stage"],
    tumorSizeMm: num(f.tumorSizeMm),
    nodesInvolved: num(f.nodesInvolved),
    grade: (f.grade === "" ? undefined : Number(f.grade)) as Patient["grade"],
    erStatus: str(f.erStatus) as Patient["erStatus"],
    prStatus: str(f.prStatus) as Patient["prStatus"],
    her2Status: str(f.her2Status) as Patient["her2Status"],
    ki67: f.ki67 ?? undefined,
    currentTreatment: str(f.currentTreatment),
    status: str(f.status) as Patient["status"],
    diagnosedOn: str(f.diagnosedOn),
    notes: str(f.notes),
  };
}

export function PatientForm({ patient, mode }: { patient?: Patient; mode: "create" | "edit" }) {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormState>(() => initial(patient));
  const createPatient = useCreatePatient();
  const updatePatient = useUpdatePatient(patient?.id ?? "");
  const saving = createPatient.isPending || updatePatient.isPending;

  const set = <K extends keyof FormState>(key: K) => (value: FormState[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = toPayload(form);
    if (mode === "create") {
      const created = await createPatient.mutateAsync(payload);
      // The API assigns the patient code, so the new record is the only place
      // to learn where to navigate; without it, fall back to the list.
      const newId = created.data?.id;
      navigate(newId ? { to: "/patients/$patientId", params: { patientId: newId } } : { to: "/patients" });
    } else {
      await updatePatient.mutateAsync(payload);
      navigate({ to: "/patients/$patientId", params: { patientId: patient!.id } });
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
            <Input id="name" value={form.name} onChange={(e) => set("name")(e.target.value)} placeholder="Jane Doe" required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="age">Age</Label>
            <Input
              id="age"
              type="number"
              min={18}
              max={110}
              value={form.age}
              onChange={(e) => set("age")(e.target.value)}
              placeholder="Not recorded"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="gender">Gender</Label>
            <Select value={optional(form.gender)} onValueChange={set("gender")}>
              <SelectTrigger id="gender">
                <SelectValue placeholder="Not recorded" />
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
            <Input
              id="email"
              type="email"
              value={form.email}
              onChange={(e) => set("email")(e.target.value)}
              placeholder="jane.doe@mail.health"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="phone">Phone</Label>
            <Input id="phone" value={form.phone} onChange={(e) => set("phone")(e.target.value)} placeholder="+1 (415) 555-0000" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="hospital">Hospital</Label>
            <Input
              id="hospital"
              value={form.hospital}
              onChange={(e) => set("hospital")(e.target.value)}
              placeholder="Not recorded"
            />
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
            <Select value={optional(form.stage)} onValueChange={set("stage")}>
              <SelectTrigger id="stage">
                <SelectValue placeholder="Not recorded" />
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
            <Input
              id="tumor"
              type="number"
              min={1}
              max={200}
              value={form.tumorSizeMm}
              onChange={(e) => set("tumorSizeMm")(e.target.value)}
              placeholder="Not measured"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="nodes">Nodes involved</Label>
            <Input
              id="nodes"
              type="number"
              min={0}
              max={40}
              value={form.nodesInvolved}
              onChange={(e) => set("nodesInvolved")(e.target.value)}
              placeholder="Not assessed"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="grade">Histologic grade</Label>
            <Select value={optional(form.grade)} onValueChange={set("grade")}>
              <SelectTrigger id="grade">
                <SelectValue placeholder="Not recorded" />
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
          {([
            { id: "er", label: "ER status", key: "erStatus" as const },
            { id: "pr", label: "PR status", key: "prStatus" as const },
            { id: "her2", label: "HER2 status", key: "her2Status" as const },
          ]).map((r) => (
            <div key={r.id} className="space-y-1.5">
              <Label htmlFor={r.id}>{r.label}</Label>
              <Select value={optional(form[r.key])} onValueChange={set(r.key)}>
                <SelectTrigger id={r.id}>
                  <SelectValue placeholder="Not recorded" />
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
            <Label htmlFor="ki67">
              Ki-67 proliferation index — {form.ki67 === null ? "not recorded" : `${form.ki67}%`}
            </Label>
            {/* The slider starts at 0 only once the clinician moves it, so an
                untouched control never writes a value of its own. */}
            <Slider
              id="ki67"
              value={[form.ki67 ?? 0]}
              min={0}
              max={100}
              step={1}
              onValueChange={(v) => set("ki67")(v[0])}
            />
            {form.ki67 !== null && (
              <Button type="button" variant="ghost" size="sm" onClick={() => set("ki67")(null)}>
                Clear
              </Button>
            )}
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
            <Select value={optional(form.currentTreatment)} onValueChange={set("currentTreatment")}>
              <SelectTrigger id="treatment">
                <SelectValue placeholder="None recorded" />
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
            <Select value={optional(form.status)} onValueChange={set("status")}>
              <SelectTrigger id="status">
                <SelectValue placeholder="Not recorded" />
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
            <Input
              id="diagnosed"
              type="date"
              value={form.diagnosedOn}
              onChange={(e) => set("diagnosedOn")(e.target.value)}
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="notes">Clinical notes</Label>
            <Textarea
              id="notes"
              rows={4}
              value={form.notes}
              onChange={(e) => set("notes")(e.target.value)}
              placeholder="Observations, comorbidities, plan…"
            />
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
