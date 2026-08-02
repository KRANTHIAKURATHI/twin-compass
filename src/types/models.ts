/**
 * OncoTwin domain models.
 *
 * This is the SINGLE source of truth for every entity the frontend exchanges
 * with the backend. Backend teams should treat these interfaces as the API
 * contract (FastAPI pydantic schemas / database rows should serialize to
 * exactly these shapes).
 *
 * Nothing in this file imports from the mock layer — models are transport
 * definitions only.
 */

/* ------------------------------------------------------------------ */
/* Shared primitives                                                    */
/* ------------------------------------------------------------------ */

export type ID = string;
/** ISO-8601 date (YYYY-MM-DD) or datetime string produced by the backend. */
export type ISODate = string;

export type RiskLevel = "low" | "moderate" | "high";
export type ReceptorStatus = "Positive" | "Negative";
export type PatientStatus = "In Treatment" | "Remission" | "Monitoring" | "Critical";
export type TumorStage = "0" | "I" | "II" | "III" | "IV";
export type LifecycleStatus = "Active" | "Superseded" | "Archived" | "Draft";
export type TimelineKind = "diagnosis" | "treatment" | "scan" | "note";

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

export interface ListQuery {
  page?: number;
  pageSize?: number;
  search?: string;
  sort?: string;
  order?: "asc" | "desc";
}

/** Envelope every write endpoint is expected to return. */
export interface MutationResult<T = unknown> {
  ok: boolean;
  data?: T;
  message?: string;
}

/* ------------------------------------------------------------------ */
/* Identity & access                                                    */
/* ------------------------------------------------------------------ */

export type UserRole = "doctor" | "patient" | "researcher" | "admin";

export interface AuthUser {
  id: ID;
  name: string;
  email: string;
  role: UserRole;
  title?: string;
  hospital?: string;
  avatarUrl?: string | null;
}

export interface AuthSession {
  user: AuthUser;
  accessToken: string;
  expiresAt: ISODate;
}

export interface Credentials {
  email: string;
  password: string;
}

/* ------------------------------------------------------------------ */
/* Clinical core                                                        */
/* ------------------------------------------------------------------ */

export interface TimelineEvent {
  date: ISODate;
  title: string;
  detail: string;
  kind: TimelineKind;
}

export interface PatientReportRef {
  name: string;
  type: string;
  date: ISODate;
  size: string;
}

export interface Patient {
  id: ID;
  name: string;
  age: number;
  gender: string;
  phone: string;
  email: string;
  hospital: string;
  stage: TumorStage;
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
  lastUpdated: ISODate;
  diagnosedOn: ISODate;
  twinStatus: "Synced" | "Recalculating" | "Stale";
  history: string[];
  notes: string;
  timeline: TimelineEvent[];
  reports: PatientReportRef[];
}

/** Write payload for POST /patients and PATCH /patients/{id}. */
export type PatientInput = Partial<Omit<Patient, "id" | "timeline" | "reports">> & {
  name: string;
};

export interface LabResult {
  date: ISODate;
  panel: string;
  marker: string;
  value: string;
  unit: string;
  range: string;
  flag: "normal" | "low" | "high" | string;
}

export interface ImagingStudy {
  id: ID;
  modality: "MRI" | "CT" | "PET" | "Mammography" | string;
  region: string;
  date: ISODate;
  finding: string;
  radiologist: string;
  status: string;
}

/* ------------------------------------------------------------------ */
/* Digital twin                                                         */
/* ------------------------------------------------------------------ */

export interface TwinVersion {
  version: string;
  createdAt: ISODate;
  status: LifecycleStatus;
  author: string;
  summary: string;
  tumorSizeMm: number;
  survival: number;
  risk: RiskLevel;
  model: string;
}

export interface TwinSnapshot {
  id: ID;
  version: string;
  takenAt: ISODate;
  trigger: string;
  size: string;
}

/* ------------------------------------------------------------------ */
/* Predictions & explainability                                         */
/* ------------------------------------------------------------------ */

export interface PredictionRun {
  id: ID;
  date: ISODate;
  twinVersion: string;
  model: string;
  survival: number;
  recurrence: number;
  response: string;
  confidence: number;
  status: "Complete" | "Low confidence" | "Superseded";
}

export interface ConfidencePoint {
  date: string;
  confidence: number;
}

export interface FeatureImportance {
  feature: string;
  weight: number;
  direction: string;
}

