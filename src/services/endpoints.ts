/**
 * Endpoint registry — one place listing every backend route the frontend
 * expects. Backend implementers can treat this file as the API surface spec.
 */
export const endpoints = {
  auth: {
    login: "/auth/login",
    register: "/auth/register",
    logout: "/auth/logout",
    forgotPassword: "/auth/forgot-password",
    resetPassword: "/auth/reset-password",
    me: "/auth/me",
  },
  patients: {
    list: "/patients",
    detail: (id: string) => `/patients/${id}`,
    create: "/patients",
    update: (id: string) => `/patients/${id}`,
    remove: (id: string) => `/patients/${id}`,
    labs: (id: string) => `/patients/${id}/labs`,
    imaging: (id: string) => `/patients/${id}/imaging`,
    timeline: (id: string) => `/patients/${id}/timeline`,
  },
  twins: {
    list: "/digital-twins",
    detail: (patientId: string) => `/digital-twins/${patientId}`,
    versions: (patientId: string) => `/digital-twins/${patientId}/versions`,
    snapshots: (patientId: string) => `/digital-twins/${patientId}/snapshots`,
    resync: (patientId: string) => `/digital-twins/${patientId}/resync`,
    restore: (patientId: string, version: string) => `/digital-twins/${patientId}/versions/${version}/restore`,
    archive: (patientId: string) => `/digital-twins/${patientId}/archive`,
  },
  predictions: {
    forPatient: (patientId: string) => `/predictions/${patientId}`,
    history: (patientId: string) => `/predictions/${patientId}/history`,
    confidenceTrend: (patientId: string) => `/predictions/${patientId}/confidence-trend`,
    explain: (patientId: string) => `/predictions/${patientId}/explainability`,
    run: "/predictions/run",
  },
  simulations: {
    list: "/simulations",
    detail: (id: string) => `/simulations/${id}`,
    run: "/simulations/run",
    save: "/simulations",
    duplicate: (id: string) => `/simulations/${id}/duplicate`,
    promote: (id: string) => `/simulations/${id}/promote`,
  },
  documents: {
    list: "/documents",
    detail: (id: string) => `/documents/${id}`,
    upload: "/documents",
    versions: (id: string) => `/documents/${id}/versions`,
    links: (id: string) => `/documents/${id}/links`,
    timeline: (id: string) => `/documents/${id}/timeline`,
  },
  ocr: {
    extract: (documentId: string) => `/ocr/${documentId}/extract`,
    fields: (documentId: string) => `/ocr/${documentId}/fields`,
    approve: (documentId: string) => `/ocr/${documentId}/approve`,
    reject: (documentId: string) => `/ocr/${documentId}/reject`,
  },
  reports: {
    list: "/reports",
    detail: (id: string) => `/reports/${id}`,
    generate: "/reports/generate",
    versions: (id: string) => `/reports/${id}/versions`,
    downloads: "/reports/downloads",
    export: "/reports/export",
  },
  appointments: {
    list: "/appointments",
    create: "/appointments",
    cancel: (id: string) => `/appointments/${id}/cancel`,
  },
  treatment: {
    plan: (patientId: string) => `/patients/${patientId}/treatment-plan`,
  },
  notifications: {
    list: "/notifications",
    markRead: (id: string) => `/notifications/${id}/read`,
    markAllRead: "/notifications/read-all",
  },
  analytics: {
    dashboard: "/analytics/dashboard",
    cohort: "/analytics/cohort",
    accuracy: "/analytics/accuracy",
  },
  admin: {
    hospitals: "/admin/hospitals",
    doctors: "/admin/doctors",
    departments: "/admin/departments",
    users: "/admin/users",
    audit: "/admin/audit-logs",
    permissions: "/admin/permissions",
  },
  research: {
    models: "/research/models",
    datasets: "/research/datasets",
    training: "/research/training-runs",
    versions: "/research/model-versions",
    performance: "/research/performance",
  },
  search: {
    global: "/search",
  },
} as const;
