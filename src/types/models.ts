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

/**
 * A patient record.
 *
 * Clinical fields are nullable on purpose: the API returns null for anything
 * the record does not carry, so the UI can render "—" instead of inventing a
 * measurement. Anything that reads one of these must handle null.
 */
export interface Patient {
  id: ID;
  name: string;
  age: number | null;
  gender: string;
  phone: string;
  email: string;
  hospital: string;
  stage: TumorStage | null;
  tumorSizeMm: number | null;
  erStatus: ReceptorStatus | null;
  prStatus: ReceptorStatus | null;
  her2Status: ReceptorStatus | null;
  ki67: number | null;
  grade: 1 | 2 | 3 | null;
  nodesInvolved: number | null;
  currentTreatment: string;
  status: PatientStatus | null;
  risk: RiskLevel | null;
  survivalProbability: number | null;
  lastUpdated: ISODate;
  diagnosedOn: ISODate;
  twinStatus: "Synced" | "Recalculating" | "Stale" | null;
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
  /** Null when the run recorded no figure — distinct from a predicted 0%. */
  survival: number | null;
  /** Complement of `survival`, so null whenever that is. */
  recurrence: number | null;
  /**
   * The twin's risk band at the time of the run. Stored in a column named
   * `response` for historical reasons; it has never held a treatment response.
   */
  riskBand: RiskLevel | null;
  /** Null when the run recorded no confidence — distinct from 0%. */
  confidence: number | null;
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
  /** Pearson r against recorded survival across the cohort. */
  correlation?: number;
  /** This patient's own value for the factor, for context next to the weight. */
  patientValue?: string | number | null;
}

/**
 * What the explainability panel actually receives.
 *
 * `basis: "cohort"` is not decoration — these weights describe correlations
 * across the patient cohort, not an attribution of one prediction, and the
 * panel must say so. `reliability` is "indicative" for small cohorts where a
 * coefficient can hit 1.0 by coincidence.
 */
export interface ExplainabilityResult {
  basis: "cohort";
  cohortSize: number;
  reliability: "reasonable" | "indicative" | "insufficient";
  factors: FeatureImportance[];
  caveat: string;
}

/** One measured tumour-size reading taken from a twin version. */
export interface TumorSizePoint {
  version: string;
  date: ISODate;
  tumorSizeMm: number;
  survival: number;
}

/* ------------------------------------------------------------------ */
/* Simulation                                                           */
/* ------------------------------------------------------------------ */

/**
 * One treatment scenario in a comparison.
 *
 * Outcome measures are nullable because predicting them needs
 * treatment-response and toxicity data this deployment does not hold. The API
 * returns null rather than a plausible-looking percentage, and the UI renders
 * an em dash. Only the regimen label, the patient's recorded risk band and
 * their recorded survival probability are ever populated today.
 */
export interface Scenario {
  id: ID;
  name: string;
  regimen: string;
  predictedResponse: number | null;
  tumorChange: number | null;
  risk: RiskLevel | null;
  confidence: number | null;
  survival5y: number | null;
  sideEffectRisk: number | null;
  recoveryWeeks: number | null;
  recommended: boolean;
  /** Tumour diameter the projection started from — the twin's, in mm. */
  baselineSizeMm?: number | null;
  /** Projected tumour diameter at the end of the regimen, in mm. */
  projectedSizeMm?: number | null;
  /** Number of cycles the projection ran over. */
  cycles?: number | null;
  /**
   * Where this card's numbers came from, or - when they are all null - why
   * there are none. Rendered under every card so a reader never has to guess
   * whether a figure was computed, measured, or simply absent.
   */
  basis?: string | null;
  provenance?: ScenarioProvenance | null;
}

export interface ScenarioProvenance {
  kind: string;
  subtype: string | null;
  regimenFamily: string | null;
  source: string | null;
  /** False until a clinician signs off on the regimen parameter table. */
  parametersVerified: boolean;
  model: string | null;
  unavailableReason: string | null;
  /** The regimen the run was projected for; absent on runs recorded before it was persisted. */
  requestedRegimen?: string | null;
  durationWeeks?: number | null;
}

export interface ScenarioDraft {
  name: string;
  regimen: string;
  dosage: string;
  durationWeeks: number;
  notes: string;
}

/**
 * Run request body besides `patientId`. Every field is optional: with no
 * regimen the backend uses the patient's recorded one. `selectedScenario` is a
 * scenario name; absent or unknown means the first scenario.
 */
export type RunSimulationInput = Partial<ScenarioDraft> & { selectedScenario?: string };

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
  /** The scenarios as recorded at run time, so a run can be reopened as-run. */
  scenarios: Scenario[];
}

/* ------------------------------------------------------------------ */
/* Documents & OCR                                                      */
/* ------------------------------------------------------------------ */

export interface DocumentRecord {
  id: ID;
  name: string;
  category: "MRI" | "CT" | "PET" | "Biopsy" | "Blood" | string;
  patient: string;
  patientId: ID;
  date: ISODate;
  size: string;
  sizeBytes: number;
  mimeType: string;
  version: number;
  status: "Verified" | "Pending OCR" | "Needs review" | string;
}

