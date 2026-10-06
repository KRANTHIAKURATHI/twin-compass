/**
 * Service contracts.
 *
 * Each interface is the typed boundary between the UI and the backend. The
 * mock adapters in `index.ts` implement these today; a FastAPI/Supabase
 * adapter can implement the same interfaces later with zero UI changes.
 */
import type {
  AccuracyResult,
  Appointment,
  AuditLogEntry,
  AuthSession,
  AuthUser,
  CohortAnalytics,
  ConfidencePoint,
  Credentials,
  DashboardAnalytics,
  Dataset,
  Department,
  DocumentDownload,
  DocumentLinks,
  DocumentPreview,
  DocumentRecord,
  DocumentVersion,
  DoctorProfile,
  DownloadRecord,
  ExplainabilityResult,
  ExportFormat,
  Hospital,
  ImagingStudy,
  LabResult,
  ListQuery,
  MLModel,
  ModelVersion,
  MutationResult,
  NotificationItem,
  OcrExtraction,
  OcrField,
  Patient,
  PatientInput,
  PerformancePoint,
  PermissionRow,
  PlatformUser,
  PredictionRun,
  ReportDetail,
  ReportVersion,
  SavedReport,
  Scenario,
  RunSimulationInput,
  ScenarioDraft,
  SimulationRun,
  TimelineEvent,
  TrainingRun,
  TreatmentPlan,
  TumorSizePoint,
  TwinSnapshot,
  TwinVersion,
} from "@/types/models";

export interface AuthService {
  login(credentials: Credentials): Promise<AuthSession>;
  register(payload: Credentials & { name: string }): Promise<MutationResult<AuthUser>>;
  logout(): Promise<MutationResult>;
  /** Exchanges the httpOnly refresh cookie for a new access token. */
  refresh(): Promise<AuthSession>;
  forgotPassword(email: string): Promise<MutationResult>;
  resetPassword(payload: { token: string; password: string }): Promise<MutationResult>;
  me(): Promise<AuthUser>;
}

export interface UserService {
  // PATCH /users/profile — self-editable, non-privileged fields only (no
  // email/role change here; those need separate, more sensitive flows).
  updateProfile(payload: {
    name?: string;
    title?: string;
    hospital?: string;
    department?: string;
    avatarUrl?: string;
  }): Promise<AuthUser>;
}

export interface PatientService {
  list(query?: ListQuery): Promise<Patient[]>;
  get(id: string): Promise<Patient | undefined>;
  create(payload: PatientInput): Promise<MutationResult<Patient>>;
  update(id: string, payload: Partial<PatientInput>): Promise<MutationResult<Patient>>;
  remove(id: string): Promise<MutationResult>;
  labs(patientId: string): Promise<LabResult[]>;
  imaging(patientId: string): Promise<ImagingStudy[]>;
  timeline(patientId: string): Promise<TimelineEvent[]>;
}

/** One row of the digital-twin list — a patient plus its active version. */
export interface TwinListEntry {
  patientId: string;
  patient: string;
  /** null when the patient has no twin_versions row yet. */
  version: string | null;
  status: string;
  createdAt: string | null;
  author: string;
  summary: string;
  tumorSizeMm: number | null;
  survival: number | null;
  risk: string | null;
  model: string;
}

export interface TwinDetail {
  patientId: string;
  patient: string;
  twinStatus: string;
  active: TwinVersion | null;
  versions: TwinVersion[];
}

export interface TwinService {
  list(): Promise<TwinListEntry[]>;
  get(patientId: string): Promise<TwinDetail>;
  versions(patientId: string): Promise<TwinVersion[]>;
  snapshots(patientId: string): Promise<TwinSnapshot[]>;
  resync(patientId: string): Promise<MutationResult>;
  restore(patientId: string, version: string): Promise<MutationResult>;
  archive(patientId: string): Promise<MutationResult>;
}

export interface PredictionService {
  /** null — not undefined — when no run has ever been recorded. */
  forPatient(patientId: string): Promise<PredictionRun | null>;
  history(patientId: string): Promise<PredictionRun[]>;
  confidenceTrend(patientId: string): Promise<ConfidencePoint[]>;
  /** Measured tumour size per twin version. Empty until versions exist. */
  progression(patientId: string): Promise<TumorSizePoint[]>;
  explain(patientId: string): Promise<ExplainabilityResult>;
  run(patientId: string): Promise<MutationResult<PredictionRun>>;
}

