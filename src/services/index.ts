/**
 * Service layer — the single place the UI talks to "the backend".
 * Today it resolves mock data; later each method calls FastAPI / Supabase.
 */
import {
  patients,
  scenarios,
  notifications,
  doctor,
  type Patient,
  type Scenario,
} from "@/lib/mock-data";

const LATENCY = 220;

function delay<T>(data: T, ms = LATENCY): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(data), ms));
}

export const patientService = {
  // TODO(backend): GET /api/patients
  list: () => delay<Patient[]>(patients),
  // TODO(backend): GET /api/patients/{id}
  get: (id: string) => delay<Patient | undefined>(patients.find((p) => p.id === id)),
  // TODO(backend): POST /api/patients
  create: (payload: Partial<Patient>) => delay({ ok: true, payload }),
  // TODO(backend): PATCH /api/patients/{id}
  update: (id: string, payload: Partial<Patient>) => delay({ ok: true, id, payload }),
  // TODO(backend): DELETE /api/patients/{id}
  remove: (id: string) => delay({ ok: true, id }),
};

export const twinService = {
  // TODO(backend): GET /api/digital-twins
  list: () => delay(patients.slice(0, 12)),
  // TODO(backend): POST /api/digital-twins/{id}/resync
  resync: (id: string) => delay({ ok: true, id }, 900),
};

export const simulationService = {
  // TODO(backend): POST /api/simulations  { patientId, scenarios[] }
  run: (patientId: string) => delay<{ patientId: string; scenarios: Scenario[] }>({ patientId, scenarios }, 900),
};

export const predictionService = {
  // TODO(backend): GET /api/predictions/{patientId}
  forPatient: (patientId: string) => delay({ patientId, generatedAt: new Date().toISOString() }),
  // TODO(backend): GET /api/predictions/{patientId}/explainability
  explain: (patientId: string) => delay({ patientId }),
};

export const reportService = {
  // TODO(backend): POST /api/reports/export { format: 'pdf' | 'csv' }
  export: (format: "pdf" | "csv") => delay({ ok: true, format }, 700),
};

export const notificationService = {
  // TODO(backend): GET /api/notifications
  list: () => delay(notifications),
};

export const authService = {
  // TODO(backend): Supabase auth — signInWithPassword
  login: (email: string) => delay({ ok: true, email }, 600),
  // TODO(backend): Supabase auth — signUp
  register: (email: string) => delay({ ok: true, email }, 600),
  // TODO(backend): Supabase auth — resetPasswordForEmail
  forgotPassword: (email: string) => delay({ ok: true, email }, 600),
  // TODO(backend): Supabase auth — updateUser
  resetPassword: () => delay({ ok: true }, 600),
  // TODO(backend): GET /api/me
  me: () => delay(doctor),
};
