/**
 * Mock clinical dataset used across the app.
 * TODO(backend): replace every export here with FastAPI + Supabase responses.
 */

export type RiskLevel = "low" | "moderate" | "high";
export type ReceptorStatus = "Positive" | "Negative";
export type PatientStatus = "In Treatment" | "Remission" | "Monitoring" | "Critical";

export interface Patient {
  id: string;
  name: string;
  age: number;
  gender: string;
  phone: string;
  email: string;
  hospital: string;
  stage: "0" | "I" | "II" | "III" | "IV";
  tumorSizeMm: number;
  erStatus: ReceptorStatus;
  prStatus: ReceptorStatus;
  her2Status: ReceptorStatus;
  ki67: number;
  grade: 1 | 2 | 3;
  nodesInvolved: number;
  currentTreatment: string;
  status: PatientStatus;
  risk: RiskLevel;
  survivalProbability: number;
  lastUpdated: string;
  diagnosedOn: string;
  twinStatus: "Synced" | "Recalculating" | "Stale";
  history: string[];
  notes: string;
  timeline: { date: string; title: string; detail: string; kind: "diagnosis" | "treatment" | "scan" | "note" }[];
  reports: { name: string; type: string; date: string; size: string }[];
}

const treatments = [
  "AC-T Chemotherapy",
  "Tamoxifen (Endocrine)",
  "Trastuzumab + Chemo",
  "Letrozole + CDK4/6",
  "Neoadjuvant Chemo",
  "Radiotherapy",
];

const names = [
  "Amelia Hart", "Noor Rahman", "Priya Raghavan", "Elena Costa", "Grace Okafor",
  "Sofia Marchetti", "Hana Yamamoto", "Laila Mansour", "Ingrid Larsen", "Camila Duarte",
  "Fatima Zahra", "Mei Ling Chen", "Rachel Adler", "Yasmin Haddad", "Olivia Bennett",
  "Anika Sharma", "Zoe Karalis", "Marta Nowak", "Chiara Rossi", "Dana Petrov",
  "Aisha Bello", "Nina Vasquez", "Leila Farsi", "Emma Sorensen",
];

function pick<T>(arr: T[], i: number): T {
  return arr[i % arr.length];
}

export const patients: Patient[] = names.map((name, i) => {
  const stage = pick(["I", "II", "II", "III", "IV", "0"] as const, i);
  const risk: RiskLevel = stage === "IV" || stage === "III" ? (i % 3 === 0 ? "high" : "moderate") : i % 4 === 0 ? "moderate" : "low";
  const status = pick(["In Treatment", "Monitoring", "Remission", "In Treatment", "Critical"] as const, i);
  return {
    id: `PT-${(1042 + i * 7).toString().padStart(4, "0")}`,
    name,
    age: 33 + ((i * 5) % 42),
    gender: "Female",
    phone: `+1 (415) 555-0${(120 + i).toString().slice(-3)}`,
    email: `${name.toLowerCase().replace(/[^a-z]+/g, ".")}@mail.health`,
    hospital: pick(["Northfield Oncology Center", "St. Marien Klinik", "Cedar Bay Cancer Institute"], i),
    stage,
    tumorSizeMm: 8 + ((i * 9) % 52),
    erStatus: i % 3 === 0 ? "Negative" : "Positive",
    prStatus: i % 4 === 0 ? "Negative" : "Positive",
    her2Status: i % 5 === 0 ? "Positive" : "Negative",
    ki67: 8 + ((i * 7) % 60),
    grade: pick([1, 2, 3, 2] as const, i),
    nodesInvolved: (i * 3) % 9,
    currentTreatment: pick(treatments, i),
    status,
    risk,
    survivalProbability: risk === "high" ? 48 + (i % 12) : risk === "moderate" ? 68 + (i % 12) : 84 + (i % 11),
    lastUpdated: `2026-07-${(28 - (i % 20)).toString().padStart(2, "0")}`,
    diagnosedOn: `2025-${((i % 12) + 1).toString().padStart(2, "0")}-${((i % 27) + 1).toString().padStart(2, "0")}`,
    twinStatus: pick(["Synced", "Synced", "Recalculating", "Stale"] as const, i),
    history: [
      "Family history of breast cancer (maternal)",
      i % 2 === 0 ? "Type 2 diabetes, controlled" : "Hypertension, on medication",
      i % 3 === 0 ? "Previous lumpectomy (2023)" : "No prior oncologic surgery",
    ],
    notes:
      "Patient tolerating current regimen well. Digital twin recalibrated after latest imaging; recommend follow-up MRI in 8 weeks.",
    timeline: [
      { date: "2025-03-11", title: "Initial diagnosis", detail: `Invasive ductal carcinoma, stage ${stage}`, kind: "diagnosis" },
      { date: "2025-04-02", title: "Biopsy & biomarkers", detail: "ER/PR/HER2 panel completed", kind: "scan" },
      { date: "2025-05-20", title: "Treatment started", detail: pick(treatments, i), kind: "treatment" },
      { date: "2026-01-15", title: "Follow-up MRI", detail: "Tumor volume reduced by 22%", kind: "scan" },
      { date: "2026-06-30", title: "Digital twin updated", detail: "Simulation re-run with new labs", kind: "note" },
    ],
    reports: [
      { name: "Mammography_2026_01.pdf", type: "Imaging", date: "2026-01-15", size: "2.4 MB" },
      { name: "Pathology_Panel.pdf", type: "Pathology", date: "2025-04-02", size: "820 KB" },
      { name: "Bloodwork_Q2.csv", type: "Labs", date: "2026-05-08", size: "64 KB" },
    ],
  };
});

