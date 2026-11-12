/**
 * Service layer — the single place the UI talks to "the backend".
 *
 * Every method: (1) is typed by a contract in `contracts.ts`, (2) declares its
 * endpoint in `endpoints.ts`, and (3) calls the real API through `apiRequest`.
 * There are no fixtures: with no API configured a call fails with a clear error.
 */
import { apiRequest, ApiError, USING_MOCKS } from "@/services/api-client";
import { endpoints } from "@/services/endpoints";
import type {
  AdminService,
  AnalyticsService,
  AppointmentService,
  AuthService,
  DocumentService,
  NotificationService,
  OcrService,
  PatientService,
  PredictionService,
  ReportService,
  ResearchService,
  SimulationService,
  TreatmentService,
  TwinDetail,
  TwinListEntry,
  TwinService,
  UserService,
} from "@/services/contracts";
import type {
  AccuracyResult,
  Appointment,
  AuthSession,
  AuthUser,
  CohortAnalytics,
  DashboardAnalytics,
  DocumentDownload,
  DocumentLinks,
  DocumentPreview,
  DocumentRecord,
  ExplainabilityResult,
  ExportFormat,
  MutationResult,
  OcrExtraction,
  Patient,
  PatientInput,
  PredictionRun,
  ReportDetail,
  SavedReport,
  Scenario,
  SimulationRun,
  TimelineEvent,
  TumorSizePoint,
  PrognosisResult,
  SurvivalEstimate,
} from "@/types/models";

export { USING_MOCKS };
export { endpoints };
export * from "@/services/contracts";

/* ------------------------------------------------------------------ */
/* Auth                                                                 */
/* ------------------------------------------------------------------ */
export const authService: AuthService = {
  login: (credentials) =>
    apiRequest<AuthSession>(endpoints.auth.login, { method: "POST", body: credentials }),
  register: (payload) =>
    apiRequest(endpoints.auth.register, { method: "POST", body: payload }),
  logout: () =>
    apiRequest(endpoints.auth.logout, { method: "POST" }),
  refresh: () =>
    apiRequest<AuthSession>(endpoints.auth.refresh, { method: "POST" }),
  forgotPassword: (email) =>
    apiRequest(endpoints.auth.forgotPassword, { method: "POST", body: { email } }),
  resetPassword: (payload) =>
    apiRequest(endpoints.auth.resetPassword, { method: "POST", body: payload }),
  me: () =>
    apiRequest<AuthUser>(endpoints.auth.me),
};

/* ------------------------------------------------------------------ */
/* Users (profile)                                                      */
/* ------------------------------------------------------------------ */
export const userService: UserService = {
  updateProfile: (payload) =>
    apiRequest<AuthUser>(endpoints.users.updateProfile, { method: "PATCH", body: payload }),
};

/* ------------------------------------------------------------------ */
/* Patients                                                             */
/* ------------------------------------------------------------------ */
export const patientService: PatientService = {
  list: (query) =>
    apiRequest<Patient[]>(endpoints.patients.list, { query: query as never }),
  get: (id) =>
    apiRequest<Patient | undefined>(endpoints.patients.detail(id)),
  create: (payload: PatientInput) =>
    apiRequest(endpoints.patients.create, { method: "POST", body: payload }),
  update: (id, payload) =>
    apiRequest(endpoints.patients.update(id), { method: "PATCH", body: payload }),
  remove: (id) =>
    apiRequest(endpoints.patients.remove(id), { method: "DELETE" }),
  labs: (patientId) =>
    apiRequest(endpoints.patients.labs(patientId)),
  imaging: (patientId) =>
    apiRequest(endpoints.patients.imaging(patientId)),
  timeline: (patientId) =>
    apiRequest<TimelineEvent[]>(endpoints.patients.timeline(patientId)),
};

