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
export const ocrFieldFixtures = extra.ocrFields as OcrField[];

/* Reports --------------------------------------------------------------- */
export const savedReportFixtures = lifecycle.savedReports as SavedReport[];
export const reportVersionFixtures = lifecycle.reportVersions as ReportVersion[];
export const downloadHistoryFixtures = lifecycle.downloadHistory as unknown as DownloadRecord[];

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
