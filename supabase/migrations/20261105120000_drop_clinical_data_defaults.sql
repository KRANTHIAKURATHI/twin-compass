-- Remove schema defaults that make UNRECORDED clinical information look like recorded or model-generated data.
--
-- Before this migration an INSERT that omitted one of these columns silently stored 'I', 1, 'Negative', 0, 10, 0.9,
-- 'low', ... which later passed for a real measurement or a prediction. Every active writer (routers/clinical.py,
-- twins.py, predictions.py) supplies these columns explicitly, so dropping the defaults changes nothing for them;
-- an omitted column is now NULL ("not recorded").
--
-- DATA IS NOT TOUCHED. No UPDATE, no NULL-ing of existing 'I' / 1 / 'Negative' / 0.9 values: such a value can be a real
-- recorded one, and the existing rows carry nothing that tells the two apart (see the column comments below).
-- Not changed on purpose: status columns ('Monitoring', 'Active', 'Complete' ...), twin_status, and the empty-text /
-- empty-json defaults - they describe workflow state or "nothing", not a clinical measurement.
-- Idempotent: DROP DEFAULT on a column without a default is a no-op.

ALTER TABLE patients
    ALTER COLUMN age                  DROP DEFAULT,
    ALTER COLUMN stage                DROP DEFAULT,
    ALTER COLUMN tumor_size_mm        DROP DEFAULT,
    ALTER COLUMN er_status            DROP DEFAULT,
    ALTER COLUMN pr_status            DROP DEFAULT,
    ALTER COLUMN her2_status          DROP DEFAULT,
    ALTER COLUMN ki67                 DROP DEFAULT,
    ALTER COLUMN grade                DROP DEFAULT,
    ALTER COLUMN nodes_involved       DROP DEFAULT,
    ALTER COLUMN risk                 DROP DEFAULT,
    ALTER COLUMN survival_probability DROP DEFAULT;

ALTER TABLE twin_versions
    ALTER COLUMN tumor_size_mm DROP DEFAULT,
    ALTER COLUMN survival      DROP DEFAULT,
    ALTER COLUMN risk          DROP DEFAULT;

ALTER TABLE prediction_runs
    ALTER COLUMN survival   DROP DEFAULT,
    ALTER COLUMN recurrence DROP DEFAULT,
    ALTER COLUMN response   DROP DEFAULT,
    ALTER COLUMN confidence DROP DEFAULT;

ALTER TABLE simulation_runs
    ALTER COLUMN survival   DROP DEFAULT,
    ALTER COLUMN response   DROP DEFAULT,
    ALTER COLUMN confidence DROP DEFAULT;

COMMENT ON COLUMN patients.stage IS
    'NULL = not recorded. Rows written before 20261105120000 may hold the former schema default ''I'' (and 1 / ''Negative'' / 0 / 10 / 0.9 / ''low'' in sibling columns) without having been recorded; this cannot be established from the row.';
COMMENT ON COLUMN twin_versions.survival IS
    'NULL = no value. Copied from patients.survival_probability by resync/restore, NOT a model output (twin_versions.model = ''Patient record snapshot''). Rows before 20261105120000 may hold the former default 0.9.';
COMMENT ON COLUMN prediction_runs.survival IS
    'Model-generated only when prediction_runs.model names a model; rows labelled ''Twin state snapshot (no model attached)'' carry no model output. Rows before 20261105120000 may hold former defaults.';
