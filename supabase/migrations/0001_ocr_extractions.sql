-- Phase 7: OCR extraction / review / approval tables.
--
-- No schema for `documents`, `document_versions`, `patients`, `twin_versions`
-- etc. is tracked in this repo (they were created directly in Supabase); this
-- migration follows the same "run by hand against the Supabase project"
-- convention rather than inventing a tracked baseline that doesn't match the
-- real database. Apply this once against the target Supabase Postgres
-- instance before using any /ocr/* endpoint.
--
-- One extraction row per OCR run over a document; its fields are reviewed
-- individually and only the ones a doctor/admin explicitly approves ever
-- reach `patients`. Rejected/approved rows are never deleted - they are the
-- audit trail for what OCR proposed and who decided what to do with it.

CREATE TABLE IF NOT EXISTS ocr_extractions (
    id uuid PRIMARY KEY,
    document_id uuid NOT NULL REFERENCES documents(id),
    patient_id uuid NOT NULL REFERENCES patients(id),
    -- 'Extracted' (awaiting review) | 'Approved' | 'Rejected'
    status text NOT NULL DEFAULT 'Extracted',
    -- Name of the OCR provider/model that produced this run; null until a
    -- real provider is configured (see backend app/services/ocr_provider.py).
    model text,
    extracted_at timestamptz NOT NULL DEFAULT now(),
    reviewed_by uuid REFERENCES profiles(id),
    reviewed_at timestamptz,
    reject_reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ocr_extractions_document_id_idx ON ocr_extractions (document_id, extracted_at DESC);
CREATE INDEX IF NOT EXISTS ocr_extractions_patient_id_idx ON ocr_extractions (patient_id);

CREATE TABLE IF NOT EXISTS ocr_extraction_fields (
    id uuid PRIMARY KEY,
    extraction_id uuid NOT NULL REFERENCES ocr_extractions(id) ON DELETE CASCADE,
    -- Machine key matching a patients column (see ocr.py FIELD_CATALOG) -
    -- never a free-form/invented field name.
    field_name text NOT NULL,
    label text NOT NULL,
    extracted_value text,
    -- Null when the OCR provider does not supply a confidence score - never
    -- fabricated to make the UI look more certain than the provider is.
    confidence double precision,
    -- 'pending' | 'approved' | 'rejected'
    status text NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ocr_extraction_fields_extraction_id_idx ON ocr_extraction_fields (extraction_id);
