/**
 * Typed fixture snapshots.
 *
 * This is the ONLY module that touches the mock datasets. Everything here is
 * typed with the shared domain models, so when the backend arrives the
 * services simply stop calling these functions — no UI or type changes.
 *
 * TODO(backend): delete this file once every service points at the API.
 */
import * as raw from "@/lib/mock-data";
import * as extra from "@/lib/mock-extra";
import * as lifecycle from "@/lib/mock-lifecycle";
import type {
  Appointment,
  AuditLogEntry,
  AuthUser,
  ConfidencePoint,
  Dataset,
  Department,
  DocumentRecord,
  DocumentVersion,
  DoctorProfile,
  DownloadRecord,
  FeatureImportance,
  Hospital,
  ImagingStudy,
  LabResult,
  MLModel,
  MetricPoint,
  ModelVersion,
  NotificationItem,
  OcrField,
  Patient,
  PatientStatus,
  PerformancePoint,
  PermissionRow,
  PlatformUser,
  PredictionRun,
  ReportContent,
  SavedReport,
  Scenario,
  SimulationRun,
  TimelineEvent,
  TrainingRun,
  TreatmentPlan,
  TwinSnapshot,
  TwinVersion,
  ModelVersion as ResearchModelVersion,
  ReportVersion,
} from "@/types/models";

/* Clinical ------------------------------------------------------------- */
export const patientFixtures = raw.patients as Patient[];
export const scenarioFixtures = raw.scenarios as Scenario[];
export const labResultFixtures = extra.labResults as unknown as LabResult[];
export const imagingFixtures = extra.imagingStudies as ImagingStudy[];
export const progressionForecastFixtures = raw.progressionForecast as MetricPoint[];
export const featureImportanceFixtures = raw.featureImportance as FeatureImportance[];

/* Twin / prediction / simulation --------------------------------------- */
export const twinVersionFixtures = lifecycle.twinVersions as TwinVersion[];
export const twinSnapshotFixtures = lifecycle.twinSnapshots as TwinSnapshot[];
export const predictionHistoryFixtures = lifecycle.predictionHistory as PredictionRun[];
export const confidenceTrendFixtures = lifecycle.confidenceTrend as ConfidencePoint[];
export const simulationRunFixtures = lifecycle.simulationRuns as SimulationRun[];
export const simulationHistoryFixtures = extra.simulationHistory as unknown as Record<string, string>[];

/* Documents & OCR ------------------------------------------------------- */
export const documentFixtures = extra.documents as DocumentRecord[];
export const documentVersionFixtures = extra.documentVersions as DocumentVersion[];
export const documentLinkFixtures = lifecycle.documentLinks;
export const documentTimelineFixtures = lifecycle.documentTimeline as TimelineEvent[];
/** Raw fixture rows use a display label as `field`; map the ones that match
 * a real patient column onto its machine key (see backend FIELD_CATALOG in
 * `routers/ocr.py`) so mock mode exercises the same approve/reject shape a
 * real backend would. Anything with no clinical column stays label-only —
 * informational (e.g. "Patient name"), never approvable. */
const OCR_FIELD_KEY_BY_LABEL: Record<string, string> = {
  "Tumor size (mm)": "tumor_size_mm",
  "ER status": "er_status",
  "PR status": "pr_status",
  "HER2 status": "her2_status",
  "Ki-67 (%)": "ki67",
  "Nodes involved": "nodes_involved",
};
export const ocrFieldFixtures = (extra.ocrFields as { field: string; value: string; confidence: number }[]).map(
  (row): OcrField => ({
    field: OCR_FIELD_KEY_BY_LABEL[row.field] ?? row.field,
    label: row.field,
    value: row.value,
    confidence: row.confidence,
    status: "pending",
  }),
);

/* Reports --------------------------------------------------------------- */
export const savedReportFixtures = lifecycle.savedReports as SavedReport[];
export const reportVersionFixtures = lifecycle.reportVersions as ReportVersion[];
export const downloadHistoryFixtures = lifecycle.downloadHistory as unknown as DownloadRecord[];

