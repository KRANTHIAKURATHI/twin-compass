-- 0004: make the Reports feature work on the LIVE text-id schema.
--
-- Supersedes 0002_reports.sql for this database; 0002 must NOT be applied. It
-- declares uuid keys against `patients.id` (text here), and its
-- `CREATE TABLE IF NOT EXISTS reports` would silently skip the legacy table,
-- leaving the columns the router reads missing.
--
-- Live `reports` (legacy): id, title, patient_id, patient_name, type, created,
-- version, status, downloads. This migration is additive only: existing rows
-- and columns are untouched, and the legacy `created` value remains the date
-- shown for rows that have no `generated_at` (the router COALESCEs the two).
-- Legacy rows get NULL `content`; nothing is back-filled or invented.
--
-- Ids and timestamps are text, matching the rest of the live schema.
-- `generated_by` / `downloaded_by` hold the auth user id as text with no
-- foreign key (profiles.id is uuid; the router compares via CAST).

ALTER TABLE reports
    ADD COLUMN IF NOT EXISTS generated_by text,
    ADD COLUMN IF NOT EXISTS generated_at text,
    ADD COLUMN IF NOT EXISTS content jsonb,
    ADD COLUMN IF NOT EXISTS created_at text;

CREATE TABLE IF NOT EXISTS report_downloads (
    id text PRIMARY KEY DEFAULT (gen_random_uuid())::text,
    report_id text NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    format text NOT NULL,
    downloaded_by text,
    downloaded_at text NOT NULL
);

CREATE INDEX IF NOT EXISTS report_downloads_report_id_idx
    ON report_downloads (report_id, downloaded_at DESC);
