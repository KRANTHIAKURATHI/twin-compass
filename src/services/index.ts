/**
 * Service layer — the single place the UI talks to "the backend".
 *
 * Every method: (1) is typed by a contract in `contracts.ts`, (2) declares its
 * endpoint in `endpoints.ts`, and (3) runs through `withFallback` so it hits
 * the real API as soon as `VITE_API_BASE_URL` is set and otherwise resolves
 * the typed fixtures. No UI change is needed to switch.
 */
import { apiRequest, withFallback, ApiError, USING_MOCKS } from "@/services/api-client";
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
        user: {
          ...fx.currentDoctorFixture,
          email: credentials.email || fx.currentDoctorFixture.email,
        },
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
  logout: () =>
    withFallback(
      () => apiRequest(endpoints.auth.logout, { method: "POST" }),
      () => ok(),
      200,
    ),
  refresh: () =>
    withFallback<AuthSession>(
      () => apiRequest(endpoints.auth.refresh, { method: "POST" }),
      () => ({
        user: fx.currentDoctorFixture,
        accessToken: "mock-access-token",
        expiresAt: new Date(Date.now() + 86_400_000).toISOString(),
      }),
      200,
    ),
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
  me: () =>
    withFallback<AuthUser>(
      () => apiRequest(endpoints.auth.me),
      () => fx.currentDoctorFixture,
    ),
};

