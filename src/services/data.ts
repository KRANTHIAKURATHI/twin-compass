/**
 * The data surface the UI imports from.
 *
 * Pages import typed snapshots from here (or, preferably, the hooks in
 * `@/hooks/api`). Today the values resolve from `fixtures.ts`; once the
 * backend exists these become the initial/placeholder data while the
 * services + query hooks supply live responses. No page imports
 * `@/lib/mock-*` directly any more.
 */
import * as f from "@/services/fixtures";
import * as raw from "@/lib/mock-data";
import * as extra from "@/lib/mock-extra";
import * as lifecycle from "@/lib/mock-lifecycle";

export type * from "@/types/models";

/* Clinical */
export const patients = f.patientFixtures;
export const scenarios = f.scenarioFixtures;
export const labResults = f.labResultFixtures;
export const imagingStudies = f.imagingFixtures;
export const progressionForecast = f.progressionForecastFixtures;
export const featureImportance = f.featureImportanceFixtures;
export const doctor = raw.doctor;

/* Analytics */
export const dashboardStats = raw.dashboardStats;
export const patientGrowth = raw.patientGrowth;
export const stageDistribution = raw.stageDistribution;
export const treatmentComparison = raw.treatmentComparison;
export const accuracyTrend = raw.accuracyTrend;
export const riskDistribution = raw.riskDistribution;
export const ageDistribution = raw.ageDistribution;
export const survivalCurve = raw.survivalCurve;
export const recentActivity = raw.recentActivity;
export const followUps = raw.followUps;
export const notifications = raw.notifications;

/* Twin / prediction / simulation */
export const twinVersions = f.twinVersionFixtures;
export const twinSnapshots = f.twinSnapshotFixtures;
export const predictionHistory = f.predictionHistoryFixtures;
export const confidenceTrend = f.confidenceTrendFixtures;
export const simulationRuns = f.simulationRunFixtures;
export const simulationHistory = extra.simulationHistory;

/* Documents & OCR */
export const documents = f.documentFixtures;
export const documentVersions = f.documentVersionFixtures;
export const documentLinks = lifecycle.documentLinks;
export const documentTimeline = lifecycle.documentTimeline;
export const ocrFields = f.ocrFieldFixtures;

/* Reports */
export const savedReports = f.savedReportFixtures;
export const reportVersions = f.reportVersionFixtures;
export const downloadHistory = lifecycle.downloadHistory;
export const systemTimelineEvents = lifecycle.systemTimelineEvents;

/* Care coordination */
export const appointments = f.appointmentFixtures;
export const treatmentPlan = f.treatmentPlanFixture;
export const patientNotifications = f.patientNotificationFixtures;

/* Admin */
export const hospitals = f.hospitalFixtures;
export const doctorsDirectory = f.doctorDirectoryFixtures;
export const departments = f.departmentFixtures;
export const platformUsers = f.platformUserFixtures;
export const auditLogs = f.auditLogFixtures;
export const permissionMatrix = f.permissionMatrixFixtures;

/* Research */
export const models = f.modelFixtures;
export const datasets = f.datasetFixtures;
export const trainingRuns = f.trainingRunFixtures;
export const modelVersions = f.modelVersionFixtures;
export const performanceTrend = f.performanceTrendFixtures;
