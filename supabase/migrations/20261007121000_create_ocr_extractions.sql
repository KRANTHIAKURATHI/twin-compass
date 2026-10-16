-- OCR extraction and review tables using the production text-ID schema.
-- Profiles and role tables are managed by the backend identity migrations.

CREATE TABLE IF NOT EXISTS ocr_extractions (
    id text PRIMARY KEY,
    document_id text NOT NULL REFERENCES documents(id),
    patient_id text NOT NULL REFERENCES patients(id),
    status text NOT NULL DEFAULT 'Extracted',
    model text,
    extracted_at timestamptz NOT NULL DEFAULT now(),
    reviewed_by uuid REFERENCES profiles(id),
    reviewed_at timestamptz,
    reject_reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ocr_extractions_document_id_idx
    ON ocr_extractions (document_id, extracted_at DESC);

CREATE INDEX IF NOT EXISTS ocr_extractions_patient_id_idx
    ON ocr_extractions (patient_id);

CREATE TABLE IF NOT EXISTS ocr_extraction_fields (
    id text PRIMARY KEY,
    extraction_id text NOT NULL REFERENCES ocr_extractions(id) ON DELETE CASCADE,
    field_name text NOT NULL,
    label text NOT NULL,
    extracted_value text,
    confidence double precision,
    status text NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ocr_extraction_fields_extraction_id_idx
    ON ocr_extraction_fields (extraction_id);

ALTER TABLE ocr_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE ocr_extraction_fields ENABLE ROW LEVEL SECURITY;

CREATE POLICY ocr_extractions_read_clinical_roles
    ON ocr_extractions FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.profile_id = auth.uid()
              AND r.name IN ('doctor', 'researcher', 'admin')
        )
    );

CREATE POLICY ocr_extractions_write_clinical_roles
    ON ocr_extractions FOR INSERT TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.profile_id = auth.uid()
              AND r.name IN ('doctor', 'admin')
        )
    );

CREATE POLICY ocr_extractions_review_clinical_roles
    ON ocr_extractions FOR UPDATE TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.profile_id = auth.uid()
              AND r.name IN ('doctor', 'admin')
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.profile_id = auth.uid()
              AND r.name IN ('doctor', 'admin')
        )
    );

CREATE POLICY ocr_extraction_fields_read_clinical_roles
    ON ocr_extraction_fields FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.profile_id = auth.uid()
              AND r.name IN ('doctor', 'researcher', 'admin')
        )
    );

CREATE POLICY ocr_extraction_fields_write_clinical_roles
    ON ocr_extraction_fields FOR INSERT TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.profile_id = auth.uid()
              AND r.name IN ('doctor', 'admin')
        )
    );

CREATE POLICY ocr_extraction_fields_review_clinical_roles
    ON ocr_extraction_fields FOR UPDATE TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.profile_id = auth.uid()
              AND r.name IN ('doctor', 'admin')
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.profile_id = auth.uid()
              AND r.name IN ('doctor', 'admin')
        )
    );