/* ------------------------------------------------------------------ */
/* Digital twins                                                        */
/* ------------------------------------------------------------------ */
export const twinService: TwinService = {
  list: () =>
    apiRequest<TwinListEntry[]>(endpoints.twins.list),
  get: (patientId) =>
    apiRequest<TwinDetail>(endpoints.twins.detail(patientId)),
  versions: (patientId) =>
    apiRequest(endpoints.twins.versions(patientId)),
  snapshots: (patientId) =>
    apiRequest(endpoints.twins.snapshots(patientId)),
  resync: (patientId) =>
    apiRequest(endpoints.twins.resync(patientId), { method: "POST" }),
  restore: (patientId, version) =>
    apiRequest(endpoints.twins.restore(patientId, version), { method: "POST" }),
  archive: (patientId) =>
    apiRequest(endpoints.twins.archive(patientId), { method: "POST" }),
};

/* ------------------------------------------------------------------ */
/* Predictions                                                          */
/* ------------------------------------------------------------------ */
export const predictionService: PredictionService = {
  forPatient: (patientId) =>
    apiRequest<PredictionRun | null>(endpoints.predictions.forPatient(patientId)),
  history: (patientId) =>
    apiRequest(endpoints.predictions.history(patientId)),
  confidenceTrend: (patientId) =>
    apiRequest(endpoints.predictions.confidenceTrend(patientId)),
  prognosis: (patientId) =>
    apiRequest<PrognosisResult>(endpoints.predictions.prognosis(patientId)),
  progression: (patientId) =>
    apiRequest<TumorSizePoint[]>(endpoints.predictions.progression(patientId)),
  explain: (patientId) =>
    apiRequest<ExplainabilityResult>(endpoints.predictions.explain(patientId)),
  run: (patientId) =>
    apiRequest(endpoints.predictions.run, { method: "POST", body: { patientId } }),
};

/* ------------------------------------------------------------------ */
/* Simulations                                                          */
/* ------------------------------------------------------------------ */
export const simulationService: SimulationService = {
  list: (patientId) =>
    apiRequest<SimulationRun[]>(endpoints.simulations.list, {
          query: (patientId ? { patientId } : undefined) as never,
        }),
  get: (id) =>
    apiRequest<SimulationRun | undefined>(endpoints.simulations.detail(id)),
  // Reads the patient's newest recorded run and returns the scenarios stored
  // on it. Previously this fetched the runs list and typed it as Scenario[],
  // which was simply the wrong shape.
  scenarios: async (patientId) => {
    const runs = await simulationService.list(patientId);
    return (runs[0]?.scenarios ?? []) as Scenario[];
  },
  run: (patientId, draft) =>
    apiRequest(endpoints.simulations.run, { method: "POST", body: { patientId, ...draft } }),
  save: (patientId, draft) =>
    apiRequest(endpoints.simulations.save, { method: "POST", body: { patientId, ...draft } }),
  duplicate: (id) =>
    apiRequest(endpoints.simulations.duplicate(id), { method: "POST" }),
  promote: (id, notes, selectedScenario) =>
    apiRequest(endpoints.simulations.promote(id), {
          method: "POST",
          body: { notes, ...(selectedScenario ? { selectedScenario } : {}) },
        }),
};

/* ------------------------------------------------------------------ */
/* Documents & OCR                                                      */
/* ------------------------------------------------------------------ */
export const documentService: DocumentService = {
  list: (query) =>
    apiRequest<DocumentRecord[]>(endpoints.documents.list, { query: query as never }),
  get: (id) =>
    apiRequest<DocumentRecord | undefined>(endpoints.documents.detail(id)),
  upload: ({ file, patientId, category }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("patientId", patientId);
    if (category) formData.append("category", category);
    return apiRequest(endpoints.documents.upload, { method: "POST", body: formData });
  },
  versions: (id) =>
    apiRequest(endpoints.documents.versions(id)),
  timeline: (id) =>
    apiRequest(endpoints.documents.timeline(id)),
  links: (id) =>
    apiRequest<DocumentLinks>(endpoints.documents.links(id)),
  download: (id) =>
    apiRequest<DocumentDownload>(endpoints.documents.download(id)),
  preview: (id) =>
    apiRequest<DocumentPreview>(endpoints.documents.preview(id)),
};

export const ocrService: OcrService = {
  extract: (documentId) =>
    apiRequest(endpoints.ocr.extract(documentId), { method: "POST" }),
  fields: (documentId) =>
    apiRequest(endpoints.ocr.fields(documentId)),
  approve: (documentId, fields) =>
    apiRequest(endpoints.ocr.approve(documentId), { method: "POST", body: { fields } }),
  reject: (documentId, reason) =>
    apiRequest(endpoints.ocr.reject(documentId), { method: "POST", body: { reason } }),
};

