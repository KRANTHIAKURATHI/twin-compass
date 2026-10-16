-- Per-field OCR extraction source: where the value's text came from.
-- Additive and nullable. NULL means unknown (all rows written before this
-- migration, and any value whose source was ambiguous). No backfill.

ALTER TABLE ocr_extraction_fields
    ADD COLUMN IF NOT EXISTS source text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ocr_extraction_fields_source_check'
          AND conrelid = 'ocr_extraction_fields'::regclass
    ) THEN
        ALTER TABLE ocr_extraction_fields
            ADD CONSTRAINT ocr_extraction_fields_source_check
            CHECK (source IS NULL OR source IN ('text-layer', 'ocr'));
    END IF;
END
$$;
