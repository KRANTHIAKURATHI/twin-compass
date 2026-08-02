/**
 * Lifecycle / versioning mock datasets: digital-twin versions, prediction history,
 * simulation runs, document links and report history.
 * TODO(backend): replace each export with FastAPI / database responses.
 */

export type LifecycleStatus = "Active" | "Superseded" | "Archived" | "Draft";

export interface TwinVersion {
  version: string;
  createdAt: string;
  status: LifecycleStatus;
  author: string;
  summary: string;
  tumorSizeMm: number;
  survival: number;
  risk: "low" | "moderate" | "high";
  model: string;
}

export const twinVersions: TwinVersion[] = [
  {
    version: "v7",
    createdAt: "2026-07-28 09:12",
    status: "Active",
    author: "OCR approval · Dr. Sarah Whitmore",
    summary: "Tumor size updated to 21 mm from verified MRI extraction",
    tumorSizeMm: 21,
    survival: 88,
    risk: "low",
    model: "twin-v2.4",
  },
  {
    version: "v6",
    createdAt: "2026-06-21 09:14",
    status: "Superseded",
    author: "Dr. Sarah Whitmore",
    summary: "Ki-67 corrected to 24%, recurrence head re-run",
    tumorSizeMm: 23,
    survival: 86,
    risk: "low",
    model: "twin-v2.4",
  },
  {
    version: "v5",
    createdAt: "2026-05-14 15:40",
    status: "Superseded",
    author: "Automatic recalculation",
    summary: "Cycle 3 chemotherapy exposure ingested",
    tumorSizeMm: 26,
    survival: 84,
    risk: "moderate",
    model: "twin-v2.3",
  },
  {
    version: "v4",
    createdAt: "2026-04-02 11:02",
    status: "Superseded",
    author: "Radiology import",
    summary: "CT chest/abdomen — no distant disease, staging confirmed",
    tumorSizeMm: 29,
    survival: 82,
    risk: "moderate",
    model: "twin-v2.3",
  },
  {
    version: "v3",
    createdAt: "2026-02-10 08:25",
    status: "Archived",
    author: "Dr. Luis Alvarez",
    summary: "Treatment plan attached (AC-T + Trastuzumab)",
    tumorSizeMm: 32,
    survival: 79,
    risk: "moderate",
    model: "twin-v2.2",
  },
];

export const twinSnapshots = [
  { id: "SNP-311", version: "v7", takenAt: "2026-07-28 09:12", trigger: "OCR approval", size: "1.4 MB" },
  { id: "SNP-298", version: "v6", takenAt: "2026-06-21 09:14", trigger: "Manual verification", size: "1.4 MB" },
  { id: "SNP-277", version: "v5", takenAt: "2026-05-14 15:40", trigger: "Scheduled recalculation", size: "1.3 MB" },
  { id: "SNP-251", version: "v4", takenAt: "2026-04-02 11:02", trigger: "Imaging import", size: "1.3 MB" },
  { id: "SNP-220", version: "v3", takenAt: "2026-02-10 08:25", trigger: "Plan update", size: "1.2 MB" },
];

export interface PredictionRun {
  id: string;
  date: string;
  twinVersion: string;
  model: string;
  survival: number;
  recurrence: number;
  response: string;
  confidence: number;
  status: "Complete" | "Low confidence" | "Superseded";
}

export const predictionHistory: PredictionRun[] = [
  { id: "PR-5120", date: "2026-07-28", twinVersion: "v7", model: "twin-v2.4", survival: 88, recurrence: 17, response: "Likely responder", confidence: 91, status: "Complete" },
  { id: "PR-5044", date: "2026-06-21", twinVersion: "v6", model: "twin-v2.4", survival: 86, recurrence: 19, response: "Likely responder", confidence: 86, status: "Superseded" },
  { id: "PR-4980", date: "2026-05-14", twinVersion: "v5", model: "twin-v2.3", survival: 84, recurrence: 22, response: "Partial response", confidence: 74, status: "Low confidence" },
  { id: "PR-4901", date: "2026-04-02", twinVersion: "v4", model: "twin-v2.3", survival: 82, recurrence: 24, response: "Partial response", confidence: 81, status: "Superseded" },
  { id: "PR-4822", date: "2026-02-10", twinVersion: "v3", model: "twin-v2.2", survival: 79, recurrence: 27, response: "Uncertain", confidence: 68, status: "Low confidence" },
];

export const confidenceTrend = [
  { date: "Feb", confidence: 68 },
  { date: "Apr", confidence: 81 },
  { date: "May", confidence: 74 },
  { date: "Jun", confidence: 86 },
  { date: "Jul", confidence: 91 },
];

export interface SimulationRun {
  id: string;
  date: string;
  patient: string;
  patientId: string;
  twinVersion: string;
  model: string;
  selected: string;
  compared: string[];
  decision: "Promoted to plan" | "Under review" | "Rejected";
  decidedBy: string;
  notes: string;
  survival: number;
  response: number;
  confidence: number;
}

