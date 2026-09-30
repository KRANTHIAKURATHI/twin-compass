-- Phase 8: Reports tables.
--
-- Same convention as 0001_ocr_extractions.sql: `patients`, `twin_versions`,
-- `prediction_runs`, `simulation_runs`, `documents`, `timeline_events` and
-- `profiles` already exist in the target Supabase project and are not
-- tracked here. Apply this once against that Supabase Postgres instance
-- before using any /reports/* endpoint.
--
-- A "report" is an immutable snapshot: `content` freezes the aggregated
-- patient/twin/prediction/simulation/document data at the moment it was
-- generated, so an older version keeps reading exactly what it said at the
-- time even as the underlying patient record moves on. Generating again
-- inserts a new row with `version + 1` for the same (patient_id, type) - it
-- never updates a prior row, which is what keeps report history auditable.

CREATE TABLE IF NOT EXISTS reports (
    id uuid PRIMARY KEY,
    patient_id uuid NOT NULL REFERENCES patients(id),
    type text NOT NULL DEFAULT 'Clinical summary',
    title text NOT NULL,
    version integer NOT NULL,
    -- Always 'Final': generation is synchronous and completes or fails, so
    -- there is no in-between state to fabricate a 'Draft' for.
    status text NOT NULL DEFAULT 'Final',
    generated_by uuid REFERENCES profiles(id),
    generated_at timestamptz NOT NULL DEFAULT now(),
    content jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS reports_patient_id_idx ON reports (patient_id, generated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS reports_patient_type_version_idx ON reports (patient_id, type, version);

-- One row per export/download, kept forever as the audit trail of who
-- exported which report version and in what format.
CREATE TABLE IF NOT EXISTS report_downloads (
    id uuid PRIMARY KEY,
    report_id uuid NOT NULL REFERENCES reports(id),
    format text NOT NULL,
    downloaded_by uuid REFERENCES profiles(id),
    downloaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS report_downloads_report_id_idx ON report_downloads (report_id, downloaded_at DESC);
