-- Migration 0001: Initial schema (user_version = 1)
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = OFF;
PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS repos (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'python',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    deleted_at INTEGER NULL,
    metadata TEXT NULL
);

CREATE TABLE IF NOT EXISTS fingerprints (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    vector_dims INTEGER NOT NULL DEFAULT 32,
    model_blob BLOB NOT NULL,
    commit_hash TEXT NOT NULL,
    commit_count INTEGER NOT NULL DEFAULT 0,
    file_count INTEGER NOT NULL DEFAULT 0,
    build_duration_s REAL NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    deleted_at INTEGER NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_fingerprints_repo ON fingerprints(repo_id, is_active);

CREATE TABLE IF NOT EXISTS feature_vectors (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    fingerprint_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    unit_type TEXT NOT NULL,
    unit_name TEXT NULL,
    language TEXT NOT NULL,
    vector BLOB NOT NULL,
    vector_dims INTEGER NOT NULL DEFAULT 32,
    body_hash TEXT NULL,
    line_start INTEGER NULL,
    line_end INTEGER NULL,
    commit_hash TEXT NULL,
    created_at INTEGER NOT NULL,
    deleted_at INTEGER NULL
);
CREATE INDEX IF NOT EXISTS idx_fv_repo_file ON feature_vectors(repo_id, file_path);
CREATE INDEX IF NOT EXISTS idx_fv_fingerprint ON feature_vectors(fingerprint_id);

CREATE TABLE IF NOT EXISTS scan_results (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    fingerprint_id TEXT NOT NULL,
    scan_type TEXT NOT NULL,
    trigger TEXT NOT NULL,
    file_path TEXT NULL,
    dna_score REAL NULL,
    latency_ms REAL NULL,
    degraded INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scan_results_repo_time ON scan_results(repo_id, created_at DESC);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    progress REAL NULL,
    started_at INTEGER NULL,
    completed_at INTEGER NULL,
    error TEXT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_repo_status ON jobs(repo_id, status);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    entity_type TEXT NULL,
    entity_id TEXT NULL,
    detail TEXT NULL,
    created_at INTEGER NOT NULL
);

INSERT OR IGNORE INTO config (key, value, updated_at) VALUES
    ('logs.max_mb', '50', 0),
    ('logs.retain_days', '7', 0),
    ('scan_history.retain_days', '90', 0),
    ('jobs.retain_days', '30', 0),
    ('harvester.max_file_bytes', '1048576', 0),
    ('features.rust_scanner', 'true', 0),
    ('features.ide_inline_hints', 'true', 0),
    ('features.evolution_report', 'false', 0),
    ('features.multi_language', 'false', 0),
    ('features.export', 'false', 0);
