/**
 * Reusable API hooks.
 *
 * Every page should read/write through these instead of calling services or
 * touching fixtures directly. They wrap TanStack Query, so the day the backend
 * lands, only `src/services/*` changes — hooks, and therefore pages, stay put.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { toast } from "sonner";
import {
  adminService,
  analyticsService,
  appointmentService,
  documentService,
  notificationService,
  ocrService,
  patientService,
  predictionService,
  reportService,
  researchService,
  simulationService,
  treatmentService,
  twinService,
} from "@/services";
import { queryKeys } from "@/hooks/query-keys";
import type { MutationResult, OcrField, Patient, PatientInput, ScenarioDraft } from "@/types/models";

type QueryOpts<T> = Omit<UseQueryOptions<T, Error, T, readonly unknown[]>, "queryKey" | "queryFn">;

/** Generic read hook — thin wrapper so option defaults stay in one place. */
export function useApiQuery<T>(key: readonly unknown[], fn: () => Promise<T>, options?: QueryOpts<T>) {
  return useQuery<T, Error, T, readonly unknown[]>({
    queryKey: key,
    queryFn: fn,
    staleTime: 30_000,
    ...options,
  });
}

/**
 * Generic write hook with built-in loading/success/error handling.
 * `isPending`, `isSuccess`, and `isError` are always available to the UI.
 */
export function useApiMutation<TVars, TData = MutationResult>(
  fn: (vars: TVars) => Promise<TData>,
  options?: {
    successMessage?: string | ((data: TData, vars: TVars) => string);
    errorMessage?: string;
    invalidate?: readonly (readonly unknown[])[];
  } & Omit<UseMutationOptions<TData, Error, TVars>, "mutationFn">,
) {
  const queryClient = useQueryClient();
  const { successMessage, errorMessage, invalidate, ...rest } = options ?? {};
  return useMutation<TData, Error, TVars>({
    mutationFn: fn,
    ...rest,
    onSuccess: (data, vars, ctx) => {
      invalidate?.forEach((key) => queryClient.invalidateQueries({ queryKey: key as unknown[] }));
      const msg = typeof successMessage === "function" ? successMessage(data, vars) : successMessage;
      if (msg) toast.success(msg);
      rest.onSuccess?.(data, vars, ctx);
    },
    onError: (error, vars, ctx) => {
      toast.error(errorMessage ?? error.message ?? "Something went wrong");
      rest.onError?.(error, vars, ctx);
    },
  });
}

/* ---------------------------- Patients ----------------------------- */
export const usePatients = (search?: string) =>
  useApiQuery(queryKeys.patients.list(search), () => patientService.list({ search }));

export const usePatient = (id: string) =>
  useApiQuery(queryKeys.patients.detail(id), () => patientService.get(id), { enabled: Boolean(id) });

export const usePatientLabs = (id: string) => useApiQuery(queryKeys.patients.labs(id), () => patientService.labs(id));
export const usePatientImaging = (id: string) =>
  useApiQuery(queryKeys.patients.imaging(id), () => patientService.imaging(id));
export const usePatientTimeline = (id: string) =>
  useApiQuery(queryKeys.patients.timeline(id), () => patientService.timeline(id));

export const useCreatePatient = () =>
  useApiMutation((payload: PatientInput) => patientService.create(payload), {
    successMessage: "Patient created",
    invalidate: [queryKeys.patients.all],
  });

/** Optimistic: the row updates instantly and rolls back if the API rejects. */
export function useUpdatePatient(id: string) {
  const queryClient = useQueryClient();
  return useApiMutation((payload: Partial<PatientInput>) => patientService.update(id, payload), {
    successMessage: "Patient updated",
    invalidate: [queryKeys.patients.all],
    onMutate: async (payload) => {
      const key = queryKeys.patients.detail(id);
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<Patient>(key);
      if (previous) queryClient.setQueryData<Patient>(key, { ...previous, ...(payload as Partial<Patient>) });
      return { previous };
    },
    onError: (_e, _v, ctx) => {
      const previous = (ctx as { previous?: Patient } | undefined)?.previous;
      if (previous) queryClient.setQueryData(queryKeys.patients.detail(id), previous);
    },
  });
}

export const useDeletePatient = () =>
  useApiMutation((id: string) => patientService.remove(id), {
    successMessage: "Patient removed",
    invalidate: [queryKeys.patients.all],
  });

