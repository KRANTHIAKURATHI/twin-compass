-- Documents: add the columns the active /documents router reads and writes.
--
-- The live `documents` / `document_versions` tables come from the original
-- backend/supabase_schema.sql layout (text ids; `date` / `size` text columns;
-- no storage metadata). The active router (backend/app/api/v1/routers/
-- documents.py) stores the file in Supabase Storage and persists its
-- metadata, so it needs the columns below. Without them GET /documents fails
-- with `UndefinedColumnError: column d.mime_type does not exist`.
--
-- Additive only: every column is nullable with no default, no existing row is
-- rewritten, and no constraint is added, changed or dropped. Existing rows
-- keep working - the router falls back to the legacy `date` column and
-- reports a missing file as such.
--
-- Types follow the live schema's conventions: text timestamps (the router
-- writes ISO-8601 strings, as for twin_versions.created_at) and text ids
-- (uploaded_by holds the uploader's profile id as text, matching
-- patients.created_by; no foreign key, same as there).
--
-- Run once by hand against the Supabase project (same convention as 0001 and
-- 0002). Idempotent: safe to re-run.

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
