/**
 * Service layer — the single place the UI talks to "the backend".
 *
 * Every method: (1) is typed by a contract in `contracts.ts`, (2) declares its
 * endpoint in `endpoints.ts`, and (3) runs through `withFallback` so it hits
 * the real API as soon as `VITE_API_BASE_URL` is set and otherwise resolves
 * the typed fixtures. No UI change is needed to switch.
 */
import { apiRequest, withFallback, USING_MOCKS } from "@/services/api-client";
import { endpoints } from "@/services/endpoints";
import * as fx from "@/services/fixtures";
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
  TwinService,
} from "@/services/contracts";
import type {
  Appointment,
  AuthSession,
  AuthUser,
  DocumentRecord,
  ExportFormat,
  MutationResult,
  Patient,
  PatientInput,
  SavedReport,
  Scenario,
  SimulationRun,
  TimelineEvent,
} from "@/types/models";

export { USING_MOCKS };
export { endpoints };
export * from "@/services/contracts";

const ok = <T>(data?: T, message?: string): MutationResult<T> => ({ ok: true, data, message });

/* ------------------------------------------------------------------ */
/* Auth                                                                 */
/* ------------------------------------------------------------------ */
export const authService: AuthService = {
  login: (credentials) =>
    withFallback<AuthSession>(
      () => apiRequest(endpoints.auth.login, { method: "POST", body: credentials }),
      () => ({
        user: { ...fx.currentDoctorFixture, email: credentials.email || fx.currentDoctorFixture.email },
        accessToken: "mock-access-token",
        expiresAt: new Date(Date.now() + 86_400_000).toISOString(),
      }),
      600,
    ),
  register: (payload) =>
    withFallback(
      () => apiRequest(endpoints.auth.register, { method: "POST", body: payload }),
      () => ok<AuthUser>({ ...fx.currentDoctorFixture, name: payload.name, email: payload.email }),
      600,
    ),
  logout: () => withFallback(() => apiRequest(endpoints.auth.logout, { method: "POST" }), () => ok(), 200),
  forgotPassword: (email) =>
    withFallback(
      () => apiRequest(endpoints.auth.forgotPassword, { method: "POST", body: { email } }),
      () => ok(undefined, "Reset link sent"),
      600,
    ),
  resetPassword: (payload) =>
    withFallback(
      () => apiRequest(endpoints.auth.resetPassword, { method: "POST", body: payload }),
      () => ok(undefined, "Password updated"),
      600,
    ),
  me: () => withFallback<AuthUser>(() => apiRequest(endpoints.auth.me), () => fx.currentDoctorFixture),
};

/* ------------------------------------------------------------------ */
/* Patients                                                             */
/* ------------------------------------------------------------------ */
export const patientService: PatientService = {
  list: (query) =>
    withFallback<Patient[]>(
      () => apiRequest(endpoints.patients.list, { query: query as never }),
      () => {
        const term = query?.search?.toLowerCase();
        return term
          ? fx.patientFixtures.filter((p) => `${p.name} ${p.id}`.toLowerCase().includes(term))
          : fx.patientFixtures;
      },
    ),
  get: (id) =>
    withFallback<Patient | undefined>(
      () => apiRequest(endpoints.patients.detail(id)),
      () => fx.patientFixtures.find((p) => p.id === id),
    ),
  create: (payload: PatientInput) =>
    withFallback(
      () => apiRequest(endpoints.patients.create, { method: "POST", body: payload }),
      () => ok({ id: `PT-${Math.floor(Math.random() * 9000) + 1000}`, ...payload } as Patient, "Patient created"),
      500,
    ),
  update: (id, payload) =>
    withFallback(
      () => apiRequest(endpoints.patients.update(id), { method: "PATCH", body: payload }),
      () => ok({ ...(fx.patientFixtures.find((p) => p.id === id) as Patient), ...payload }, "Patient updated"),
      500,
    ),
  remove: (id) =>
    withFallback(
      () => apiRequest(endpoints.patients.remove(id), { method: "DELETE" }),
      () => ok(undefined, `${id} removed`),
      400,
    ),
  labs: (patientId) =>
    withFallback(
      () => apiRequest(endpoints.patients.labs(patientId)),
      () => fx.labResultFixtures,
    ),
  imaging: (patientId) =>
    withFallback(
      () => apiRequest(endpoints.patients.imaging(patientId)),
      () => fx.imagingFixtures,
    ),
  timeline: (patientId) =>
    withFallback<TimelineEvent[]>(
      () => apiRequest(endpoints.patients.timeline(patientId)),
      () => (fx.patientFixtures.find((p) => p.id === patientId)?.timeline ?? []) as TimelineEvent[],
    ),
};

