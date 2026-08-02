/**
 * Query keys — one namespace so cache invalidation stays consistent once the
 * backend is live.
 */
export const queryKeys = {
  auth: ["auth", "me"] as const,
  patients: {
    all: ["patients"] as const,
    list: (search?: string) => ["patients", "list", search ?? ""] as const,
    detail: (id: string) => ["patients", "detail", id] as const,
    labs: (id: string) => ["patients", id, "labs"] as const,
    imaging: (id: string) => ["patients", id, "imaging"] as const,
    timeline: (id: string) => ["patients", id, "timeline"] as const,
  },
  twins: {
    all: ["twins"] as const,
    list: ["twins", "list"] as const,
    versions: (id: string) => ["twins", id, "versions"] as const,
    snapshots: (id: string) => ["twins", id, "snapshots"] as const,
  },
  predictions: {
    all: ["predictions"] as const,
    latest: (id: string) => ["predictions", id, "latest"] as const,
    history: (id: string) => ["predictions", id, "history"] as const,
    trend: (id: string) => ["predictions", id, "trend"] as const,
    explain: (id: string) => ["predictions", id, "explain"] as const,
  },
  simulations: {
    all: ["simulations"] as const,
    list: ["simulations", "list"] as const,
    detail: (id: string) => ["simulations", "detail", id] as const,
    scenarios: (patientId: string) => ["simulations", "scenarios", patientId] as const,
  },
  documents: {
    all: ["documents"] as const,
    list: (search?: string) => ["documents", "list", search ?? ""] as const,
    versions: (id: string) => ["documents", id, "versions"] as const,
    timeline: (id: string) => ["documents", id, "timeline"] as const,
  },
  ocr: {
    fields: (id: string) => ["ocr", id, "fields"] as const,
  },
  reports: {
    all: ["reports"] as const,
    list: ["reports", "list"] as const,
    versions: (id: string) => ["reports", id, "versions"] as const,
    downloads: ["reports", "downloads"] as const,
  },
  appointments: ["appointments"] as const,
  treatment: (patientId: string) => ["treatment", patientId] as const,
  notifications: {
    all: ["notifications"] as const,
    doctor: ["notifications", "doctor"] as const,
    patient: ["notifications", "patient"] as const,
  },
  analytics: {
    dashboard: ["analytics", "dashboard"] as const,
    cohort: ["analytics", "cohort"] as const,
    accuracy: ["analytics", "accuracy"] as const,
  },
  admin: {
    hospitals: ["admin", "hospitals"] as const,
    doctors: ["admin", "doctors"] as const,
    departments: ["admin", "departments"] as const,
    users: ["admin", "users"] as const,
    audit: ["admin", "audit"] as const,
    permissions: ["admin", "permissions"] as const,
  },
  research: {
    models: ["research", "models"] as const,
    datasets: ["research", "datasets"] as const,
    training: ["research", "training"] as const,
    versions: ["research", "versions"] as const,
    performance: ["research", "performance"] as const,
  },
};
