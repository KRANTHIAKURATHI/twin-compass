-- ============================================================================
-- OncoTwin — Supabase/Postgres schema
--
-- Mirrors the SQLAlchemy models in backend/app/models.py 1:1 (same table
-- and column names), which in turn mirror every entity in
-- src/types/models.ts (the frontend's API contract). Column names are
-- snake_case; the backend's Pydantic `Camel` schemas translate them to/from
-- the camelCase JSON the frontend expects, so nothing here needs to change
-- to match the UI. Kept in sync with the latest Alembic revision
-- (app/migrations/versions/4f2747671a6f_audit_log_enrichment.py, on top of
-- the db318e221391 baseline) as of this file's last edit — if you add new
-- columns via `alembic revision --autogenerate` later, mirror them here too,
-- or this file will drift.
--
-- Usage:
--   1. Open the Supabase SQL editor (or `psql` against your project) and run
--      this whole file once, on an empty database.
--   2. Point the backend's DATABASE_URL at the Supabase Postgres connection
--      string (see backend/README.md "Switching to Supabase").
--   3. Run `alembic stamp head` from backend/ against that same
--      DATABASE_URL. This tells Alembic "these tables already exist at the
--      baseline revision" without re-running any DDL, so the next
--      `alembic upgrade head` (which also runs automatically on app
--      startup) is a no-op instead of erroring on tables that already exist.
--   4. Start the backend as usual.
--   5. Run `python -m app.ml.train` once (or let the app do it on first
--      boot) and restart, so `seed.py` inserts the admin account and the
--      real model/training metadata rows referenced below.
--
-- IDs are text UUIDs (not `uuid` type) because the backend generates them in
-- Python (`uuid.uuid4()` as a string) rather than relying on a DB default —
-- this keeps SQLite (dev) and Postgres (prod) byte-for-byte compatible.
-- `gen_random_uuid()` defaults are included anyway as a safety net for rows
-- inserted directly via SQL/Supabase Studio.
-- ============================================================================

create extension if not exists pgcrypto;

-- ------------------------------------------------------------------ Identity & access --

create table users (
    id             text primary key default gen_random_uuid()::text,
    name           text not null,
    email          text not null unique,
    password_hash  text not null,
    role           text not null default 'doctor'
                       check (role in ('doctor', 'patient', 'researcher', 'admin')),
    title          text,
    hospital       text,
    department     text,
    specialization text,
    phone          text,
    avatar_url     text,
    status         text default 'Active',
    last_active    text,
    created_at     text
);
create index idx_users_email on users (email);

create table password_reset_tokens (
    id         text primary key default gen_random_uuid()::text,
    user_id    text not null references users (id) on delete cascade,
    token      text not null unique,
    expires_at timestamptz not null,
    used       boolean default false
);
create index idx_password_reset_tokens_token on password_reset_tokens (token);
create index idx_password_reset_tokens_user on password_reset_tokens (user_id);

-- ------------------------------------------------------------------ Clinical core --

-- Single-row counter allocating human-readable PT-1000-style patient codes.
-- A dedicated table (rather than a Postgres SEQUENCE) keeps allocation
-- logic identical between SQLite (dev, no SEQUENCE support) and Postgres.
create table patient_code_counters (
    id         integer primary key default 1,
    next_value integer default 1000
);

create table patients (
    id                   text primary key default gen_random_uuid()::text,
    patient_code         text unique,
    name                 text not null,
    age                  integer default 0,
    gender               text default '',
    phone                text default '',
    email                text default '',
    hospital             text default '',
    stage                text default 'I'
                             check (stage in ('0', 'I', 'II', 'III', 'IV')),
    tumor_size_mm        double precision default 0,
    er_status            text default 'Negative' check (er_status in ('Positive', 'Negative')),
    pr_status            text default 'Negative' check (pr_status in ('Positive', 'Negative')),
    her2_status          text default 'Negative' check (her2_status in ('Positive', 'Negative')),
    ki67                 double precision default 10,
    grade                integer default 1 check (grade in (1, 2, 3)),
    nodes_involved       integer default 0,
    current_treatment    text default '',
    status               text default 'Monitoring'
                             check (status in ('In Treatment', 'Remission', 'Monitoring', 'Critical')),
    risk                 text default 'low' check (risk in ('low', 'moderate', 'high')),
    survival_probability double precision default 0.9,
    last_updated         text,
    diagnosed_on         text,
    twin_status          text default 'Synced'
                             check (twin_status in ('Synced', 'Recalculating', 'Stale')),
    history              jsonb default '[]',
    notes                text default '',
    created_by           text references users (id) on delete set null,
    created_at           text,
    deleted_at           timestamptz,
    -- Medical history
    comorbidities        jsonb default '[]',
    allergies            jsonb default '[]',
    current_medications  jsonb default '[]',
    previous_treatments  jsonb default '[]',
    family_history       text default '',
    smoking_status       text default 'Unknown'
                             check (smoking_status in ('Never', 'Former', 'Current', 'Unknown')),
    alcohol_use          text default 'Unknown'
                             check (alcohol_use in ('None', 'Occasional', 'Regular', 'Unknown')),
    surgical_history     jsonb default '[]'
);
create index idx_patients_name on patients (name);
create index idx_patients_hospital on patients (hospital);
create index idx_patients_created_by on patients (created_by);
create index idx_patients_patient_code on patients (patient_code);
create index idx_patients_deleted_at on patients (deleted_at);

create table timeline_events (
    id         text primary key default gen_random_uuid()::text,
    patient_id text not null references patients (id) on delete cascade,
    date       text,
    title      text default '',
    detail     text default '',
    kind       text default 'note' check (kind in ('diagnosis', 'treatment', 'scan', 'note'))
);
create index idx_timeline_events_patient on timeline_events (patient_id);

create table patient_report_refs (
    id         text primary key default gen_random_uuid()::text,
    patient_id text not null references patients (id) on delete cascade,
    name       text default '',
    type       text default '',
    date       text,
    size       text default '0 KB'
);
create index idx_patient_report_refs_patient on patient_report_refs (patient_id);

create table lab_results (
    id         text primary key default gen_random_uuid()::text,
    patient_id text not null references patients (id) on delete cascade,
    date       text,
    panel      text default '',
    marker     text default '',
    value      text default '',
    unit       text default '',
    range      text default '',
    flag       text default 'normal'
);
create index idx_lab_results_patient on lab_results (patient_id);

create table imaging_studies (
    id          text primary key default gen_random_uuid()::text,
    patient_id  text not null references patients (id) on delete cascade,
    modality    text default 'MRI',
    region      text default '',
    date        text,
    finding     text default '',
    radiologist text default '',
    status      text default 'Pending'
);
create index idx_imaging_studies_patient on imaging_studies (patient_id);

-- ------------------------------------------------------------------ Digital twin --

create table twin_versions (
    id            text primary key default gen_random_uuid()::text,
    patient_id    text not null references patients (id) on delete cascade,
    version       text default 'v1',
    created_at    text,
    status        text default 'Active'
                      check (status in ('Active', 'Superseded', 'Archived', 'Draft')),
    author        text default '',
    summary       text default '',
    tumor_size_mm double precision default 0,
    survival      double precision default 0.9,
    risk          text default 'low' check (risk in ('low', 'moderate', 'high')),
    model         text default '',
    snapshot      jsonb default '{}'
);
create index idx_twin_versions_patient on twin_versions (patient_id);

create table twin_snapshots (
    id         text primary key default gen_random_uuid()::text,
    patient_id text not null references patients (id) on delete cascade,
    version    text default 'v1',
    taken_at   text,
    trigger    text default 'manual',
    size       text default '0 KB'
);
create index idx_twin_snapshots_patient on twin_snapshots (patient_id);

-- ------------------------------------------------------------------ Predictions & simulations --

create table prediction_runs (
    id           text primary key default gen_random_uuid()::text,
    patient_id   text not null references patients (id) on delete cascade,
    date         text,
    twin_version text default 'v1',
    model        text default '',
    survival     double precision default 0.9,
    recurrence   double precision default 0.1,
    response     text default 'Favorable',
    confidence   double precision default 0.8,
    status       text default 'Complete'
                     check (status in ('Complete', 'Low confidence', 'Superseded'))
);
create index idx_prediction_runs_patient on prediction_runs (patient_id);

create table simulation_runs (
    id           text primary key default gen_random_uuid()::text,
    date         text,
    patient_id   text not null references patients (id) on delete cascade,
    patient_name text default '',
    twin_version text default 'v1',
    model        text default '',
    selected     text default '',
    compared     jsonb default '[]',
    decision     text default 'Under review'
                     check (decision in ('Promoted to plan', 'Under review', 'Rejected')),
    decided_by   text default '',
    notes        text default '',
    survival     double precision default 0.9,
    response     double precision default 0.5,
    confidence   double precision default 0.7,
    scenarios    jsonb default '[]'
);
create index idx_simulation_runs_patient on simulation_runs (patient_id);

-- ------------------------------------------------------------------ Documents & OCR --

create table documents (
    id           text primary key default gen_random_uuid()::text,
    name         text not null,
    category     text default 'Blood' check (category in ('MRI', 'CT', 'PET', 'Biopsy', 'Blood')),
    patient_id   text references patients (id) on delete set null,
    patient_name text default '',
    date         text,
    size         text default '0 KB',
    version      integer default 1,
    status       text default 'Pending OCR'
                     check (status in ('Verified', 'Pending OCR', 'Needs review'))
);
create index idx_documents_patient on documents (patient_id);

create table document_versions (
    id          text primary key default gen_random_uuid()::text,
    document_id text not null references documents (id) on delete cascade,
    version     integer default 1,
    date        text,
    author      text default '',
    note        text default ''
);
create index idx_document_versions_document on document_versions (document_id);

create table ocr_fields (
    id           text primary key default gen_random_uuid()::text,
    document_id  text not null references documents (id) on delete cascade,
    field        text default '',
    value        text default '',
    confidence   double precision default 0.5,
    model        text default 'ocr-heuristic-v1',
    extracted_at text,
    approved     boolean default false,
    rejected     boolean default false
);
create index idx_ocr_fields_document on ocr_fields (document_id);

-- ------------------------------------------------------------------ Reports --

create table reports (
    id           text primary key default gen_random_uuid()::text,
    title        text default '',
    patient_id   text references patients (id) on delete set null,
    patient_name text default '',
    type         text default 'Clinical summary'
                     check (type in ('Clinical summary', 'Tumor board packet', 'Model audit', 'Cohort summary')),
    created      text,
    version      integer default 1,
    status       text default 'Draft' check (status in ('Final', 'Draft', 'Archived')),
    downloads    integer default 0
);
create index idx_reports_patient on reports (patient_id);

create table report_versions (
    id        text primary key default gen_random_uuid()::text,
    report_id text not null references reports (id) on delete cascade,
    version   integer default 1,
    date      text,
    author    text default '',
    note      text default ''
);
create index idx_report_versions_report on report_versions (report_id);

create table download_records (
    id        text primary key default gen_random_uuid()::text,
    report_id text not null references reports (id) on delete cascade,
    format    text default 'pdf' check (format in ('pdf', 'csv')),
    by        text default '',
    date      text
);
create index idx_download_records_report on download_records (report_id);

-- ------------------------------------------------------------------ Care coordination --

create table appointments (
    id         text primary key default gen_random_uuid()::text,
    title      text default '',
    doctor     text default '',
    patient_id text references patients (id) on delete set null,
    date       text,
    time       text default '09:00',
    location   text default '',
    status     text default 'Scheduled'
                   check (status in ('Confirmed', 'Scheduled', 'Completed', 'Cancelled'))
);
create index idx_appointments_patient on appointments (patient_id);

create table treatment_plans (
    id           text primary key default gen_random_uuid()::text,
    patient_id   text not null unique references patients (id) on delete cascade,
    regimen      text default '',
    cycle        integer default 1,
    total_cycles integer default 6,
    started_on   text,
    next_dose    text,
    adherence    double precision default 1.0,
    side_effects jsonb default '[]',
    medications  jsonb default '[]'
);

create table notifications (
    id            text primary key default gen_random_uuid()::text,
    user_id       text references users (id) on delete cascade,
    audience_role text,
    title         text default '',
    body          text default '',
    time          text,
    unread        boolean default true,
    type          text
);
create index idx_notifications_user on notifications (user_id);
create index idx_notifications_audience_role on notifications (audience_role);

-- ------------------------------------------------------------------ Administration --

create table hospitals (
    id       text primary key default gen_random_uuid()::text,
    name     text default '',
    city     text default '',
    beds     integer default 0,
    doctors  integer default 0,
    patients integer default 0,
    status   text default 'Active'
);

create table departments (
    id           text primary key default gen_random_uuid()::text,
    name         text default '',
    head         text default '',
    staff        integer default 0,
    active_cases integer default 0
);

create table audit_logs (
    id         text primary key default gen_random_uuid()::text,
    time       text,
    actor      text default '',
    actor_role text default '',
    action     text default '',
    target     text default '',
    before     jsonb,
    after      jsonb,
    ip         text default ''
);
create index idx_audit_logs_time on audit_logs (time);

create table permissions (
    id         text primary key default gen_random_uuid()::text,
    capability text not null unique,
    doctor     boolean default false,
    patient    boolean default false,
    technician boolean default false,
    admin      boolean default true
);

-- ------------------------------------------------------------------ Research --

create table datasets (
    id         text primary key default gen_random_uuid()::text,
    name       text default '',
    records    integer default 0,
    modalities text default '',
    updated    text
);

create table training_runs (
    id       text primary key default gen_random_uuid()::text,
    model    text default '',
    started  text,
    duration text default '',
    epochs   integer default 1,
    loss     double precision default 0.0,
    status   text default 'Complete'
);

create table model_versions (
    id       text primary key default gen_random_uuid()::text,
    version  text default 'v1.0.0',
    released text,
    auc      double precision default 0.0,
    notes    text default '',
    stage    text default 'Production'
);

create table ml_models (
    id      text primary key default gen_random_uuid()::text,
    name    text default '',
    version text default 'v1.0.0',
    task    text default 'Malignancy risk classification',
    auc     double precision default 0.0,
    status  text default 'Production'
);

create table performance_points (
    id        text primary key default gen_random_uuid()::text,
    month     text default '',
    auc       double precision default 0.0,
    precision double precision default 0.0,
    recall    double precision default 0.0
);

-- ============================================================================
-- Row Level Security: left disabled (off by default in a fresh Supabase
-- Postgres table). The backend connects with the Postgres service-role
-- connection string and does its own JWT-based authorization in
-- app/deps.py (get_current_user / role checks per router), so RLS policies
-- are not required for the app to function. Enable + write policies here
-- only if you also want to query these tables directly from the browser via
-- supabase-js with the anon key.
-- ============================================================================
