-- C4 (Phase 6.2-A): row-level security for patient-linked clinical data, built on `patient_access` (Phase 6.1).
--
-- Purpose: defense in depth against the Supabase Data API. The backend connects as `postgres` (BYPASSRLS) and keeps
-- enforcing patient access in application code; these policies only constrain `authenticated` callers of the Data
-- API (and `anon`, which gets nothing). No INSERT/UPDATE/DELETE policy exists for any role: writes are closed to the
-- Data API and happen only through the backend.
--
-- Access rule (mirrors services/patient_access.py):
--   admin      -> every row
--   doctor     -> rows of patients with a 'care_team' patient_access row for that doctor
--   patient    -> rows of the patient with a 'self' row for that login
--   researcher -> nothing identified, ever (a stray access row for a researcher grants nothing)
--   anon       -> nothing (no policy; table grants are also revoked below when the role exists)
--
-- Why a function: `patient_access`, `user_roles` and `roles` have RLS enabled and (deliberately) no policies, so a policy
-- subquery run as the caller could not read them. `public.can_read_patient` is SECURITY DEFINER (owner = the role that
-- runs this migration, which bypasses RLS) with a pinned search_path, EXECUTE only for `authenticated`, and it can only
-- answer yes/no for the caller (auth.uid()) - it returns no rows and takes no user argument, so it cannot be used to
-- probe anyone else's access. `patient_access` itself keeps RLS with no policies, so there is no recursive evaluation.
--
-- Scope: the approved clinical tables only (not every table). audit_logs, notifications and registry tables are left as
-- they are. Existing OCR policies were role-only (any doctor/researcher/admin) and also granted INSERT/UPDATE; they are
-- replaced by the patient-scoped SELECT policy below.
-- No data is modified. Idempotent: functions are CREATE OR REPLACE, policies are dropped then created, RLS/REVOKE repeat safely.

CREATE OR REPLACE FUNCTION public.can_read_patient(p_patient_id text)
RETURNS boolean
LANGUAGE plpgsql          -- plpgsql: the body is not validated at creation, so non-Supabase databases (no auth schema) still migrate
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    uid uuid := auth.uid();
BEGIN
    IF uid IS NULL THEN
        RETURN false;
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.user_roles ur JOIN public.roles r ON r.id = ur.role_id
        WHERE ur.profile_id = uid AND r.name = 'admin'
    ) THEN
        RETURN true;
    END IF;
    IF p_patient_id IS NULL THEN
        RETURN false;
    END IF;
    RETURN EXISTS (
        SELECT 1
        FROM public.patient_access pa
        JOIN public.user_roles ur ON ur.profile_id = pa.profile_id
        JOIN public.roles r ON r.id = ur.role_id
        WHERE pa.patient_id = p_patient_id
          AND pa.profile_id = uid
          AND ((pa.relationship = 'care_team' AND r.name = 'doctor')
            OR (pa.relationship = 'self' AND r.name = 'patient'))
    );
END;
$$;

REVOKE ALL ON FUNCTION public.can_read_patient(text) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION public.can_read_patient(text) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT EXECUTE ON FUNCTION public.can_read_patient(text) TO authenticated;
    END IF;
END
$$;

DO $$
DECLARE
    -- table, patient column on the table itself
    direct_tables text[][] := ARRAY[
        ['patients', 'id'], ['appointments', 'patient_id'], ['documents', 'patient_id'], ['imaging_studies', 'patient_id'],
        ['lab_results', 'patient_id'], ['ocr_extractions', 'patient_id'], ['patient_report_refs', 'patient_id'],
        ['prediction_runs', 'patient_id'], ['reports', 'patient_id'], ['simulation_runs', 'patient_id'],
        ['timeline_events', 'patient_id'], ['treatment_plans', 'patient_id'], ['twin_snapshots', 'patient_id'],
        ['twin_versions', 'patient_id']
    ];
    -- child table, FK column, parent table (its patient_id is the owner)
    child_tables text[][] := ARRAY[
        ['document_versions', 'document_id', 'documents'], ['ocr_fields', 'document_id', 'documents'],
        ['ocr_extraction_fields', 'extraction_id', 'ocr_extractions'], ['report_versions', 'report_id', 'reports'],
        ['report_downloads', 'report_id', 'reports'], ['download_records', 'report_id', 'reports']
    ];
    i int;
    t text;
BEGIN
    -- replace the earlier role-only OCR policies (read for researchers too; INSERT/UPDATE for any doctor)
    FOREACH t IN ARRAY ARRAY['ocr_extractions', 'ocr_extraction_fields'] LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_read_clinical_roles', t);
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_write_clinical_roles', t);
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_review_clinical_roles', t);
    END LOOP;

    FOR i IN 1 .. array_length(direct_tables, 1) LOOP
        t := direct_tables[i][1];
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_patient_scope', t);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT TO authenticated USING (public.can_read_patient(%I::text))',
            t || '_patient_scope', t, direct_tables[i][2]);
    END LOOP;

    FOR i IN 1 .. array_length(child_tables, 1) LOOP
        t := child_tables[i][1];
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_patient_scope', t);
        -- the owner is reached through the parent row; the parent's own policy is evaluated for the caller as well
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM public.%I p WHERE p.id = %I.%I AND public.can_read_patient(p.patient_id)))',
            t || '_patient_scope', t, child_tables[i][3], t, child_tables[i][2]);
    END LOOP;

    -- anon never reads clinical data: drop its table privileges where the Supabase role exists
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        FOR i IN 1 .. array_length(direct_tables, 1) LOOP
            EXECUTE format('REVOKE ALL ON public.%I FROM anon', direct_tables[i][1]);
        END LOOP;
        FOR i IN 1 .. array_length(child_tables, 1) LOOP
            EXECUTE format('REVOKE ALL ON public.%I FROM anon', child_tables[i][1]);
        END LOOP;
        REVOKE ALL ON public.patient_access FROM anon;
    END IF;
END
$$;