export interface DocumentVersion {
  version: number;
  date: ISODate;
  author: string;
  note: string;
}

export interface DocumentLinks {
  patientId: ID;
  patient: string;
  twinVersion: string | null;
  prediction: string | null;
  report: string | null;
}

export interface DocumentPreview {
  available: boolean;
  mimeType: string;
  url: string | null;
}

export interface DocumentDownload {
  url: string;
  expiresIn: number;
}

export type OcrFieldStatus = "pending" | "approved" | "rejected";

export interface OcrField {
  /** Machine key matching a patient column (e.g. "tumor_size_mm") — used when approving. */
  field: string;
  /** Human-readable label for display (e.g. "Tumor size (mm)"). */
  label?: string;
  value: string | null;
  /** Omitted/null when the OCR provider does not supply a confidence score — never fabricated. */
  confidence: number | null;
  status?: OcrFieldStatus;
}

export type OcrExtractionStatus = "Extracted" | "Approved" | "Rejected";

export interface OcrExtraction {
  documentId: ID;
  patientId: ID;
  status: OcrExtractionStatus;
  fields: OcrField[];
  /** Null until a real OCR provider is configured server-side. */
  model: string | null;
  extractedAt: ISODate;
  reviewedBy?: string | null;
  reviewedAt?: ISODate | null;
  rejectReason?: string | null;
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
  at: ISODate;
}

export type ExportFormat = "pdf" | "csv";

/** Prediction section of a report snapshot — honest about model absence. */
export type ReportPrediction =
  | {
      basis: "measured";
      date: ISODate;
      twinVersion: string | null;
      model: string | null;
      survival: number | null;
      recurrence: number | null;
      riskBand: string | null;
      confidence: number | null;
    }
  | { basis: "none"; caveat: string };

export interface ReportSimulationRun {
  id: ID;
  date: ISODate;
  selected: string | null;
  decision: string | null;
  survival: number | null;
  response: number | null;
  confidence: number | null;
}

export interface ReportContent {
  patient: {
    name: string;
    patientId: string;
    age: number | null;
    stage: string | null;
    tumorSizeMm: number | null;
    erStatus: string | null;
    prStatus: string | null;
    her2Status: string | null;
    currentTreatment: string | null;
    status: string | null;
  };
  digitalTwin: {
    version: string;
    createdAt: ISODate;
    status: string;
    tumorSizeMm: number | null;
    survival: number | null;
    risk: string | null;
  } | null;
  prediction: ReportPrediction;
  simulations: {
    basis: "prototype";
    caveat: string;
    runs: ReportSimulationRun[];
  };
  documents: { count: number };
  timeline: TimelineEvent[];
  notes: string | null;
  generationNote?: string;
}

export interface ReportDetail extends SavedReport {
  content: ReportContent;
}

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

/**
 * A headline number on the dashboard.
 *
 * `value` is nullable on purpose: "no patient has a recorded survival
 * probability yet" is a real state, and rendering it as 0% would be a claim
 * the data does not support. Tiles read null as "—".
 */
export interface DashboardStat {
  key: string;
  label: string;
  value: number | null;
  format: "count" | "percent";
}

/** The registered model, as recorded in `ml_models`. */
export interface ModelSummary {
  name: string;
  version: string;
  auc: number;
  task?: string;
  status: string;
}

/**
 * Validation performance. `seriesKind` matters: the stored series is
 * cross-validation folds, so charting it as a time trend would imply the model
 * improved over time, which was never measured.
 */
export interface AccuracyResult {
  series: Array<{ label: string; auc: number; precision: number; recall: number }>;
  seriesKind: "cross-validation-folds";
  model: ModelSummary | null;
}

export interface RiskSlice {
  key: string;
  name: string;
  value: number;
}

export interface TreatmentComparisonRow {
  treatment: string;
  response: number;
  recurrence: number;
  runs: number;
}

export interface ActivityEntry {
  title: string;
  detail: string;
  time: ISODate;
  actorRole: string;
}

export interface FollowUpEntry {
  patient: string;
  id: string;
  when: string;
  type: string;
}

export interface DashboardAnalytics {
  stats: DashboardStat[];
  model: ModelSummary | null;
  patientGrowth: Array<{ month: string; patients: number; twins: number }>;
  riskDistribution: RiskSlice[];
  stageDistribution: Array<{ stage: string; count: number }>;
  treatmentComparison: TreatmentComparisonRow[];
  accuracy: AccuracyResult;
  recentActivity: ActivityEntry[];
  followUps: FollowUpEntry[];
}

/**
 * Two anchor points per risk band, not a curve: baseline (true by definition)
 * and the probability actually recorded. This database holds no year-by-year
 * outcome data, so the intermediate years cannot be drawn honestly.
 */
export interface SurvivalByRisk {
  points: Array<Record<string, string | number | null>>;
  cohortSizes: Record<string, number>;
  caveat: string;
}

export interface CohortAnalytics {
  ageDistribution: Array<{ range: string; count: number }>;
  stageDistribution: Array<{ stage: string; count: number }>;
  riskDistribution: RiskSlice[];
  treatmentComparison: TreatmentComparisonRow[];
  survivalByRisk: SurvivalByRisk;
}
