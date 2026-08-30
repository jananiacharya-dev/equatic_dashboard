-- Equatic plant dashboard schema
-- Postgres 16. Applied automatically on first container start.

-- ============ 1. METADATA (drives the UI) ============

CREATE TABLE sensor_inventory (
    tag_id          TEXT PRIMARY KEY,
    source_tag_id   TEXT,                -- vendor's name for this tag; NULL until their list arrives
    instrument_type TEXT NOT NULL,       -- PT, TT, FM, pHT, LS, EPC, V, I
    measurement     TEXT NOT NULL,
    units           TEXT,
    range_min       DOUBLE PRECISION,
    range_max       DOUBLE PRECISION,
    subsystem       TEXT NOT NULL,       -- electrolyzer, effluent, carbonation, intake, main_header, drainage, pressure_control
    stack_group     TEXT,                -- SG-1..SG-4, NULL for system-level tags
    stack_id        TEXT,                -- ES-01..ES-24, NULL above stack level
    cell_number     INTEGER,             -- 1..52 for C2C voltage tags, else NULL
    signal_class    TEXT NOT NULL,       -- analog, discrete, control_feedback
    data_source     TEXT NOT NULL DEFAULT 'wincc',  -- wincc, windaq, manual
    display_page    TEXT,                -- NULL = not shown (e.g. EPC until PV confirmed)
    display_group   TEXT
);

CREATE TABLE metric_registry (
    metric_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    formula_ref     TEXT,                -- 'pending: Babette' until formulas arrive
    units           TEXT,
    display_page    TEXT,
    level           TEXT NOT NULL DEFAULT '2'   -- '1', '2', or 'both'
);

-- ============ 2. TIME SERIES ============

CREATE TABLE sensor_readings (
    tag_id     TEXT NOT NULL REFERENCES sensor_inventory(tag_id),
    ts_utc     TIMESTAMPTZ NOT NULL,
    value_avg  DOUBLE PRECISION,
    value_min  DOUBLE PRECISION,
    value_max  DOUBLE PRECISION,
    quality    TEXT NOT NULL DEFAULT 'good',
    PRIMARY KEY (tag_id, ts_utc)
);
-- The PK doubles as the index every dashboard query uses:
-- WHERE tag_id IN (...) AND ts_utc BETWEEN ... is an index-only range scan.

CREATE TABLE metric_values (
    metric_id   TEXT NOT NULL REFERENCES metric_registry(metric_id),
    ts_utc      TIMESTAMPTZ NOT NULL,
    value       DOUBLE PRECISION,
    resolution  TEXT NOT NULL DEFAULT 'raw',   -- raw, hourly, daily
    stack_group TEXT NOT NULL DEFAULT '',      -- SG-1..SG-4 for per-group metrics; '' for plant-wide (ce, uptime, gcdr_day)
    PRIMARY KEY (metric_id, ts_utc, resolution, stack_group)
);

CREATE TABLE state_events (
    tag_id  TEXT NOT NULL REFERENCES sensor_inventory(tag_id),
    ts_utc  TIMESTAMPTZ NOT NULL,
    state   TEXT NOT NULL,               -- HIGH, LOW, ALARM, OK, ...
    PRIMARY KEY (tag_id, ts_utc)
);

-- ============ 3. HUMAN-ENTERED ============

CREATE TABLE users (
    user_id  SERIAL PRIMARY KEY,
    name     TEXT NOT NULL,
    email    TEXT UNIQUE NOT NULL,
    role     TEXT NOT NULL CHECK (role IN ('admin', 'operator')),
    password_hash TEXT NOT NULL
);

CREATE TABLE annotations (
    annotation_id SERIAL PRIMARY KEY,
    ts_utc        TIMESTAMPTZ NOT NULL,
    event_type    TEXT NOT NULL,         -- flush, outage, config_change, note
    description   TEXT,
    test_run_id   TEXT,
    created_by    INTEGER REFERENCES users(user_id)
);
CREATE INDEX idx_annotations_ts ON annotations (ts_utc);

CREATE TABLE manual_samples (
    sample_id              SERIAL PRIMARY KEY,
    sample_ts              TIMESTAMPTZ NOT NULL,
    collector_id           INTEGER REFERENCES users(user_id),
    analyst_id             INTEGER REFERENCES users(user_id),
    analysis_type          TEXT,
    analysis_ts            TIMESTAMPTZ,
    instrumentation_status TEXT,
    data_health_status     TEXT,
    notes                  TEXT
);

CREATE TABLE qaqc_records (
    record_id        SERIAL PRIMARY KEY,
    instrument_tag   TEXT REFERENCES sensor_inventory(tag_id),
    calibration_date DATE NOT NULL,
    result           TEXT,
    next_due         DATE,
    performed_by     INTEGER REFERENCES users(user_id)
);

CREATE TABLE documents (
    doc_id      SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    source      TEXT NOT NULL CHECK (source IN ('upload', 'gdrive')),
    url_or_path TEXT NOT NULL,
    linked_type TEXT,                    -- sample, instrument, annotation
    linked_id   TEXT
);

-- ============ 4. INTEGRITY ============

CREATE TABLE corrections (
    correction_id   SERIAL PRIMARY KEY,
    tag_id          TEXT NOT NULL REFERENCES sensor_inventory(tag_id),
    ts_start        TIMESTAMPTZ NOT NULL,
    ts_end          TIMESTAMPTZ NOT NULL,
    corrected_value DOUBLE PRECISION,
    reason          TEXT NOT NULL,
    corrected_by    INTEGER REFERENCES users(user_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Metadata lookups the UI makes constantly:
CREATE INDEX idx_inventory_page  ON sensor_inventory (display_page, display_group);
CREATE INDEX idx_inventory_stack ON sensor_inventory (stack_group, stack_id, cell_number);