/* ------------------------------ Twins ------------------------------ */
export const useTwins = () => useApiQuery(queryKeys.twins.list, () => twinService.list());
export const useTwinVersions = (patientId: string) =>
  useApiQuery(queryKeys.twins.versions(patientId), () => twinService.versions(patientId));
export const useTwinSnapshots = (patientId: string) =>
  useApiQuery(queryKeys.twins.snapshots(patientId), () => twinService.snapshots(patientId));

export const useResyncTwin = () =>
  useApiMutation((patientId: string) => twinService.resync(patientId), {
    successMessage: "Digital twin re-synced",
    invalidate: [queryKeys.twins.all],
  });

export const useRestoreTwinVersion = () =>
  useApiMutation((vars: { patientId: string; version: string }) => twinService.restore(vars.patientId, vars.version), {
    successMessage: (_d, v) => `Restored ${v.version}`,
    invalidate: [queryKeys.twins.all],
  });

export const useArchiveTwin = () =>
  useApiMutation((patientId: string) => twinService.archive(patientId), {
    successMessage: "Digital twin archived",
    invalidate: [queryKeys.twins.all],
  });

/* --------------------------- Predictions --------------------------- */
export const usePrediction = (patientId: string) =>
  useApiQuery(queryKeys.predictions.latest(patientId), () => predictionService.forPatient(patientId));
export const usePredictionHistory = (patientId: string) =>
  useApiQuery(queryKeys.predictions.history(patientId), () => predictionService.history(patientId));
export const useConfidenceTrend = (patientId: string) =>
  useApiQuery(queryKeys.predictions.trend(patientId), () => predictionService.confidenceTrend(patientId));
export const useExplainability = (patientId: string) =>
  useApiQuery(queryKeys.predictions.explain(patientId), () => predictionService.explain(patientId));

export const useRunPrediction = () =>
  useApiMutation((patientId: string) => predictionService.run(patientId), {
    successMessage: "Prediction complete",
    invalidate: [queryKeys.predictions.all],
  });

/* --------------------------- Simulations --------------------------- */
export const useSimulationRuns = () => useApiQuery(queryKeys.simulations.list, () => simulationService.list());
export const useSimulationRun = (id: string) =>
  useApiQuery(queryKeys.simulations.detail(id), () => simulationService.get(id), { enabled: Boolean(id) });
export const useScenarios = (patientId: string) =>
  useApiQuery(queryKeys.simulations.scenarios(patientId), () => simulationService.scenarios(patientId));

export const useRunSimulation = () =>
  useApiMutation((vars: { patientId: string; draft?: ScenarioDraft }) =>
    simulationService.run(vars.patientId, vars.draft),
  );

export const useSaveScenario = () =>
  useApiMutation((draft: ScenarioDraft) => simulationService.save(draft), {
    successMessage: "Scenario saved",
    invalidate: [queryKeys.simulations.all],
  });

export const useDuplicateScenario = () =>
  useApiMutation((id: string) => simulationService.duplicate(id), {
    successMessage: "Scenario duplicated",
    invalidate: [queryKeys.simulations.all],
  });

export const usePromoteSimulation = () =>
  useApiMutation((vars: { id: string; notes?: string }) => simulationService.promote(vars.id, vars.notes), {
    successMessage: "Promoted to treatment plan",
    invalidate: [queryKeys.simulations.all, queryKeys.patients.all],
  });

/* --------------------------- Documents ----------------------------- */
export const useDocuments = (search?: string) =>
  useApiQuery(queryKeys.documents.list(search), () => documentService.list({ search }));
export const useDocumentVersions = (id: string) =>
  useApiQuery(queryKeys.documents.versions(id), () => documentService.versions(id));
export const useDocumentTimeline = (id: string) =>
  useApiQuery(queryKeys.documents.timeline(id), () => documentService.timeline(id));

export const useUploadDocument = () =>
  useApiMutation((file: { name: string; size: number; patientId?: string }) => documentService.upload(file), {
    successMessage: (_d, v) => `${v.name} uploaded`,
    invalidate: [queryKeys.documents.all],
  });

/* ------------------------------- OCR ------------------------------- */
export const useOcrFields = (documentId: string) =>
  useApiQuery(queryKeys.ocr.fields(documentId), () => ocrService.fields(documentId), {
    enabled: Boolean(documentId),
  });