export const reportContentFixture: ReportContent = {
  patient: {
    name: patientFixtures[0]!.name,
    patientId: patientFixtures[0]!.id,
    age: patientFixtures[0]!.age,
    stage: patientFixtures[0]!.stage,
    tumorSizeMm: patientFixtures[0]!.tumorSizeMm,
    erStatus: patientFixtures[0]!.erStatus,
    prStatus: patientFixtures[0]!.prStatus,
    her2Status: patientFixtures[0]!.her2Status,
    currentTreatment: patientFixtures[0]!.currentTreatment,
    status: patientFixtures[0]!.status,
  },
  digitalTwin: twinVersionFixtures[0]
    ? {
        version: twinVersionFixtures[0].version,
        createdAt: twinVersionFixtures[0].createdAt,
        status: twinVersionFixtures[0].status,
        tumorSizeMm: twinVersionFixtures[0].tumorSizeMm,
        survival: twinVersionFixtures[0].survival,
        risk: twinVersionFixtures[0].risk,
      }
    : null,
  prediction: predictionHistoryFixtures[0]
    ? {
        basis: "measured",
        date: predictionHistoryFixtures[0].date,
        twinVersion: predictionHistoryFixtures[0].twinVersion,
        model: predictionHistoryFixtures[0].model,
        survival: predictionHistoryFixtures[0].survival,
        recurrence: predictionHistoryFixtures[0].recurrence,
        riskBand: predictionHistoryFixtures[0].riskBand,
        confidence: predictionHistoryFixtures[0].confidence,
      }
    : { basis: "none", caveat: "No prediction run has been recorded for this patient." },
  simulations: {
    basis: "prototype",
    caveat: "Research/prototype kinetic simulation projection - not a clinically validated recommendation.",
    runs: simulationRunFixtures.slice(0, 5).map((s) => ({
      id: s.id,
      date: s.date,
      selected: s.selected,
      decision: s.decision,
      survival: s.survival,
      response: s.response,
      confidence: s.confidence,
    })),
  },
  documents: { count: documentFixtures.filter((d) => d.patientId === patientFixtures[0]!.id).length },
  timeline: (lifecycle.systemTimelineEvents as TimelineEvent[]).slice(0, 10),
  notes: patientFixtures[0]!.notes ?? null,
};

/* Care coordination ----------------------------------------------------- */
export const appointmentFixtures = extra.appointments as Appointment[];
export const treatmentPlanFixture = extra.treatmentPlan as TreatmentPlan;
export const notificationFixtures = raw.notifications as unknown as NotificationItem[];
export const patientNotificationFixtures = extra.patientNotifications as NotificationItem[];

/* Admin ----------------------------------------------------------------- */
export const hospitalFixtures = extra.hospitals as Hospital[];
export const doctorDirectoryFixtures = extra.doctorsDirectory as DoctorProfile[];
export const departmentFixtures = extra.departments as Department[];
export const platformUserFixtures = extra.platformUsers as PlatformUser[];
export const auditLogFixtures = extra.auditLogs as AuditLogEntry[];
export const permissionMatrixFixtures = extra.permissionMatrix as PermissionRow[];

/* Research -------------------------------------------------------------- */
export const modelFixtures = extra.models as MLModel[];
export const datasetFixtures = extra.datasets as Dataset[];
export const trainingRunFixtures = extra.trainingRuns as TrainingRun[];
export const modelVersionFixtures = extra.modelVersions as ResearchModelVersion[];
export const performanceTrendFixtures = extra.performanceTrend as PerformancePoint[];

/* Analytics ------------------------------------------------------------- */
export const dashboardStatFixtures = raw.dashboardStats as unknown as MetricPoint[];
export const patientGrowthFixtures = raw.patientGrowth as MetricPoint[];
export const stageDistributionFixtures = raw.stageDistribution as MetricPoint[];
export const treatmentComparisonFixtures = raw.treatmentComparison as MetricPoint[];
export const accuracyTrendFixtures = raw.accuracyTrend as MetricPoint[];
export const riskDistributionFixtures = raw.riskDistribution as MetricPoint[];
export const ageDistributionFixtures = raw.ageDistribution as MetricPoint[];
export const survivalCurveFixtures = raw.survivalCurve as MetricPoint[];
export const recentActivityFixtures = raw.recentActivity as unknown as Record<string, string>[];
export const followUpFixtures = raw.followUps as unknown as Record<string, string>[];

/* Identity -------------------------------------------------------------- */
export const currentDoctorFixture: AuthUser = {
  id: "DR-01",
  name: raw.doctor.name,
  email: (raw.doctor as { email?: string }).email ?? "s.whitmore@northfield.health",
  role: "doctor",
  title: (raw.doctor as { role?: string }).role,
  hospital: (raw.doctor as { hospital?: string }).hospital,
};

export type { ModelVersion, PatientStatus };