/* ------------------------------------------------------------------ */
/* Users (profile)                                                      */
/* ------------------------------------------------------------------ */
export const userService: UserService = {
  updateProfile: (payload) =>
    withFallback<AuthUser>(
      () => apiRequest(endpoints.users.updateProfile, { method: "PATCH", body: payload }),
      () => ({
        ...fx.currentDoctorFixture,
        ...payload,
        name: payload.name ?? fx.currentDoctorFixture.name,
      }),
      400,
    ),
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
      () =>
        ok(
          { id: `PT-${Math.floor(Math.random() * 9000) + 1000}`, ...payload } as Patient,
          "Patient created",
        ),
      500,
    ),
  update: (id, payload) =>
    withFallback(
      () => apiRequest(endpoints.patients.update(id), { method: "PATCH", body: payload }),
      () =>
        ok(
          { ...(fx.patientFixtures.find((p) => p.id === id) as Patient), ...payload },
          "Patient updated",
        ),
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
    withFallback<TwinListEntry[]>(
      () => apiRequest(endpoints.twins.list),
      // Mock mode only. A fixture patient has no twin version, so it is
      // described as "Not created" rather than given an invented version.
      () =>
        fx.patientFixtures.slice(0, 12).map((p) => ({
          patientId: p.id,
          patient: p.name,
          version: null,
          status: "Not created",
          createdAt: null,
          author: "",
          summary: "",
          tumorSizeMm: p.tumorSizeMm,
          survival: p.survivalProbability ?? null,
          risk: p.risk,
          model: "",
        })),
    ),
  get: (patientId) =>
    withFallback<TwinDetail>(
      () => apiRequest(endpoints.twins.detail(patientId)),
      () => ({
        patientId,
        patient: fx.patientFixtures.find((p) => p.id === patientId)?.name ?? patientId,
        twinStatus: "Not created",
        active: fx.twinVersionFixtures[0] ?? null,
        versions: fx.twinVersionFixtures,
      }),
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
    withFallback<PredictionRun | null>(
      () => apiRequest(endpoints.predictions.forPatient(patientId)),
      () => fx.predictionHistoryFixtures[0] ?? null,
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
  progression: (patientId) =>
    withFallback<TumorSizePoint[]>(
      () => apiRequest(endpoints.predictions.progression(patientId)),
      () => [],
    ),
  explain: (patientId) =>
    withFallback<ExplainabilityResult>(
      () => apiRequest(endpoints.predictions.explain(patientId)),
      () => ({
        basis: "cohort",
        cohortSize: fx.patientFixtures.length,
        reliability: "indicative",
        factors: fx.featureImportanceFixtures,
        caveat: "Fixture data — not computed from any cohort.",
      }),
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
  list: (patientId) =>
    withFallback<SimulationRun[]>(
      () =>
        apiRequest(endpoints.simulations.list, {
          query: (patientId ? { patientId } : undefined) as never,
        }),
      () =>
        patientId
          ? fx.simulationRunFixtures.filter((r) => r.patientId === patientId)
          : fx.simulationRunFixtures,
    ),
  get: (id) =>
    withFallback<SimulationRun | undefined>(
      () => apiRequest(endpoints.simulations.detail(id)),
      () => fx.simulationRunFixtures.find((r) => r.id === id),
    ),
  // Reads the patient's newest recorded run and returns the scenarios stored
  // on it. Previously this fetched the runs list and typed it as Scenario[],
  // which was simply the wrong shape.
  scenarios: async (patientId) => {
    const runs = await simulationService.list(patientId);
    return (runs[0]?.scenarios ?? []) as Scenario[];
  },
  run: (patientId, draft) =>
    withFallback(
      () =>
        apiRequest(endpoints.simulations.run, { method: "POST", body: { patientId, ...draft } }),
      () => ({ id: `mock-run-${patientId}`, patientId, scenarios: fx.scenarioFixtures }),
      900,
    ),
  save: (patientId, draft) =>
    withFallback(
      () => apiRequest(endpoints.simulations.save, { method: "POST", body: { patientId, ...draft } }),
      () => ok(fx.simulationRunFixtures[0], "Scenario saved"),
      500,
    ),
  duplicate: (id) =>
    withFallback(
      () => apiRequest(endpoints.simulations.duplicate(id), { method: "POST" }),
      () =>
        ok(
          fx.simulationRunFixtures.find((r) => r.id === id),
          "Scenario duplicated",
        ),
      500,
    ),
  promote: (id, notes, selectedScenario) =>
    withFallback(
      () =>
        apiRequest(endpoints.simulations.promote(id), {
          method: "POST",
          body: { notes, ...(selectedScenario ? { selectedScenario } : {}) },
        }),
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
      () => {
        const term = query?.search?.toLowerCase();
        const rows = term
          ? fx.documentFixtures.filter((d) => `${d.name} ${d.patient}`.toLowerCase().includes(term))
          : fx.documentFixtures;
        return query?.patientId ? rows.filter((d) => d.patientId === query.patientId) : rows;
      },
    ),
  get: (id) =>
    withFallback<DocumentRecord | undefined>(
      () => apiRequest(endpoints.documents.detail(id)),
      () => fx.documentFixtures.find((d) => d.id === id),
    ),
  upload: ({ file, patientId, category }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("patientId", patientId);
    if (category) formData.append("category", category);
    return withFallback(
      () => apiRequest(endpoints.documents.upload, { method: "POST", body: formData }),
      () => ok(fx.documentFixtures[0], `${file.name} uploaded`),
      900,
    );
  },
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
  links: (id) =>
    withFallback<DocumentLinks>(
      () => apiRequest(endpoints.documents.links(id)),
      () => {
        const doc = fx.documentFixtures.find((d) => d.id === id);
        return {
          patientId: doc?.patientId ?? "",
          patient: doc?.patient ?? "",
          twinVersion: fx.documentLinkFixtures.twinVersion,
          prediction: fx.documentLinkFixtures.prediction,
          report: fx.documentLinkFixtures.report,
        };
      },
    ),
  download: (id) =>
    withFallback<DocumentDownload>(
      () => apiRequest(endpoints.documents.download(id)),
      () => {
        throw new ApiError("Download requires a real backend — no fixture file exists to serve.", 503, {
          code: "MOCK_MODE",
        });
      },
    ),
  preview: (id) =>
    withFallback<DocumentPreview>(
      () => apiRequest(endpoints.documents.preview(id)),
      () => ({ available: false, mimeType: fx.documentFixtures.find((d) => d.id === id)?.mimeType ?? "", url: null }),
    ),
};

const mockOcrExtraction = (documentId: string, status: OcrExtraction["status"]): OcrExtraction => ({
  documentId,
  patientId: fx.documentFixtures.find((d) => d.id === documentId)?.patientId ?? "",
  status,
  fields: fx.ocrFieldFixtures,
  // Mock mode only — no real OCR provider is configured server-side (see
  // backend app/services/ocr_provider.py), so a real call never returns this.
  model: "ocr-clinical-v3 (mock)",
  extractedAt: new Date().toISOString(),
});

export const ocrService: OcrService = {
  extract: (documentId) =>
    withFallback(
      () => apiRequest(endpoints.ocr.extract(documentId), { method: "POST" }),
      () => ok(mockOcrExtraction(documentId, "Extracted"), "Extraction complete — requires verification."),
      1200,
    ),
  fields: (documentId) =>
    withFallback(
      () => apiRequest(endpoints.ocr.fields(documentId)),
      () => mockOcrExtraction(documentId, "Extracted"),
    ),
  approve: (documentId, fields) =>
    withFallback(
      () => apiRequest(endpoints.ocr.approve(documentId), { method: "POST", body: { fields } }),
      () => ok({ ...mockOcrExtraction(documentId, "Approved"), fields }, "Extraction approved — digital twin resynced."),
      800,
    ),
  reject: (documentId, reason) =>
    withFallback(
      () => apiRequest(endpoints.ocr.reject(documentId), { method: "POST", body: { reason } }),
      () => ok(mockOcrExtraction(documentId, "Rejected"), "Extraction rejected."),
      500,
    ),
};

/* ------------------------------------------------------------------ */
/* Reports                                                              */
/* ------------------------------------------------------------------ */
export const reportService: ReportService = {
  list: (patientId) =>
    withFallback(
      () => apiRequest(endpoints.reports.list, { query: (patientId ? { patientId } : undefined) as never }),
      () => (patientId ? fx.savedReportFixtures.filter((r) => r.patientId === patientId) : fx.savedReportFixtures),
    ),
  get: (id) =>
    withFallback<ReportDetail>(
      () => apiRequest(endpoints.reports.detail(id)),
      () => ({ ...fx.savedReportFixtures[0]!, content: fx.reportContentFixture }),
    ),
  versions: (id) =>
    withFallback(
      () => apiRequest(endpoints.reports.versions(id)),
      () => fx.reportVersionFixtures,
    ),
  downloads: (reportId) =>
    withFallback(
      () => apiRequest(endpoints.reports.downloads, { query: (reportId ? { reportId } : undefined) as never }),
      () => (reportId ? fx.downloadHistoryFixtures.filter((d) => d.report === reportId) : fx.downloadHistoryFixtures),
    ),
  generate: (patientId, type = "Clinical summary") =>
    withFallback(
      () => apiRequest(endpoints.reports.generate, { method: "POST", body: { patientId, type } }),
      () => ok<SavedReport>(fx.savedReportFixtures[0]!, "Report generated"),
      900,
    ),
  export: (reportId, format: ExportFormat) =>
    withFallback(
      () => apiRequest(endpoints.reports.export(reportId), { method: "POST", body: { format } }),
      () => ok({ ...fx.savedReportFixtures[0]!, content: fx.reportContentFixture, format }, `${format.toUpperCase()} export recorded`),
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
      () =>
        ok(
          { id: `AP-${Date.now()}`, status: "Scheduled", ...payload } as Appointment,
          "Appointment requested",
        ),
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
    withFallback<DashboardAnalytics>(
      () => apiRequest(endpoints.analytics.dashboard),
      () => ({
        stats: [],
        model: null,
        patientGrowth: fx.patientGrowthFixtures as DashboardAnalytics["patientGrowth"],
        riskDistribution: [],
        stageDistribution: fx.stageDistributionFixtures as DashboardAnalytics["stageDistribution"],
        treatmentComparison: [],
        accuracy: { series: [], seriesKind: "cross-validation-folds", model: null },
        recentActivity: [],
        followUps: [],
      }),
    ),
  cohort: () =>
    withFallback<CohortAnalytics>(
      () => apiRequest(endpoints.analytics.cohort),
      () => ({
        ageDistribution: [],
        stageDistribution: fx.stageDistributionFixtures as CohortAnalytics["stageDistribution"],
        riskDistribution: [],
        treatmentComparison: [],
        survivalByRisk: { points: [], cohortSizes: {}, caveat: "" },
      }),
    ),
  accuracy: () =>
    withFallback<AccuracyResult>(
      () => apiRequest(endpoints.analytics.accuracy),
      () => ({ series: [], seriesKind: "cross-validation-folds", model: null }),
    ),
};

export const adminService: AdminService = {
  hospitals: () =>
    withFallback(
      () => apiRequest(endpoints.admin.hospitals),
      () => fx.hospitalFixtures,
    ),
  doctors: () =>
    withFallback(
      () => apiRequest(endpoints.admin.doctors),
      () => fx.doctorDirectoryFixtures,
    ),
  departments: () =>
    withFallback(
      () => apiRequest(endpoints.admin.departments),
      () => fx.departmentFixtures,
    ),
  users: () =>
    withFallback(
      () => apiRequest(endpoints.admin.users),
      () => fx.platformUserFixtures,
    ),
  auditLogs: () =>
    withFallback(
      () => apiRequest(endpoints.admin.audit),
      () => fx.auditLogFixtures,
    ),
  permissions: () =>
    withFallback(
      () => apiRequest(endpoints.admin.permissions),
      () => fx.permissionMatrixFixtures,
    ),
};

export const researchService: ResearchService = {
  models: () =>
    withFallback(
      () => apiRequest(endpoints.research.models),
      () => fx.modelFixtures,
    ),
  datasets: () =>
    withFallback(
      () => apiRequest(endpoints.research.datasets),
      () => fx.datasetFixtures,
    ),
  trainingRuns: () =>
    withFallback(
      () => apiRequest(endpoints.research.training),
      () => fx.trainingRunFixtures,
    ),
  modelVersions: () =>
    withFallback(
      () => apiRequest(endpoints.research.versions),
      () => fx.modelVersionFixtures,
    ),
  performance: () =>
    withFallback(
      () => apiRequest(endpoints.research.performance),
      () => fx.performanceTrendFixtures,
    ),
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