export const useExtractOcr = () => useApiMutation((documentId: string) => ocrService.extract(documentId));

export const useApproveOcr = () =>
  useApiMutation((vars: { documentId: string; fields: OcrField[] }) => ocrService.approve(vars.documentId, vars.fields), {
    successMessage: "Extraction approved — digital twin updated",
    invalidate: [queryKeys.documents.all, queryKeys.twins.all],
  });

export const useRejectOcr = () =>
  useApiMutation((vars: { documentId: string; reason: string }) => ocrService.reject(vars.documentId, vars.reason), {
    successMessage: "Extraction rejected",
    invalidate: [queryKeys.documents.all],
  });

/* ----------------------------- Reports ----------------------------- */
export const useReports = () => useApiQuery(queryKeys.reports.list, () => reportService.list());
export const useReportVersions = (id: string) =>
  useApiQuery(queryKeys.reports.versions(id), () => reportService.versions(id));
export const useDownloadHistory = () => useApiQuery(queryKeys.reports.downloads, () => reportService.downloads());

export const useGenerateReport = () =>
  useApiMutation((patientId: string) => reportService.generate(patientId), {
    successMessage: "Report generated",
    invalidate: [queryKeys.reports.all],
  });

export const useExportReport = () =>
  useApiMutation((format: "pdf" | "csv") => reportService.export(format), {
    successMessage: (_d, v) => `Export ready (${v.toUpperCase()})`,
    invalidate: [queryKeys.reports.downloads],
  });

/* -------------------------- Coordination --------------------------- */
export const useAppointments = () => useApiQuery(queryKeys.appointments, () => appointmentService.list());
export const useTreatmentPlan = (patientId: string) =>
  useApiQuery(queryKeys.treatment(patientId), () => treatmentService.plan(patientId));

export const useCancelAppointment = () =>
  useApiMutation((id: string) => appointmentService.cancel(id), {
    successMessage: "Appointment cancelled",
    invalidate: [queryKeys.appointments],
  });

export const useNotifications = (audience: "doctor" | "patient" = "doctor") =>
  useApiQuery(
    audience === "doctor" ? queryKeys.notifications.doctor : queryKeys.notifications.patient,
    () => (audience === "doctor" ? notificationService.list() : notificationService.patientList()),
  );

export const useMarkNotificationRead = () =>
  useApiMutation((id: string) => notificationService.markRead(id), { invalidate: [queryKeys.notifications.all] });

export const useMarkAllNotificationsRead = () =>
  useApiMutation(() => notificationService.markAllRead(), {
    successMessage: "All notifications marked as read",
    invalidate: [queryKeys.notifications.all],
  });

/* --------------------- Analytics / admin / research ----------------- */
export const useDashboardAnalytics = () => useApiQuery(queryKeys.analytics.dashboard, () => analyticsService.dashboard());
export const useCohortAnalytics = () => useApiQuery(queryKeys.analytics.cohort, () => analyticsService.cohort());
export const useAccuracyAnalytics = () => useApiQuery(queryKeys.analytics.accuracy, () => analyticsService.accuracy());

export const useHospitals = () => useApiQuery(queryKeys.admin.hospitals, () => adminService.hospitals());
export const useDoctors = () => useApiQuery(queryKeys.admin.doctors, () => adminService.doctors());
export const useDepartments = () => useApiQuery(queryKeys.admin.departments, () => adminService.departments());
export const usePlatformUsers = () => useApiQuery(queryKeys.admin.users, () => adminService.users());
export const useAuditLogs = () => useApiQuery(queryKeys.admin.audit, () => adminService.auditLogs());
export const usePermissions = () => useApiQuery(queryKeys.admin.permissions, () => adminService.permissions());

export const useModels = () => useApiQuery(queryKeys.research.models, () => researchService.models());
export const useDatasets = () => useApiQuery(queryKeys.research.datasets, () => researchService.datasets());
export const useTrainingRuns = () => useApiQuery(queryKeys.research.training, () => researchService.trainingRuns());
export const useModelVersions = () => useApiQuery(queryKeys.research.versions, () => researchService.modelVersions());
export const usePerformanceTrend = () => useApiQuery(queryKeys.research.performance, () => researchService.performance());

export { queryKeys };