export interface SimulationService {
  /** Filtered server-side when `patientId` is given. */
  list(patientId?: string): Promise<SimulationRun[]>;
  get(id: string): Promise<SimulationRun | undefined>;
  /**
   * Scenarios recorded by this patient's most recent run, or `[]` if they have
   * never had one. Deliberately does not invent scenarios for an unrun
   * patient — the simulator shows an empty state and a Run button instead.
   */
  scenarios(patientId: string): Promise<Scenario[]>;
  /**
   * Executes a run and returns the record it created. `id` is the new
   * `simulation_runs` row — the simulator needs it to promote the selected
   * scenario, and without it the Promote button had nothing to act on.
   */
  run(
    patientId: string,
    draft?: RunSimulationInput,
  ): Promise<{ id: string; patientId: string; scenarios: Scenario[] }>;
  save(patientId: string, draft: ScenarioDraft): Promise<MutationResult<SimulationRun>>;
  duplicate(id: string): Promise<MutationResult<SimulationRun>>;
  promote(id: string, notes?: string, selectedScenario?: string): Promise<MutationResult>;
}

export interface DocumentService {
  list(query?: ListQuery & { patientId?: string }): Promise<DocumentRecord[]>;
  get(id: string): Promise<DocumentRecord | undefined>;
  upload(payload: {
    file: File;
    patientId: string;
    category?: string;
  }): Promise<MutationResult<DocumentRecord>>;
  versions(id: string): Promise<DocumentVersion[]>;
  timeline(id: string): Promise<TimelineEvent[]>;
  links(id: string): Promise<DocumentLinks>;
  download(id: string): Promise<DocumentDownload>;
  preview(id: string): Promise<DocumentPreview>;
}

export interface OcrService {
  extract(documentId: string): Promise<MutationResult<OcrExtraction>>;
  fields(documentId: string): Promise<OcrExtraction>;
  approve(documentId: string, fields: OcrField[]): Promise<MutationResult<OcrExtraction>>;
  reject(documentId: string, reason?: string): Promise<MutationResult<OcrExtraction>>;
}

export interface ReportService {
  list(patientId?: string): Promise<SavedReport[]>;
  get(id: string): Promise<ReportDetail>;
  versions(id: string): Promise<ReportVersion[]>;
  downloads(reportId?: string): Promise<DownloadRecord[]>;
  generate(patientId: string, type?: string): Promise<MutationResult<SavedReport>>;
  export(reportId: string, format: ExportFormat): Promise<MutationResult<ReportDetail & { format: ExportFormat }>>;
}

export interface AppointmentService {
  list(): Promise<Appointment[]>;
  create(payload: Omit<Appointment, "id" | "status">): Promise<MutationResult<Appointment>>;
  cancel(id: string): Promise<MutationResult>;
}

export interface TreatmentService {
  plan(patientId: string): Promise<TreatmentPlan>;
}

export interface NotificationService {
  list(): Promise<NotificationItem[]>;
  patientList(): Promise<NotificationItem[]>;
  markRead(id: string): Promise<MutationResult>;
  markAllRead(): Promise<MutationResult>;
}

export interface AnalyticsService {
  dashboard(): Promise<DashboardAnalytics>;
  cohort(): Promise<CohortAnalytics>;
  accuracy(): Promise<AccuracyResult>;
}

export interface AdminService {
  hospitals(): Promise<Hospital[]>;
  doctors(): Promise<DoctorProfile[]>;
  departments(): Promise<Department[]>;
  users(): Promise<PlatformUser[]>;
  auditLogs(): Promise<AuditLogEntry[]>;
  permissions(): Promise<PermissionRow[]>;
}

export interface ResearchService {
  models(): Promise<MLModel[]>;
  datasets(): Promise<Dataset[]>;
  trainingRuns(): Promise<TrainingRun[]>;
  modelVersions(): Promise<ModelVersion[]>;
  performance(): Promise<PerformancePoint[]>;
}