export const dashboardStats = [
  { label: "Total Patients", value: "1,284", delta: "+4.2%", tone: "primary" as const, icon: "users" },
  { label: "Active Digital Twins", value: "946", delta: "+7.1%", tone: "primary" as const, icon: "twin" },
  { label: "High Risk Patients", value: "112", delta: "+1.8%", tone: "risk" as const, icon: "alert" },
  { label: "Treatment Simulations", value: "3,470", delta: "+12.4%", tone: "primary" as const, icon: "flask" },
  { label: "Successful Predictions", value: "89.4%", delta: "+2.0%", tone: "success" as const, icon: "check" },
  { label: "Avg. Survival Probability", value: "76.2%", delta: "-0.6%", tone: "warning" as const, icon: "heart" },
];

export const patientGrowth = [
  { month: "Jan", patients: 720, twins: 480 },
  { month: "Feb", patients: 812, twins: 540 },
  { month: "Mar", patients: 878, twins: 612 },
  { month: "Apr", patients: 964, twins: 701 },
  { month: "May", patients: 1052, twins: 788 },
  { month: "Jun", patients: 1173, twins: 869 },
  { month: "Jul", patients: 1284, twins: 946 },
];

export const stageDistribution = [
  { stage: "Stage 0", count: 96 },
  { stage: "Stage I", count: 342 },
  { stage: "Stage II", count: 418 },
  { stage: "Stage III", count: 286 },
  { stage: "Stage IV", count: 142 },
];

export const treatmentComparison = [
  { treatment: "AC-T Chemo", response: 74, recurrence: 18 },
  { treatment: "Endocrine", response: 68, recurrence: 22 },
  { treatment: "HER2 Targeted", response: 81, recurrence: 14 },
  { treatment: "CDK4/6", response: 77, recurrence: 16 },
  { treatment: "Radiotherapy", response: 62, recurrence: 26 },
];

export const accuracyTrend = [
  { month: "Jan", accuracy: 84.2 },
  { month: "Feb", accuracy: 85.1 },
  { month: "Mar", accuracy: 86.4 },
  { month: "Apr", accuracy: 87.0 },
  { month: "May", accuracy: 88.3 },
  { month: "Jun", accuracy: 88.9 },
  { month: "Jul", accuracy: 89.4 },
];

export const riskDistribution = [
  { name: "Low risk", value: 612, key: "low" },
  { name: "Moderate risk", value: 560, key: "moderate" },
  { name: "High risk", value: 112, key: "high" },
];

export const ageDistribution = [
  { range: "25-34", count: 84 },
  { range: "35-44", count: 226 },
  { range: "45-54", count: 388 },
  { range: "55-64", count: 342 },
  { range: "65-74", count: 176 },
  { range: "75+", count: 68 },
];

export const survivalCurve = [
  { year: "Y0", low: 100, moderate: 100, high: 100 },
  { year: "Y1", low: 99, moderate: 96, high: 88 },
  { year: "Y2", low: 98, moderate: 92, high: 76 },
  { year: "Y3", low: 96, moderate: 87, high: 64 },
  { year: "Y4", low: 94, moderate: 82, high: 55 },
  { year: "Y5", low: 92, moderate: 77, high: 47 },
];

export const recentActivity = [
  { title: "Digital twin recalculated", detail: "PT-1049 · Noor Rahman", time: "6 min ago", tone: "primary" as const },
  { title: "Simulation finished", detail: "4 treatment scenarios compared", time: "24 min ago", tone: "success" as const },
  { title: "High-risk flag raised", detail: "PT-1112 · Elena Costa", time: "1 h ago", tone: "risk" as const },
  { title: "New patient added", detail: "PT-1203 · Camila Duarte", time: "3 h ago", tone: "primary" as const },
  { title: "Prediction confidence dropped", detail: "Model v2.4 · cohort HER2+", time: "5 h ago", tone: "warning" as const },
];