/* ------------------------------------------------------------------ */
/* Simulation                                                           */
/* ------------------------------------------------------------------ */

export interface Scenario {
  id: ID;
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

export interface ScenarioDraft {
  name: string;
  regimen: string;
  dosage: string;
  durationWeeks: number;
  notes: string;
}

export interface SimulationRun {
  id: ID;
  date: ISODate;
  patient: string;
  patientId: ID;
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

/* ------------------------------------------------------------------ */
/* Documents & OCR                                                      */
/* ------------------------------------------------------------------ */

export interface DocumentRecord {
  id: ID;
  name: string;
  category: "MRI" | "CT" | "PET" | "Biopsy" | "Blood" | string;
  patient: string;
  date: ISODate;
  size: string;
  version: number;
  status: "Verified" | "Pending OCR" | "Needs review" | string;
}

export interface DocumentVersion {
  version: number;
  date: ISODate;
  author: string;
  note: string;
}

export interface OcrField {
  field: string;
  value: string;
  confidence: number;
}

export interface OcrExtraction {
  documentId: ID;
  fields: OcrField[];
  model: string;
  extractedAt: ISODate;
}

/* ------------------------------------------------------------------ */
/* Reports                                                              */
/* ------------------------------------------------------------------ */

export interface SavedReport {
  id: ID;
  title: string;
  patient: string;
  patientId: ID;
  type: "Clinical summary" | "Tumor board packet" | "Model audit" | "Cohort summary";
  created: ISODate;
  version: number;
  status: "Final" | "Draft" | "Archived";
  downloads: number;
}

export interface ReportVersion {
  version: number;
  date: ISODate;
  author: string;
  note: string;
}

export interface DownloadRecord {
  id: ID;
  report: ID;
  format: string;
  by: string;
  date: ISODate;
}

export type ExportFormat = "pdf" | "csv";

/* ------------------------------------------------------------------ */
/* Care coordination                                                    */
/* ------------------------------------------------------------------ */

export interface Appointment {
  id: ID;
  title: string;
  doctor: string;
  date: ISODate;
  time: string;
  location: string;
  status: "Confirmed" | "Scheduled" | "Completed" | "Cancelled" | string;
}

export interface TreatmentPlan {
  regimen: string;
  cycle: number;
  totalCycles: number;
  startedOn: ISODate;
  nextDose: ISODate;
  adherence: number;
  sideEffects: { name: string; grade: string; advice: string }[];
  medications: { name: string; dose: string; schedule: string }[];
}

export interface NotificationItem {
  id: ID;
  title: string;
  body: string;
  time: string;
  unread: boolean;
  type?: string;
}

/* ------------------------------------------------------------------ */
/* Administration                                                       */
/* ------------------------------------------------------------------ */

export interface Hospital {
  id: ID;
  name: string;
  city: string;
  beds: number;
  doctors: number;
  patients: number;
  status: string;
}

export interface DoctorProfile {
  id: ID;
  name: string;
  dept: string;
  hospital: string;
  patients: number;
  status: string;
}

export interface Department {
  id: ID;
  name: string;
  head: string;
  staff: number;
  activeCases: number;
}

export interface PlatformUser {
  id: ID;
  name: string;
  email: string;
  role: string;
  lastActive: string;
  status: string;
}

export interface AuditLogEntry {
  id: ID;
  time: ISODate;
  actor: string;
  action: string;
  target: string;
  ip: string;
}

export interface PermissionRow {
  capability: string;
  doctor: boolean;
  patient: boolean;
  technician: boolean;
  admin: boolean;
}

/* ------------------------------------------------------------------ */
/* Research                                                             */
/* ------------------------------------------------------------------ */

export interface MLModel {
  id: ID;
  name: string;
  version: string;
  task: string;
  auc: number;
  status: string;
}

export interface Dataset {
  id: ID;
  name: string;
  records: number;
  modalities: string;
  updated: ISODate;
}

export interface TrainingRun {
  id: ID;
  model: string;
  started: ISODate;
  duration: string;
  epochs: number;
  loss: number;
  status: string;
}

export interface ModelVersion {
  version: string;
  released: ISODate;
  auc: number;
  notes: string;
  stage: string;
}

export interface PerformancePoint {
  month: string;
  auc: number;
  precision: number;
  recall: number;
}

/* ------------------------------------------------------------------ */
/* Analytics                                                            */
/* ------------------------------------------------------------------ */

export interface MetricPoint {
  [key: string]: string | number;
}