/* ------------------------------------------------------------------ */
/* Reports                                                              */
/* ------------------------------------------------------------------ */
export const reportService: ReportService = {
  list: (patientId) =>
    apiRequest(endpoints.reports.list, { query: (patientId ? { patientId } : undefined) as never }),
  get: (id) =>
    apiRequest<ReportDetail>(endpoints.reports.detail(id)),
  versions: (id) =>
    apiRequest(endpoints.reports.versions(id)),
  downloads: (reportId) =>
    apiRequest(endpoints.reports.downloads, { query: (reportId ? { reportId } : undefined) as never }),
  generate: (patientId, type = "Clinical summary") =>
    apiRequest(endpoints.reports.generate, { method: "POST", body: { patientId, type } }),
  export: (reportId, format: ExportFormat) =>
    apiRequest(endpoints.reports.export(reportId), { method: "POST", body: { format } }),
};

/* ------------------------------------------------------------------ */
/* Care coordination                                                    */
/* ------------------------------------------------------------------ */
export const appointmentService: AppointmentService = {
  list: () =>
    apiRequest(endpoints.appointments.list),
  create: (payload) =>
    apiRequest(endpoints.appointments.create, { method: "POST", body: payload }),
  cancel: (id) =>
    apiRequest(endpoints.appointments.cancel(id), { method: "POST" }),
};

export const treatmentService: TreatmentService = {
  plan: (patientId) =>
    apiRequest(endpoints.treatment.plan(patientId)),
};

export const notificationService: NotificationService = {
  list: () =>
    apiRequest(endpoints.notifications.list),
  patientList: () =>
    apiRequest(endpoints.notifications.list, { query: { audience: "patient" } }),
  markRead: (id) =>
    apiRequest(endpoints.notifications.markRead(id), { method: "POST" }),
  markAllRead: () =>
    apiRequest(endpoints.notifications.markAllRead, { method: "POST" }),
};

/* ------------------------------------------------------------------ */
/* Analytics, admin, research                                           */
/* ------------------------------------------------------------------ */
/**
 * Analytics.
 *
 * The mock branches below are shaped like the real responses rather than the
 * loose `MetricPoint[]` they used to return — the previous fallbacks handed
 * back an unrelated fixture array (patient growth for the whole dashboard),
 * which typechecked only because the contract was `MetricPoint[]`.
 */
export const analyticsService: AnalyticsService = {
  dashboard: () =>
    apiRequest<DashboardAnalytics>(endpoints.analytics.dashboard),
  cohort: () =>
    apiRequest<CohortAnalytics>(endpoints.analytics.cohort),
  accuracy: () =>
    apiRequest<AccuracyResult>(endpoints.analytics.accuracy),
};

export const adminService: AdminService = {
  hospitals: () =>
    apiRequest(endpoints.admin.hospitals),
  doctors: () =>
    apiRequest(endpoints.admin.doctors),
  departments: () =>
    apiRequest(endpoints.admin.departments),
  users: () =>
    apiRequest(endpoints.admin.users),
  auditLogs: () =>
    apiRequest(endpoints.admin.audit),
  permissions: () =>
    apiRequest(endpoints.admin.permissions),
};

export const researchService: ResearchService = {
  models: () =>
    apiRequest(endpoints.research.models),
  datasets: () =>
    apiRequest(endpoints.research.datasets),
  trainingRuns: () =>
    apiRequest(endpoints.research.training),
  modelVersions: () =>
    apiRequest(endpoints.research.versions),
  performance: () =>
    apiRequest(endpoints.research.performance),
};

export const services = {
  auth: authService,
  users: userService,
  patients: patientService,
  twins: twinService,
  predictions: predictionService,
  simulations: simulationService,
  documents: documentService,
  ocr: ocrService,
  reports: reportService,
  appointments: appointmentService,
  treatment: treatmentService,
  notifications: notificationService,
  analytics: analyticsService,
  admin: adminService,
  research: researchService,
};
