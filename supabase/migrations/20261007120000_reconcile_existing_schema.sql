-- Reconcile schema changes already present in production.
-- This migration is additive and idempotent for clean local resets.
-- It does not recreate baseline tables, modify profiles, or insert data.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS mime_type    text,
    ADD COLUMN IF NOT EXISTS size_bytes   bigint,
    ADD COLUMN IF NOT EXISTS storage_path text,
    ADD COLUMN IF NOT EXISTS uploaded_by  text,
    ADD COLUMN IF NOT EXISTS created_at   text,
    ADD COLUMN IF NOT EXISTS updated_at   text;

ALTER TABLE document_versions
    ADD COLUMN IF NOT EXISTS created_at   text,
    ADD COLUMN IF NOT EXISTS storage_path text,
    ADD COLUMN IF NOT EXISTS size_bytes   bigint;

ALTER TABLE reports
    ADD COLUMN IF NOT EXISTS generated_by text,
    ADD COLUMN IF NOT EXISTS generated_at text,
    ADD COLUMN IF NOT EXISTS content     jsonb,
    ADD COLUMN IF NOT EXISTS created_at  text;

CREATE TABLE IF NOT EXISTS report_downloads (
    id            text PRIMARY KEY DEFAULT (gen_random_uuid())::text,
    report_id     text NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    format        text NOT NULL,
    downloaded_by text,
    downloaded_at text NOT NULL
);

CREATE INDEX IF NOT EXISTS report_downloads_report_id_idx
    ON report_downloads (report_id, downloaded_at DESC);