/* ------------------------------------------------------------------ */
/* Digital twins                                                        */
/* ------------------------------------------------------------------ */
export const twinService: TwinService = {
  list: () =>
    withFallback<Patient[]>(
      () => apiRequest(endpoints.twins.list),
      () => fx.patientFixtures.slice(0, 12),
    ),
  versions: (patientId) =>
    withFallback(
      () => apiRequest(endpoints.twins.versions(patientId)),
      () => fx.twinVersionFixtures,
    ),
  snapshots: (patientId) =>
    withFallback(
      () => apiRequest(endpoints.twins.snapshots(patientId)),
      () => fx.twinSnapshotFixtures,
    ),
  resync: (patientId) =>
    withFallback(
      () => apiRequest(endpoints.twins.resync(patientId), { method: "POST" }),
      () => ok(undefined, `Twin ${patientId} re-synced`),
      900,
    ),
  restore: (patientId, version) =>
    withFallback(
      () => apiRequest(endpoints.twins.restore(patientId, version), { method: "POST" }),
      () => ok(undefined, `Restored ${version}`),
      700,
    ),
  archive: (patientId) =>
    withFallback(
      () => apiRequest(endpoints.twins.archive(patientId), { method: "POST" }),
      () => ok(undefined, `Twin ${patientId} archived`),
      500,
    ),
};

/* ------------------------------------------------------------------ */
/* Predictions                                                          */
/* ------------------------------------------------------------------ */
export const predictionService: PredictionService = {
  forPatient: (patientId) =>
    withFallback(
      () => apiRequest(endpoints.predictions.forPatient(patientId)),
      () => fx.predictionHistoryFixtures[0],
    ),
  history: (patientId) =>
    withFallback(
      () => apiRequest(endpoints.predictions.history(patientId)),
      () => fx.predictionHistoryFixtures,
    ),
  confidenceTrend: (patientId) =>
    withFallback(
      () => apiRequest(endpoints.predictions.confidenceTrend(patientId)),
      () => fx.confidenceTrendFixtures,
    ),
  explain: (patientId) =>
    withFallback(
      () => apiRequest(endpoints.predictions.explain(patientId)),
      () => fx.featureImportanceFixtures,
    ),
  run: (patientId) =>
    withFallback(
      () => apiRequest(endpoints.predictions.run, { method: "POST", body: { patientId } }),
      () => ok(fx.predictionHistoryFixtures[0], "Prediction complete"),
      900,
    ),
};

