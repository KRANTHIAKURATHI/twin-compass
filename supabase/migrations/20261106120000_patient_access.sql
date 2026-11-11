-- Patient-level access control (Phase 6.1). Until now a role check was the only authorization: any doctor could
-- reach every patient. `patient_access` states which profile may access which patient:
--   relationship 'care_team' -> a clinician (role doctor) assigned to the patient
--   relationship 'self'      -> the patient-role login that IS the patient
-- Administrators bypass the table; researchers never get identified patient access.
--
-- Requires `profiles` (created by the Alembic identity migration, which therefore runs first) and `patients`.
-- Existing patients get NO rows: ownership is not inferred. They stay reachable by administrators only until an
-- administrator (or the creating doctor, for new patients) assigns someone. No existing data is changed.
-- RLS is enabled with no policies, i.e. closed to anon/authenticated; the backend role bypasses it by design.

CREATE TABLE IF NOT EXISTS patient_access (
    id           text PRIMARY KEY DEFAULT gen_random_uuid()::text,
    patient_id   text NOT NULL REFERENCES patients (id) ON DELETE CASCADE,
    profile_id   uuid NOT NULL REFERENCES profiles (id) ON DELETE CASCADE,
    relationship text NOT NULL CHECK (relationship IN ('care_team', 'self')),
    granted_by   uuid REFERENCES profiles (id) ON DELETE SET NULL,
    granted_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT patient_access_unique UNIQUE (patient_id, profile_id, relationship)
);

CREATE INDEX IF NOT EXISTS patient_access_profile_idx ON patient_access (profile_id, relationship);

ALTER TABLE patient_access ENABLE ROW LEVEL SECURITY;
