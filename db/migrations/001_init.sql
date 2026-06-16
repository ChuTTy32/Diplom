-- Расширение TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ─── Метрики энтропии от агента ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS entropy_metrics (
    time        TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    file_path   TEXT             NOT NULL,
    entropy     DOUBLE PRECISION NOT NULL,
    file_size   BIGINT,
    alert       BOOLEAN          DEFAULT FALSE,
    host        TEXT             DEFAULT 'localhost'
);

SELECT create_hypertable('entropy_metrics', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_entropy_alert ON entropy_metrics (alert, time DESC);

-- ─── События бэкапов (RPO/RTO) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS backup_events (
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type      TEXT        NOT NULL,
    archive_name    TEXT,
    duration_sec    INTEGER,
    size_bytes      BIGINT,
    rpo_minutes     INTEGER,
    rto_minutes     INTEGER,
    error_msg       TEXT
);

SELECT create_hypertable('backup_events', 'time', if_not_exists => TRUE);

-- ─── Системные метрики ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system_metrics (
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cpu_pct         REAL,
    mem_pct         REAL,
    disk_pct        REAL,
    disk_write_mbps REAL,
    net_in_kb       REAL,
    net_out_kb      REAL
);

SELECT create_hypertable('system_metrics', 'time', if_not_exists => TRUE);