/* ------------------------------------------------------------------ */
/* Simulations                                                          */
/* ------------------------------------------------------------------ */
export const simulationService: SimulationService = {
  list: () =>
    withFallback(
      () => apiRequest(endpoints.simulations.list),
      () => fx.simulationRunFixtures,
    ),
  get: (id) =>
    withFallback<SimulationRun | undefined>(
      () => apiRequest(endpoints.simulations.detail(id)),
      () => fx.simulationRunFixtures.find((r) => r.id === id),
    ),
  scenarios: (_patientId) =>
    withFallback<Scenario[]>(
      () => apiRequest(endpoints.simulations.list),
      () => fx.scenarioFixtures,
    ),
  run: (patientId, draft) =>
    withFallback(
      () => apiRequest(endpoints.simulations.run, { method: "POST", body: { patientId, ...draft } }),
      () => ({ patientId, scenarios: fx.scenarioFixtures }),
      900,
    ),
  save: (draft) =>
    withFallback(
      () => apiRequest(endpoints.simulations.save, { method: "POST", body: draft }),
      () => ok(fx.simulationRunFixtures[0], "Scenario saved"),
      500,
    ),
  duplicate: (id) =>
    withFallback(
      () => apiRequest(endpoints.simulations.duplicate(id), { method: "POST" }),
      () => ok(fx.simulationRunFixtures.find((r) => r.id === id), "Scenario duplicated"),
      500,
    ),
  promote: (id, notes) =>
    withFallback(
      () => apiRequest(endpoints.simulations.promote(id), { method: "POST", body: { notes } }),
      () => ok(undefined, `${id} promoted to treatment plan`),
      700,
    ),
};

/* ------------------------------------------------------------------ */
/* Documents & OCR                                                      */
/* ------------------------------------------------------------------ */
export const documentService: DocumentService = {
  list: (query) =>
    withFallback<DocumentRecord[]>(
      () => apiRequest(endpoints.documents.list, { query: query as never }),
      () => fx.documentFixtures,
    ),
  get: (id) =>
    withFallback<DocumentRecord | undefined>(
      () => apiRequest(endpoints.documents.detail(id)),
      () => fx.documentFixtures.find((d) => d.id === id),
    ),
  upload: (file) =>
    withFallback(
      () => apiRequest(endpoints.documents.upload, { method: "POST", body: file }),
      () => ok(fx.documentFixtures[0], `${file.name} uploaded`),
      900,
    ),
  versions: (id) =>
    withFallback(
      () => apiRequest(endpoints.documents.versions(id)),
      () => fx.documentVersionFixtures,
    ),
  timeline: (id) =>
    withFallback(
      () => apiRequest(endpoints.documents.timeline(id)),
      () => fx.documentTimelineFixtures,
    ),
};

export const ocrService: OcrService = {
  extract: (documentId) =>
    withFallback(
      () => apiRequest(endpoints.ocr.extract(documentId), { method: "POST" }),
      () => ({ documentId, fields: fx.ocrFieldFixtures, model: "ocr-clinical-v3", extractedAt: new Date().toISOString() }),
      1200,
    ),
  fields: (documentId) =>
    withFallback(
      () => apiRequest(endpoints.ocr.fields(documentId)),
      () => fx.ocrFieldFixtures,
    ),
  approve: (documentId, fields) =>
    withFallback(
      () => apiRequest(endpoints.ocr.approve(documentId), { method: "POST", body: { fields } }),
      () => ok(undefined, "Extraction approved — digital twin updated"),
      800,
    ),
  reject: (documentId, reason) =>
    withFallback(
      () => apiRequest(endpoints.ocr.reject(documentId), { method: "POST", body: { reason } }),
      () => ok(undefined, "Extraction rejected"),
      500,
    ),
};

/* ------------------------------------------------------------------ */
/* Reports                                                              */
/* ------------------------------------------------------------------ */
export const reportService: ReportService = {
  list: () =>
    withFallback(
      () => apiRequest(endpoints.reports.list),
      () => fx.savedReportFixtures,
    ),
  versions: (id) =>
    withFallback(
      () => apiRequest(endpoints.reports.versions(id)),
      () => fx.reportVersionFixtures,
    ),
  downloads: () =>
    withFallback(
      () => apiRequest(endpoints.reports.downloads),
      () => fx.downloadHistoryFixtures,
    ),
  generate: (patientId) =>
    withFallback(
      () => apiRequest(endpoints.reports.generate, { method: "POST", body: { patientId } }),
      () => ok<SavedReport>(fx.savedReportFixtures[0]!, "Report generated"),
      900,
    ),
  export: (format: ExportFormat) =>
    withFallback(
      () => apiRequest(endpoints.reports.export, { method: "POST", body: { format } }),
      () => ok({ format }, `Export ready (${format.toUpperCase()})`),
      700,
    ),
};