export const followUps = [
  { patient: "Amelia Hart", id: "PT-1042", when: "Today · 14:30", type: "MRI review" },
  { patient: "Priya Raghavan", id: "PT-1056", when: "Tomorrow · 09:15", type: "Chemo cycle 4" },
  { patient: "Grace Okafor", id: "PT-1070", when: "Fri · 11:00", type: "Twin re-simulation" },
  { patient: "Hana Yamamoto", id: "PT-1084", when: "Mon · 15:45", type: "Biomarker panel" },
];

export interface Scenario {
  id: string;
  name: string;
  regimen: string;
  predictedResponse: number;
  tumorChange: number;
  risk: RiskLevel;
  confidence: number;
  survival5y: number;
  sideEffectRisk: number;
  recoveryWeeks: number;
  recommended: boolean;
}

export const scenarios: Scenario[] = [
  {
    id: "sc-1",
    name: "HER2 Targeted Therapy",
    regimen: "Trastuzumab + Pertuzumab + Docetaxel",
    predictedResponse: 84,
    tumorChange: -46,
    risk: "low",
    confidence: 91,
    survival5y: 88,
    sideEffectRisk: 28,
    recoveryWeeks: 14,
    recommended: true,
  },
  {
    id: "sc-2",
    name: "Neoadjuvant Chemotherapy",
    regimen: "Doxorubicin + Cyclophosphamide → Paclitaxel",
    predictedResponse: 76,
    tumorChange: -38,
    risk: "moderate",
    confidence: 87,
    survival5y: 81,
    sideEffectRisk: 54,
    recoveryWeeks: 22,
    recommended: false,
  },
  {
    id: "sc-3",
    name: "Endocrine Therapy",
    regimen: "Letrozole + Ribociclib",
    predictedResponse: 69,
    tumorChange: -24,
    risk: "moderate",
    confidence: 82,
    survival5y: 77,
    sideEffectRisk: 21,
    recoveryWeeks: 8,
    recommended: false,
  },
  {
    id: "sc-4",
    name: "Surgery + Radiotherapy",
    regimen: "Lumpectomy followed by whole-breast RT",
    predictedResponse: 58,
    tumorChange: -18,
    risk: "high",
    confidence: 74,
    survival5y: 66,
    sideEffectRisk: 37,
    recoveryWeeks: 18,
    recommended: false,
  },
];

export const progressionForecast = [
  { month: "M0", untreated: 26, treated: 26 },
  { month: "M3", untreated: 31, treated: 20 },
  { month: "M6", untreated: 38, treated: 15 },
  { month: "M9", untreated: 46, treated: 12 },
  { month: "M12", untreated: 55, treated: 10 },
  { month: "M18", untreated: 68, treated: 9 },
];

export const featureImportance = [
  { feature: "HER2 status", weight: 0.24, direction: "negative" },
  { feature: "Tumor size (mm)", weight: 0.19, direction: "negative" },
  { feature: "Ki-67 index", weight: 0.16, direction: "negative" },
  { feature: "Lymph nodes involved", weight: 0.13, direction: "negative" },
  { feature: "ER status", weight: 0.11, direction: "positive" },
  { feature: "Age at diagnosis", weight: 0.09, direction: "positive" },
  { feature: "Treatment adherence", weight: 0.08, direction: "positive" },
];

export const notifications = [
  { id: "n1", title: "New patient added", body: "Camila Duarte (PT-1203) was registered by Dr. Alvarez.", time: "3 min ago", type: "patient", unread: true },
  { id: "n2", title: "Prediction completed", body: "Survival model finished for PT-1049 with 91% confidence.", time: "22 min ago", type: "prediction", unread: true },
  { id: "n3", title: "Digital twin updated", body: "Twin for PT-1070 re-synced with new imaging data.", time: "1 h ago", type: "twin", unread: true },
  { id: "n4", title: "Simulation finished", body: "4 treatment scenarios compared for PT-1042.", time: "4 h ago", type: "simulation", unread: false },
  { id: "n5", title: "System alert", body: "Model registry v2.4 deployed to the inference cluster.", time: "Yesterday", type: "system", unread: false },
  { id: "n6", title: "High-risk flag", body: "PT-1112 crossed the recurrence-risk threshold (78%).", time: "Yesterday", type: "system", unread: false },
];

export const doctor = {
  name: "Dr. Sarah Whitmore",
  email: "s.whitmore@northfield.health",
  phone: "+1 (415) 555-0188",
  hospital: "Northfield Oncology Center",
  department: "Medical Oncology",
  specialization: "Breast Oncology & Precision Medicine",
  role: "Consultant Oncologist",
  experience: "14 years",
  initials: "SW",
};
