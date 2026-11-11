-- Patient-access coverage check and OPTIONAL, REVIEW-FIRST backfill (Phase 6.1).
--
-- NOT a migration: it lives outside supabase/migrations on purpose, so it is never applied automatically.
-- Run each section by hand in the Supabase SQL editor (as the `postgres` role) and read the output before the next.
--
-- Why this exists: `patient_access` starts empty. Until a row exists, only administrators can open a patient;
-- doctors see an empty list. The schema holds NO authoritative "this doctor treats this patient" relationship for
-- existing data:
--   * patients.created_by references the LEGACY `users` table, not `profiles`; the API only fills it when the acting
--     profile id also exists in `users`, so it is NULL for nearly every patient. It is not used here.
--   * The one trustworthy record is the audit trail: since the audit-logging change, creating a patient writes an
--     audit_logs row `action = 'patient.created'` whose `after` JSON holds the creating profile id and the patient id.
--     The application's own rule is "the creating doctor is the first member of the care team"; section 2 reproduces
--     exactly that rule from that record and nothing else.
-- Anything not covered by section 2 (patients created before audit logging, patients created by admins, patients whose
-- creator is no longer an active doctor) needs a human decision: assign through POST /admin/patients/{id}/access.
-- Do not guess relationships by name, hospital or e-mail.

-- ==== 1. coverage (read-only) ============================================================================
SELECT
    count(*)                                                        AS patients_total,
    count(*) FILTER (WHERE pa.patient_id IS NULL)                   AS patients_with_no_access_rows,
    count(*) FILTER (WHERE pa.patient_id IS NOT NULL)               AS patients_with_access_rows
FROM patients p
LEFT JOIN (SELECT DISTINCT patient_id FROM patient_access) pa ON pa.patient_id = p.id
WHERE p.deleted_at IS NULL;

-- ==== 2. candidates derived from the audit trail (read-only; review every row) ===========================
SELECT
    p.patient_code,
    p.id          AS patient_id,
    pr.id         AS doctor_profile_id,
    pr.email      AS doctor_email,
    a.time        AS created_at
FROM audit_logs a
JOIN patients p  ON p.id = a.after ->> 'patientId'
JOIN profiles pr ON pr.id::text = a.after ->> 'actorId'
JOIN user_roles ur ON ur.profile_id = pr.id
JOIN roles r       ON r.id = ur.role_id AND r.name = 'doctor'
WHERE a.action = 'patient.created'
  AND a.actor_role = 'doctor'
  AND p.deleted_at IS NULL
  AND pr.is_active AND pr.deleted_at IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM patient_access x
      WHERE x.patient_id = p.id AND x.profile_id = pr.id AND x.relationship = 'care_team')
ORDER BY a.time;

-- ==== 3. apply the reviewed candidates (WRITES - run only after section 2 looks right) ====================
-- Idempotent (ON CONFLICT DO NOTHING). `granted_by` is left NULL: nobody "granted" these; they restate the creation.
INSERT INTO patient_access (patient_id, profile_id, relationship, granted_by)
SELECT DISTINCT p.id, pr.id, 'care_team', NULL::uuid
FROM audit_logs a
JOIN patients p  ON p.id = a.after ->> 'patientId'
JOIN profiles pr ON pr.id::text = a.after ->> 'actorId'
JOIN user_roles ur ON ur.profile_id = pr.id
JOIN roles r       ON r.id = ur.role_id AND r.name = 'doctor'
WHERE a.action = 'patient.created'
  AND a.actor_role = 'doctor'
  AND p.deleted_at IS NULL
  AND pr.is_active AND pr.deleted_at IS NULL
ON CONFLICT (patient_id, profile_id, relationship) DO NOTHING
RETURNING patient_id, profile_id;