/* ------------------------------------------------------------------ */
/* Care coordination                                                    */
/* ------------------------------------------------------------------ */
export const appointmentService: AppointmentService = {
  list: () =>
    withFallback(
      () => apiRequest(endpoints.appointments.list),
      () => fx.appointmentFixtures,
    ),
  create: (payload) =>
    withFallback(
      () => apiRequest(endpoints.appointments.create, { method: "POST", body: payload }),
      () => ok({ id: `AP-${Date.now()}`, status: "Scheduled", ...payload } as Appointment, "Appointment requested"),
      600,
    ),
  cancel: (id) =>
    withFallback(
      () => apiRequest(endpoints.appointments.cancel(id), { method: "POST" }),
      () => ok(undefined, "Appointment cancelled"),
      500,
    ),
};

export const treatmentService: TreatmentService = {
  plan: (patientId) =>
    withFallback(
      () => apiRequest(endpoints.treatment.plan(patientId)),
      () => fx.treatmentPlanFixture,
    ),
};

export const notificationService: NotificationService = {
  list: () =>
    withFallback(
      () => apiRequest(endpoints.notifications.list),
      () => fx.notificationFixtures,
    ),
  patientList: () =>
    withFallback(
      () => apiRequest(endpoints.notifications.list, { query: { audience: "patient" } }),
      () => fx.patientNotificationFixtures,
    ),
  markRead: (id) =>
    withFallback(
      () => apiRequest(endpoints.notifications.markRead(id), { method: "POST" }),
      () => ok(),
      200,
    ),
  markAllRead: () =>
    withFallback(
      () => apiRequest(endpoints.notifications.markAllRead, { method: "POST" }),
      () => ok(),
      250,
    ),
};

/* ------------------------------------------------------------------ */
/* Analytics, admin, research                                           */
/* ------------------------------------------------------------------ */
export const analyticsService: AnalyticsService = {
  dashboard: () =>
    withFallback(
      () => apiRequest(endpoints.analytics.dashboard),
      () => fx.patientGrowthFixtures,
    ),
  cohort: () =>
    withFallback(
      () => apiRequest(endpoints.analytics.cohort),
      () => fx.stageDistributionFixtures,
    ),
  accuracy: () =>
    withFallback(
      () => apiRequest(endpoints.analytics.accuracy),
      () => fx.accuracyTrendFixtures,
    ),
};

export const adminService: AdminService = {
  hospitals: () => withFallback(() => apiRequest(endpoints.admin.hospitals), () => fx.hospitalFixtures),
  doctors: () => withFallback(() => apiRequest(endpoints.admin.doctors), () => fx.doctorDirectoryFixtures),
  departments: () => withFallback(() => apiRequest(endpoints.admin.departments), () => fx.departmentFixtures),
  users: () => withFallback(() => apiRequest(endpoints.admin.users), () => fx.platformUserFixtures),
  auditLogs: () => withFallback(() => apiRequest(endpoints.admin.audit), () => fx.auditLogFixtures),
  permissions: () => withFallback(() => apiRequest(endpoints.admin.permissions), () => fx.permissionMatrixFixtures),
};

export const researchService: ResearchService = {
  models: () => withFallback(() => apiRequest(endpoints.research.models), () => fx.modelFixtures),
  datasets: () => withFallback(() => apiRequest(endpoints.research.datasets), () => fx.datasetFixtures),
  trainingRuns: () => withFallback(() => apiRequest(endpoints.research.training), () => fx.trainingRunFixtures),
  modelVersions: () => withFallback(() => apiRequest(endpoints.research.versions), () => fx.modelVersionFixtures),
  performance: () => withFallback(() => apiRequest(endpoints.research.performance), () => fx.performanceTrendFixtures),
};

export const services = {
  auth: authService,
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
