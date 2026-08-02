/**
 * Service contracts.
 *
 * Each interface is the typed boundary between the UI and the backend. The
 * mock adapters in `index.ts` implement these today; a FastAPI/Supabase
 * adapter can implement the same interfaces later with zero UI changes.
 */
import type {
  Appointment,
  AuditLogEntry,
  AuthSession,
  AuthUser,
  ConfidencePoint,
  Credentials,
  Dataset,
  Department,
  DocumentRecord,
  DocumentVersion,
  DoctorProfile,
  DownloadRecord,
  ExportFormat,
  FeatureImportance,
  Hospital,
  ImagingStudy,
  LabResult,
  ListQuery,
  MLModel,
  MetricPoint,
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
  ReportVersion,
  SavedReport,
  Scenario,
  ScenarioDraft,
  SimulationRun,
  TimelineEvent,
  TrainingRun,
  TreatmentPlan,
  TwinSnapshot,
  TwinVersion,
} from "@/types/models";

export interface AuthService {
  login(credentials: Credentials): Promise<AuthSession>;
  register(payload: Credentials & { name: string }): Promise<MutationResult<AuthUser>>;
  logout(): Promise<MutationResult>;
  forgotPassword(email: string): Promise<MutationResult>;
  resetPassword(payload: { token: string; password: string }): Promise<MutationResult>;
  me(): Promise<AuthUser>;
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

export interface TwinService {
  list(): Promise<Patient[]>;
  versions(patientId: string): Promise<TwinVersion[]>;
  snapshots(patientId: string): Promise<TwinSnapshot[]>;
  resync(patientId: string): Promise<MutationResult>;
  restore(patientId: string, version: string): Promise<MutationResult>;
  archive(patientId: string): Promise<MutationResult>;
}

export interface PredictionService {
  forPatient(patientId: string): Promise<PredictionRun | undefined>;
  history(patientId: string): Promise<PredictionRun[]>;
  confidenceTrend(patientId: string): Promise<ConfidencePoint[]>;
  explain(patientId: string): Promise<FeatureImportance[]>;
  run(patientId: string): Promise<MutationResult<PredictionRun>>;
}

export interface SimulationService {
  list(): Promise<SimulationRun[]>;
  get(id: string): Promise<SimulationRun | undefined>;
  scenarios(patientId: string): Promise<Scenario[]>;
  run(patientId: string, draft?: ScenarioDraft): Promise<{ patientId: string; scenarios: Scenario[] }>;
  save(draft: ScenarioDraft): Promise<MutationResult<SimulationRun>>;
  duplicate(id: string): Promise<MutationResult<SimulationRun>>;
  promote(id: string, notes?: string): Promise<MutationResult>;
}

export interface DocumentService {
  list(query?: ListQuery): Promise<DocumentRecord[]>;
  get(id: string): Promise<DocumentRecord | undefined>;
  upload(file: { name: string; size: number; patientId?: string }): Promise<MutationResult<DocumentRecord>>;
  versions(id: string): Promise<DocumentVersion[]>;
  timeline(id: string): Promise<TimelineEvent[]>;
}

export interface OcrService {
  extract(documentId: string): Promise<OcrExtraction>;
  fields(documentId: string): Promise<OcrField[]>;
  approve(documentId: string, fields: OcrField[]): Promise<MutationResult>;
  reject(documentId: string, reason: string): Promise<MutationResult>;
}

export interface ReportService {
  list(): Promise<SavedReport[]>;
  versions(id: string): Promise<ReportVersion[]>;
  downloads(): Promise<DownloadRecord[]>;
  generate(patientId: string): Promise<MutationResult<SavedReport>>;
  export(format: ExportFormat): Promise<MutationResult<{ format: ExportFormat }>>;
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
  dashboard(): Promise<MetricPoint[]>;
  cohort(): Promise<MetricPoint[]>;
  accuracy(): Promise<MetricPoint[]>;
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