export const simulationRuns: SimulationRun[] = [
  {
    id: "SIM-4412",
    date: "2026-06-30",
    patient: "Amelia Hart",
    patientId: "PT-1000",
    twinVersion: "v7",
    model: "twin-v2.4",
    selected: "AC-T + Trastuzumab",
    compared: ["AC-T + Trastuzumab", "Endocrine only", "Neoadjuvant chemo", "Surgery + radiotherapy"],
    decision: "Promoted to plan",
    decidedBy: "Dr. Sarah Whitmore",
    notes: "Best survival/side-effect balance. Cardiac monitoring every 3 cycles.",
    survival: 86,
    response: 84,
    confidence: 91,
  },
  {
    id: "SIM-4380",
    date: "2026-05-14",
    patient: "Amelia Hart",
    patientId: "PT-1000",
    twinVersion: "v5",
    model: "twin-v2.3",
    selected: "Endocrine only",
    compared: ["Endocrine only", "AC-T + Trastuzumab"],
    decision: "Under review",
    decidedBy: "—",
    notes: "Considered for de-escalation; awaiting Ki-67 confirmation.",
    survival: 74,
    response: 68,
    confidence: 74,
  },
  {
    id: "SIM-4321",
    date: "2026-03-08",
    patient: "Noor Rahman",
    patientId: "PT-1001",
    twinVersion: "v4",
    model: "twin-v2.3",
    selected: "Neoadjuvant chemo",
    compared: ["Neoadjuvant chemo", "Surgery first"],
    decision: "Promoted to plan",
    decidedBy: "Dr. Luis Alvarez",
    notes: "Downstaging before breast-conserving surgery.",
    survival: 81,
    response: 77,
    confidence: 83,
  },
];

export const documentLinks = {
  twinVersion: "v7",
  prediction: "PR-5120",
  report: "RPT-2214",
};

export const documentTimeline = [
  { date: "2026-06-21 09:14", title: "Verified by doctor", detail: "Dr. Sarah Whitmore approved 10 extracted fields", kind: "note" as const },
  { date: "2026-06-20 18:02", title: "OCR re-extraction", detail: "Pipeline v2.4 re-parsed the document", kind: "scan" as const },
  { date: "2026-06-20 17:40", title: "Uploaded", detail: "R. Mensah (Radiology) uploaded the original PDF", kind: "treatment" as const },
];

export interface SavedReport {
  id: string;
  title: string;
  patient: string;
  patientId: string;
  type: "Clinical summary" | "Tumor board packet" | "Model audit" | "Cohort summary";
  created: string;
  version: number;
  status: "Final" | "Draft" | "Archived";
  downloads: number;
}

export const savedReports: SavedReport[] = [
  { id: "RPT-2214", title: "Clinical decision support report", patient: "Amelia Hart", patientId: "PT-1000", type: "Clinical summary", created: "2026-07-30", version: 3, status: "Final", downloads: 12 },
  { id: "RPT-2190", title: "Tumor board packet — July", patient: "Amelia Hart", patientId: "PT-1000", type: "Tumor board packet", created: "2026-07-12", version: 2, status: "Final", downloads: 8 },
  { id: "RPT-2155", title: "Endocrine de-escalation review", patient: "Noor Rahman", patientId: "PT-1001", type: "Clinical summary", created: "2026-06-28", version: 1, status: "Draft", downloads: 1 },
  { id: "RPT-2101", title: "Model performance audit Q2", patient: "—", patientId: "—", type: "Model audit", created: "2026-06-02", version: 4, status: "Archived", downloads: 21 },
  { id: "RPT-2044", title: "Cohort summary — May", patient: "—", patientId: "—", type: "Cohort summary", created: "2026-05-31", version: 1, status: "Final", downloads: 5 },
];

export const reportVersions = [
  { version: 3, date: "2026-07-30 10:04", author: "Dr. Sarah Whitmore", note: "Added simulation SIM-4412 comparison" },
  { version: 2, date: "2026-07-14 16:20", author: "Dr. Sarah Whitmore", note: "Refreshed predictions to twin v6" },
  { version: 1, date: "2026-06-30 08:45", author: "OncoTwin generator", note: "Initial generation" },
];

export const downloadHistory = [
  { id: "DL-88", report: "RPT-2214", format: "PDF", by: "Dr. Sarah Whitmore", at: "2026-07-30 10:12" },
  { id: "DL-87", report: "RPT-2214", format: "CSV", by: "Dr. Luis Alvarez", at: "2026-07-30 09:55" },
  { id: "DL-86", report: "RPT-2190", format: "PDF", by: "Tumor board", at: "2026-07-12 14:02" },
  { id: "DL-85", report: "RPT-2101", format: "PDF", by: "Admin", at: "2026-06-03 08:31" },
];

/** Extended clinical timeline events beyond the base patient timeline. */
export const systemTimelineEvents = [
  { date: "2026-07-28", title: "Digital twin v7 created", detail: "Twin recalculated after verified MRI extraction", kind: "note" as const },
  { date: "2026-07-28", title: "Prediction PR-5120 generated", detail: "twin-v2.4 · 91% confidence · 88% 5-year survival", kind: "note" as const },
  { date: "2026-06-30", title: "Simulation SIM-4412 run", detail: "4 scenarios compared · AC-T + Trastuzumab promoted", kind: "treatment" as const },
  { date: "2026-06-21", title: "OCR verification approved", detail: "10 fields verified by Dr. Sarah Whitmore", kind: "scan" as const },
  { date: "2026-06-20", title: "Document uploaded", detail: "MRI_Breast_2026_06.pdf (8.2 MB) added to Document Center", kind: "scan" as const },
  { date: "2026-06-18", title: "Doctor review recorded", detail: "Dr. Sarah Whitmore reviewed the treatment response", kind: "note" as const },
  { date: "2026-05-14", title: "Digital twin v5 created", detail: "Cycle 3 chemotherapy exposure ingested", kind: "note" as const },
];
