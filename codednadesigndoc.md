> **Note:** This is a fully synthesized, net-new document. It preserves every architectural decision visible in your original CodeDNA design doc, incorporates all the production-readiness gaps identified in the deep-dive, and layers on HAVEN-style governance/operability mechanics — adapted for a **local-first CLI/daemon/IDE-plugin** toolchain (not a cloud service). Drop this in as a direct replacement.

---

```markdown
# CodeDNA — Production-Ready Engineering Specification

---
## Document Governance

| Field            | Value                                              |
|------------------|----------------------------------------------------|
| status           | APPROVED — SINGLE SOURCE OF TRUTH                  |
| version          | 2.0.0                                              |
| last_updated     | 2025-06-12                                         |
| owners           | @knarayanareddy (lead), TBD (security review)      |
| review_cadence   | On every schema change, API contract change,       |
|                  | or major feature phase completion                  |
| canonical_sources| This doc > any inline code comment                 |
|                  | Schema DDL (§7) > any ORM/migration file comment   |
|                  | API contract table (§8) > any endpoint docstring   |

### Changelog

| Version | Date       | Author           | Summary                                            |
|---------|------------|------------------|----------------------------------------------------|
| 2.0.0   | 2025-06-12 | @knarayanareddy  | Full rewrite: added governance, canonical schema,  |
|         |            |                  | threat model, PRR appendix, migration policy,      |
|         |            |                  | SLOs, rollback/release strategy                    |
| 1.0.0   | (original) | @knarayanareddy  | Initial implementation blueprint                   |

### SSOT Rules

- **This document is the canonical spec.** Any implementation detail that
  conflicts with this document is a bug in the implementation, not in the doc.
- Schema DDL in §7 is canonical. Migration files must match it exactly.
  Discrepancies must be resolved by updating migrations, not this doc,
  unless a formal schema change (with versioned changelog entry) is approved.
- API contracts in §8 are canonical. OpenAPI export from FastAPI must be
  kept in sync and committed to `/docs/openapi.json` on every release.
- All ADRs in §13 are binding. Reverting an ADR requires a new ADR entry,
  not deletion.

### Items Required Before Any Public/Team Release

- [ ] Security review of localhost middleware & threat model mitigations (§9)
- [ ] SQLite schema migration strategy validated against all target platforms (§7.3)
- [ ] OpenAPI export generated, reviewed, and committed (`/docs/openapi.json`)
- [ ] PRR checklist (Appendix A) signed off by at least one reviewer
- [ ] Platform matrix smoke tests passing (§10.2)

---

## Table of Contents

1.  Purpose & Vision
2.  Glossary
3.  Goals, Non-Goals & Constraints
4.  User Personas & Use Cases
5.  System Architecture
    - 5.1 High-Level Container Diagram
    - 5.2 Component Breakdown
    - 5.3 Two-Speed Pipeline Model
    - 5.4 Data Flow (Build Baseline)
    - 5.5 Data Flow (Incremental Scan)
6.  Module Specifications
7.  Canonical Data Model
    - 7.1 Schema Principles
    - 7.2 Table DDL
    - 7.3 Migration Policy
    - 7.4 Schema Versioning Strategy
    - 7.5 Corruption Recovery
8.  API Contract
    - 8.1 General Principles
    - 8.2 Endpoint Inventory
    - 8.3 Error Contract
    - 8.4 SSE Event Contract
9.  Security & Privacy
    - 9.1 Security Posture (Local-First)
    - 9.2 Threat Model
    - 9.3 Mitigations Matrix
    - 9.4 Sensitive Data Handling
    - 9.5 Log Redaction Policy
10. Testing Strategy
    - 10.1 Test Pyramid
    - 10.2 Platform Matrix
    - 10.3 Key Test Cases
    - 10.4 CI Gates
11. Reliability & Operability
    - 11.1 Service Level Objectives (SLOs)
    - 11.2 Failure Modes & Degraded Operation
    - 11.3 Resource Limits & Disk Management
    - 11.4 Structured Logging
    - 11.5 Crash Recovery
12. Rollout, Release & Upgrade
    - 12.1 Phased Feature Delivery
    - 12.2 Release Artifact Strategy
    - 12.3 Upgrade & Rollback Story
    - 12.4 Feature Flags
13. Architecture Decision Records (ADRs)
14. Open Questions & Risks
Appendix A — Production Readiness Review (PRR) Checklist
Appendix B — Performance Budget Reference

---

## 1. Purpose & Vision

CodeDNA is a **local-first, privacy-preserving developer identity and code 
intelligence tool**. It builds a probabilistic "fingerprint" of a developer's 
coding patterns — style, idiom, structural habits, commit cadence — and 
surfaces insights about evolution, collaboration dynamics, and code health 
directly inside the developer's environment.

**Core promise:** every computation runs on the developer's machine. 
No code, no metrics, and no identifiers ever leave the local environment 
unless the developer explicitly triggers an export action.

**Production-readiness stance:** CodeDNA is a long-running local daemon + 
CLI + IDE plugin suite. "Production-ready" in this context means:
- Upgrades never silently corrupt or lose user data
- Internal errors never block developer workflow
- The attack surface is minimal and explicitly reasoned about
- Resource usage is bounded and predictable
- The system can be diagnosed and recovered by the developer themselves,
  without cloud support

---

## 2. Glossary

| Term              | Definition                                              |
|-------------------|---------------------------------------------------------|
| Fingerprint       | The full probabilistic model of a developer's coding    |
|                   | identity, stored as a serialized artifact in SQLite     |
| Feature Vector    | A fixed-dimension numeric representation of code style  |
|                   | extracted from a single function or file                |
| Baseline Build    | Full-repo fingerprint construction; slow path           |
| Incremental Scan  | Per-file or per-diff scan triggered by IDE/git; fast    |
| DNA Score         | Normalized similarity score [0.0–1.0] between two       |
|                   | feature vectors or fingerprints                         |
| Harvester         | Python module responsible for AST-based feature         |
|                   | extraction from source files                            |
| Fast Scanner      | Rust binary responsible for incremental file scans      |
|                   | meeting sub-100ms latency targets                       |
| Explainer         | Python module that translates numeric features into      |
|                   | human-readable pattern descriptions                     |
| Dashboard         | Localhost web UI served by the FastAPI daemon            |
| Daemon            | The background FastAPI process (localhost:7842)          |
| WAL               | SQLite Write-Ahead Logging mode (required for           |
|                   | concurrent reads during scans)                          |
| SSOT              | Single Source of Truth — this document                  |
| PRR               | Production Readiness Review (see Appendix A)            |
| ADR               | Architecture Decision Record (see §13)                  |

---

## 3. Goals, Non-Goals & Constraints

### 3.1 Goals

- **G1:** Build and maintain a probabilistic developer fingerprint from a 
  local git repository without network access
- **G2:** Provide incremental scan feedback fast enough to integrate into 
  IDE save and git pre-commit workflows
- **G3:** Surface actionable insights about code evolution, collaboration 
  patterns, and style drift via a local dashboard
- **G4:** Support multi-language analysis (Python primary; JS/TS, Rust, Go 
  as phase-2 targets) with a pluggable language adapter interface
- **G5:** Package as a single installable artifact with zero required runtime 
  dependencies beyond Python 3.10+ (pyinstaller standalone: zero)
- **G6:** Provide IDE integrations (VS Code, JetBrains) and git hook 
  integrations that are opt-in and removable without data loss
- **G7:** Never block developer workflow due to internal CodeDNA errors

### 3.2 Non-Goals

- **NG1:** Team/org-level sharing, telemetry, or any cloud sync — out of scope 
  permanently unless a future "CodeDNA Teams" spec is approved
- **NG2:** "Who wrote this code?" attribution for blame or HR purposes — 
  CodeDNA explicitly does not expose authorship APIs
- **NG3:** Real-time collaboration or multi-user access to the same SQLite DB
- **NG4:** Replacing existing linters, formatters, or static analysis tools 
  (CodeDNA is additive, not a substitute)
- **NG5:** Scanning code that is not in a local git repository (network 
  filesystem paths, remote SSH filesystems — undefined behavior)

### 3.3 Hard Constraints (Non-Negotiable)

| Constraint ID | Statement                                              | Rationale              |
|---------------|--------------------------------------------------------|------------------------|
| C1            | No code content leaves the machine                     | Privacy               |
| C2            | No function bodies stored by default                   | Privacy               |
| C3            | Export actions require explicit user confirmation      | Privacy               |
| C4            | Daemon listens on localhost (127.0.0.1) only; requests |                        |
|               | from non-loopback IPs are rejected with 403            | Security              |
| C5            | SQLite is the only required runtime dependency         | Portability           |
| C6            | IDE response latency ≤ 500ms (p95)                    | Workflow trust        |
| C7            | Pre-commit hook overhead ≤ 2s                         | Workflow trust        |
| C8            | Full baseline build ≤ 10 minutes for repos up to       |                        |
|               | 500k LOC                                               | Usability             |
| C9            | Scan errors must not propagate to the IDE as           |                        |
|               | blocking errors; degrade gracefully                    | Workflow trust        |
| C10           | Platform support: macOS 12+, Ubuntu 20.04+,            |                        |
|               | Windows 10/11 (WSL2 and native)                        | Reach                 |
| C11           | Stylometry: DNA scores must not be exposed via          |                        |
|               | any "who wrote this" API; per-function scores are       |                        |
|               | self-comparison only                                   | Ethics/Privacy        |

---

## 4. User Personas & Use Cases

### 4.1 Primary Persona: The Solo Developer

Wants to track their own coding evolution, understand their habits,
and catch style drift in long-running projects.

**Key flows:**
- Install CodeDNA, point at repo, build baseline
- Get ambient feedback in IDE as they code
- Review weekly dashboard insights

### 4.2 Secondary Persona: The Team Tech Lead

Uses CodeDNA individually to understand their own patterns before 
code review, not to evaluate others.

**Key flows:**
- Pre-commit hook: understand which patterns changed in this commit
- Evolution report: did this module drift from the project's idiom?

### 4.3 Tertiary Persona: The Open-Source Contributor

Uses CodeDNA on repos they contribute to infrequently; wants to 
understand how consistent their contributions are.

**Key flows:**
- Scan a specific branch/PR diff
- View similarity against their historical fingerprint

---

## 5. System Architecture

### 5.1 High-Level Container Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Developer Machine                                              │
│                                                                 │
│  ┌───────────────┐   ┌───────────────┐   ┌──────────────────┐  │
│  │  CLI          │   │  IDE Plugin   │   │  Git Hook        │  │
│  │  (codedna)    │   │  (VS Code /   │   │  (pre-commit)    │  │
│  │               │   │  JetBrains)   │   │                  │  │
│  └──────┬────────┘   └──────┬────────┘   └────────┬─────────┘  │
│         │                  │                      │            │
│         └──────────────────┼──────────────────────┘            │
│                            │ HTTP (localhost:7842)              │
│                 ┌──────────▼─────────┐                         │
│                 │  FastAPI Daemon     │                         │
│                 │  (localhost only)   │                         │
│                 │  + Dashboard UI     │                         │
│                 └──────────┬─────────┘                         │
│                            │                                   │
│          ┌─────────────────┼─────────────────┐                 │
│          │                 │                 │                 │
│   ┌──────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐         │
│   │  Python     │  │  Rust Fast   │  │  Explainer   │         │
│   │  Harvester  │  │  Scanner     │  │  Module      │         │
│   │  (slow path)│  │  (fast path) │  │  (NL output) │         │
│   └──────┬──────┘  └──────┬───────┘  └──────────────┘         │
│          │                │                                    │
│          └────────┬───────┘                                    │
│                   │                                            │
│          ┌────────▼───────┐                                    │
│          │  SQLite DB     │                                    │
│          │  (WAL mode)    │                                    │
│          │  ~/.codedna/   │                                    │
│          └────────────────┘                                    │
│                                                                 │
│  ══════════════════════════════════════════════════════════     │
│  NO NETWORK EGRESS  ║  ALL COMPUTE LOCAL  ║  NO TELEMETRY      │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Component Breakdown

| Component         | Language   | Responsibility                              |
|-------------------|------------|---------------------------------------------|
| CLI (`codedna`)   | Python     | User-facing commands: init, build, scan,    |
|                   |            | export, status, config                      |
| FastAPI Daemon    | Python     | Orchestration layer; serves REST API +      |
|                   |            | Dashboard; owns job queue; enforces          |
|                   |            | localhost-only middleware                   |
| Python Harvester  | Python     | AST traversal; feature extraction (slow     |
|                   |            | path); writes feature_vectors to DB         |
| Rust Fast Scanner | Rust       | Incremental file/diff scan; sub-100ms; IPC  |
|                   |            | via stdin/stdout JSON protocol with daemon  |
| Explainer Module  | Python     | Translates feature vectors to NL patterns;  |
|                   |            | template-based, no LLM dependency           |
| Dashboard UI      | HTML/JS    | Static bundle served by daemon; reads API;  |
|                   |            | visualizes fingerprint + evolution          |
| IDE Plugins       | TS (VSCode)| Calls daemon REST API; shows inline hints;  |
|                   | Kotlin (IJ)| opt-in, remove without data loss            |
| Git Hook          | Shell/Python| Pre-commit: invokes scan/diff endpoint;    |
|                   |            | exits 0 on any CodeDNA error (C9)           |

### 5.3 Two-Speed Pipeline Model

```
SLOW PATH (Baseline Build):
Repo files → Harvester (AST + feature extraction) → 
  Vector DB (batch insert, WAL) → Fingerprint Model → 
    fingerprints table → Explainer → Cached explanations

FAST PATH (Incremental Scan):
File save / diff → Rust Fast Scanner (IPC) → 
  Daemon (merge partial vectors) → DNA Score → 
    SSE event → IDE plugin (render hint)
```

Key invariant: **fast path never writes to fingerprints table**. It 
computes a transient score against the existing fingerprint. Fingerprint 
is only mutated by a completed baseline or scheduled delta build.

### 5.4 Data Flow: Build Baseline

```
1. CLI: codedna build --repo <path>
2. Daemon: enqueue job (type=FULL_BUILD, repo_id)
3. Harvester: walk repo files → filter by language adapters
4. Per file: AST parse → extract feature vector (N dims)
5. Batch insert into feature_vectors (chunk=500 rows)
6. On completion: compute aggregate fingerprint model
7. Write serialized model to fingerprints table
8. Mark job COMPLETE; emit SSE job.complete event
9. CLI/IDE: poll jobs/{id} or listen on SSE stream
```

### 5.5 Data Flow: Incremental Scan

```
1. IDE plugin: file save OR git hook: pre-commit diff
2. HTTP POST /scan/file or /scan/diff to daemon
3. Daemon: validate, hand off to Rust Fast Scanner via IPC
4. Fast Scanner: extract partial feature vector (sub-100ms)
5. Daemon: compute DNA score vs. current fingerprint
6. Return score + explanation JSON (≤ 500ms p95 total)
7. IDE plugin renders hint; git hook logs result, exits 0
```

---

## 6. Module Specifications

### 6.1 Harvester Module

**Inputs:** file path, language hint, config (store_bodies: bool)  
**Outputs:** FeatureVector (see §7.2)  
**Constraints:**
- Must not store function body text unless `store_bodies=true` (default: false)
- Must handle parse errors per-file without aborting the build job
- Must support language adapter interface (see §6.5)

**Feature dimensions (Python, v1):**

| Category          | Features                                            |
|-------------------|-----------------------------------------------------|
| Naming            | snake_case ratio, single-char var rate, abbrev rate |
| Structure         | avg function length, nesting depth, class ratio     |
| Idiom             | comprehension rate, lambda rate, decorator rate     |
| Error handling    | try/except ratio, bare except rate, assert rate     |
| Documentation     | docstring rate, inline comment density              |
| Imports           | stdlib ratio, relative import rate, star import rate|
| Commit patterns   | lines per commit (from git log), commit hour dist.  |

Total: 32-dimensional vector (v1). Dimension count is part of the
canonical schema (§7.2) and must be updated via migration if changed.

### 6.2 Rust Fast Scanner

**Protocol:** JSON over stdin/stdout (line-delimited)  
**Request:**
```json
{
  "type": "scan_file" | "scan_diff",
  "language": "python" | "javascript" | "typescript" | "rust" | "go",
  "content": "<file or diff content>",
  "fingerprint_id": "<uuid>"
}
```
**Response:**
```json
{
  "score": 0.0-1.0,
  "partial_vector": [float, ...],
  "latency_ms": 42,
  "error": null | "<message>"
}
```
**Invariants:**
- Returns `error` field (non-null) instead of crashing on parse failure
- Daemon treats any non-zero exit from the scanner binary as a degraded 
  state; logs error, returns `{"score": null, "degraded": true}` to caller
- Binary is bundled with the Python package (pre-compiled per platform)

### 6.3 Explainer Module

**Inputs:** FeatureVector, comparison FeatureVector (optional), verbosity  
**Outputs:** ExplanationResult: `{summary: str, patterns: [Pattern], 
  changes: [Change]}`  
**Constraints:**
- Template-based only; no LLM, no network, no external model
- Must produce output in < 50ms
- Explanations must not infer authorship identity (constraint C11)

### 6.4 Daemon (FastAPI)

**Startup:**
- Binds to `127.0.0.1:7842` only (never 0.0.0.0)
- Registers `LocalhostOnlyMiddleware` (rejects non-127.0.0.1 with 403)
- Runs DB migrations on start (idempotent; see §7.3)
- Validates DB `user_version` matches expected schema version; 
  halts with clear error if mismatch and migration is not safe to auto-run
- Spawns job worker thread pool (size: configurable, default: 2)

**Shutdown:** graceful drain of active jobs (SIGTERM → 30s drain → SIGKILL)

### 6.5 Language Adapter Interface

All language support is provided via adapters conforming to:
```python
class LanguageAdapter(Protocol):
    language: str               # "python", "javascript", etc.
    extensions: list[str]       # [".py"], [".js", ".mjs"]
    
    def extract_features(
        self, 
        source: str, 
        config: HarvesterConfig
    ) -> FeatureVector | AdapterError: ...
    
    def supports_incremental(self) -> bool: ...
```

Phase 1 (Python) uses the built-in adapter.  
Phase 2+ adds adapters via the plugin registry — no core changes required.

---

## 7. Canonical Data Model

**CANONICAL RULE:** The DDL below is the source of truth.
Migration files must produce schema identical to this. If any migration
file conflicts with this section, the migration is wrong, not this section.

### 7.1 Schema Principles

- All primary keys are UUIDs (TEXT, stored as lowercase hex with hyphens)
- All timestamps are `INTEGER` (Unix epoch seconds, UTC) unless noted
- Soft-delete pattern: `deleted_at INTEGER NULL` — no hard deletes except 
  for explicit user-triggered erasure
- Schema version tracked via SQLite `PRAGMA user_version`
- WAL mode enabled on every new database (pragma set in migration 0001)
- No foreign key enforcement in SQLite (app-layer enforced); FK columns 
  are commented for documentation purposes
- `updated_at` columns are updated by application layer, not triggers 
  (SQLite trigger support is partial across platforms)

### 7.2 Table DDL

```sql
-- ============================================================
-- Migration 0001: Initial schema (user_version = 1)
-- ============================================================
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = OFF; -- app-layer enforced
PRAGMA user_version = 1;

-- repos: one row per tracked local repository
CREATE TABLE IF NOT EXISTS repos (
    id          TEXT PRIMARY KEY,             -- UUID
    path        TEXT NOT NULL UNIQUE,         -- absolute local path
    name        TEXT NOT NULL,                -- derived from basename
    language    TEXT NOT NULL DEFAULT 'python',
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL,
    deleted_at  INTEGER NULL,
    metadata    TEXT NULL                     -- JSON blob for future use
);

-- fingerprints: one active fingerprint per repo at any time
CREATE TABLE IF NOT EXISTS fingerprints (
    id               TEXT PRIMARY KEY,        -- UUID
    repo_id          TEXT NOT NULL,           -- FK → repos.id
    version          INTEGER NOT NULL DEFAULT 1,
    vector_dims      INTEGER NOT NULL DEFAULT 32,
    model_blob       BLOB NOT NULL,           -- serialized numpy/msgpack
    commit_hash      TEXT NOT NULL,           -- git HEAD at build time
    commit_count     INTEGER NOT NULL DEFAULT 0,
    file_count       INTEGER NOT NULL DEFAULT 0,
    build_duration_s REAL NULL,
    created_at       INTEGER NOT NULL,
    updated_at       INTEGER NOT NULL,
    deleted_at       INTEGER NULL,
    is_active        INTEGER NOT NULL DEFAULT 1  -- 1=active, 0=archived
);
CREATE INDEX IF NOT EXISTS idx_fingerprints_repo 
    ON fingerprints(repo_id, is_active);

-- feature_vectors: one row per scanned function/file unit
CREATE TABLE IF NOT EXISTS feature_vectors (
    id              TEXT PRIMARY KEY,          -- UUID
    repo_id         TEXT NOT NULL,             -- FK → repos.id
    fingerprint_id  TEXT NOT NULL,             -- FK → fingerprints.id
    file_path       TEXT NOT NULL,             -- relative to repo root
    unit_type       TEXT NOT NULL,             -- 'function' | 'file'
    unit_name       TEXT NULL,                 -- function name if applicable
    language        TEXT NOT NULL,
    vector          BLOB NOT NULL,             -- float32 array, msgpack
    vector_dims     INTEGER NOT NULL DEFAULT 32,
    body_hash       TEXT NULL,                 -- SHA256 of body (no body stored)
    line_start      INTEGER NULL,
    line_end        INTEGER NULL,
    commit_hash     TEXT NULL,
    created_at      INTEGER NOT NULL,
    deleted_at      INTEGER NULL
);
CREATE INDEX IF NOT EXISTS idx_fv_repo_file 
    ON feature_vectors(repo_id, file_path);
CREATE INDEX IF NOT EXISTS idx_fv_fingerprint 
    ON feature_vectors(fingerprint_id);

-- scan_results: log of incremental scans (transient; pruned per §11.3)
CREATE TABLE IF NOT EXISTS scan_results (
    id              TEXT PRIMARY KEY,          -- UUID
    repo_id         TEXT NOT NULL,             -- FK → repos.id
    fingerprint_id  TEXT NOT NULL,             -- FK → fingerprints.id (snapshot)
    scan_type       TEXT NOT NULL,             -- 'file' | 'diff' | 'function'
    trigger         TEXT NOT NULL,             -- 'ide_save' | 'pre_commit' | 'cli'
    file_path       TEXT NULL,
    dna_score       REAL NULL,                 -- NULL if scan degraded
    latency_ms      REAL NULL,
    degraded        INTEGER NOT NULL DEFAULT 0, -- 1 if fast scanner errored
    error_message   TEXT NULL,
    created_at      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scan_results_repo_time 
    ON scan_results(repo_id, created_at DESC);

-- jobs: build/scan job queue and history
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,              -- UUID
    repo_id     TEXT NOT NULL,                 -- FK → repos.id
    type        TEXT NOT NULL,                 -- 'FULL_BUILD' | 'DELTA_BUILD'
    status      TEXT NOT NULL DEFAULT 'QUEUED',
                                               -- QUEUED|RUNNING|COMPLETE|FAILED
    progress    REAL NULL,                     -- 0.0–1.0
    started_at  INTEGER NULL,
    completed_at INTEGER NULL,
    error       TEXT NULL,
    created_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_repo_status 
    ON jobs(repo_id, status);

-- config: key-value store for user preferences
CREATE TABLE IF NOT EXISTS config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,                 -- JSON-encoded
    updated_at  INTEGER NOT NULL
);

-- audit_log: append-only local audit trail (no deletes permitted)
CREATE TABLE IF NOT EXISTS audit_log (
    id          TEXT PRIMARY KEY,              -- UUID
    event_type  TEXT NOT NULL,
    entity_type TEXT NULL,
    entity_id   TEXT NULL,
    detail      TEXT NULL,                     -- JSON blob
    created_at  INTEGER NOT NULL
);
```

### 7.3 Migration Policy

**Rules (binding):**

1. Every schema change requires a new numbered migration file: 
   `migrations/NNNN_description.sql`
2. Migration files are **append-only**: never edit a migration that 
   has been committed to main
3. Migrations must be idempotent: use `CREATE TABLE IF NOT EXISTS`,
   `CREATE INDEX IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN` patterns
4. `PRAGMA user_version` must be incremented in each migration
5. The daemon runs migrations on every start, in order, checking 
   `user_version` before each step
6. **Destructive migrations** (column drops, table drops, type changes) 
   require:
   - A new ADR entry (§13)
   - A data-migration companion step to preserve user data
   - A `--backup-before-migrate` flag honored in the CLI
7. If the detected `user_version` is **higher** than what the current 
   binary supports (user has downgraded), the daemon refuses to start 
   and prints a clear recovery message (see §11.5)

### 7.4 Schema Versioning Strategy

```
PRAGMA user_version         → integer, incremented per migration
Fingerprint.version         → integer, incremented when feature 
                               dimensions change
FeatureVector.vector_dims   → integer, must match Fingerprint.vector_dims
```

**Dimension change rule:** If `vector_dims` changes (new feature added),
existing fingerprints are marked `is_active=0` and a rebuild is required.
The daemon surfaces this via `GET /status` (`rebuild_required: true`).

### 7.5 Corruption Recovery

If SQLite integrity check fails on startup (`PRAGMA integrity_check`):
1. Daemon logs `FATAL: db_integrity_check_failed`
2. CLI prints recovery message:
   ```
   CodeDNA database may be corrupted.
   Run: codedna db repair --repo <path>
   This will attempt to recover scan history.
   Fingerprint will require a rebuild.
   Your source code is NOT affected.
   ```
3. `codedna db repair` attempts `VACUUM INTO` to a new file, 
   then renames. On failure, moves corrupt DB to `.codedna/backup/` 
   and starts fresh.

---

## 8. API Contract

### 8.1 General Principles

- Base URL: `http://127.0.0.1:7842/api/v1`
- All requests/responses: `application/json` unless noted
- All endpoints require `X-CodeDNA-Client` header (any non-empty value); 
  missing header → 400. (Prevents trivial CSRF from browser-opened tabs)
- Authentication: none required (localhost-only; protected by OS process 
  isolation)
- Versioning: URL-versioned (`/v1/`). Breaking changes require `/v2/` 
  and a deprecation notice in `GET /status`

### 8.2 Endpoint Inventory

| Method | Path                          | Description                          |
|--------|-------------------------------|--------------------------------------|
| GET    | /status                       | Daemon health, DB version, active     |
|        |                               | repo, rebuild_required flag          |
| GET    | /repos                        | List all tracked repos               |
| POST   | /repos                        | Add repo to tracking                 |
| DELETE | /repos/{repo_id}              | Untrack repo (soft delete)           |
| POST   | /repos/{repo_id}/build        | Enqueue FULL_BUILD job               |
| GET    | /jobs/{job_id}                | Get job status + progress            |
| GET    | /fingerprint/{repo_id}        | Get active fingerprint summary       |
| POST   | /scan/file                    | Incremental file scan (fast path)    |
| POST   | /scan/diff                    | Incremental diff scan (fast path)    |
| POST   | /scan/function                | Single function scan                 |
| GET    | /evolution/{repo_id}          | Evolution report (time series)       |
| GET    | /events                       | SSE stream (see §8.4)                |
| POST   | /export                       | Trigger confirmed data export        |
| GET    | /config                       | Get all config values                |
| PUT    | /config/{key}                 | Update config value                  |
| DELETE | /repos/{repo_id}/data         | Full data erasure for repo           |

**POST /scan/file — Request:**
```json
{
  "repo_id": "uuid",
  "file_path": "relative/path/to/file.py",
  "language": "python",
  "content_hash": "sha256hex"
}
```

**POST /scan/file — Response (200):**
```json
{
  "scan_id": "uuid",
  "dna_score": 0.87,
  "explanation": {
    "summary": "Consistent with your established patterns",
    "patterns": ["high comprehension rate", "minimal nesting"],
    "changes": []
  },
  "latency_ms": 94,
  "degraded": false
}
```

**POST /export — Request:**
```json
{
  "repo_id": "uuid",
  "format": "json" | "csv",
  "include": ["fingerprint", "evolution", "scan_history"],
  "confirmed": true   // must be true; false → 400
}
```

### 8.3 Error Contract

All errors return:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "human-readable description",
    "detail": {}     // optional structured context
  }
}
```

| HTTP Status | Error Code                    | Meaning                          |
|-------------|-------------------------------|----------------------------------|
| 400         | MISSING_CLIENT_HEADER         | X-CodeDNA-Client not provided    |
| 400         | EXPORT_NOT_CONFIRMED          | Export requires confirmed: true  |
| 400         | INVALID_LANGUAGE              | Language not supported           |
| 403         | NON_LOCALHOST_REJECTED        | Request from non-loopback IP     |
| 404         | REPO_NOT_FOUND                | repo_id not in DB                |
| 404         | FINGERPRINT_NOT_BUILT         | No active fingerprint for repo   |
| 409         | BUILD_ALREADY_RUNNING         | Job already QUEUED/RUNNING       |
| 503         | SCANNER_DEGRADED              | Rust scanner error; score=null   |
| 503         | DB_UNAVAILABLE                | SQLite locked beyond timeout     |

**Invariant:** IDE-facing endpoints (`/scan/*`) MUST return 200 with 
`"degraded": true` rather than 4xx/5xx. Non-blocking behavior (C9) 
is enforced at the API layer, not just the application layer.

### 8.4 SSE Event Contract

`GET /api/v1/events` — text/event-stream

| Event Type            | Payload                                      |
|-----------------------|----------------------------------------------|
| `job.progress`        | `{job_id, repo_id, progress: 0.0-1.0}`       |
| `job.complete`        | `{job_id, repo_id, fingerprint_id}`          |
| `job.failed`          | `{job_id, repo_id, error}`                   |
| `fingerprint.updated` | `{repo_id, fingerprint_id, rebuild_reason}`  |
| `daemon.status`       | `{db_version, rebuild_required}`             |

SSE stream sends a `: keepalive` comment every 15 seconds.
Clients must handle reconnect with exponential backoff (start 1s, max 30s).

---

## 9. Security & Privacy

### 9.1 Security Posture (Local-First)

CodeDNA's security model is predicated on:
- **OS process isolation**: the daemon and DB are only accessible to 
  the user who launched the daemon
- **Localhost-only binding**: only processes on the same machine can 
  reach the API (constraint C4)
- **No secrets**: CodeDNA handles no credentials, tokens, or PII beyond 
  file paths and code structure metadata
- **No telemetry**: no outbound connections whatsoever

### 9.2 Threat Model

| Asset                    | Why it matters                                  |
|--------------------------|-------------------------------------------------|
| Local source code paths  | Could expose project structure to other users   |
| Feature vectors          | Could allow stylometric fingerprinting if leaked|
| Scan history             | Shows what files were edited and when           |
| SQLite database file     | Contains all of the above                       |

| Threat Actor            | Attack Surface            | Likelihood | Impact  |
|-------------------------|---------------------------|------------|---------|
| Malicious local process | HTTP to daemon port       | Medium     | High    |
| Compromised IDE plugin  | REST API via localhost     | Low        | Medium  |
| Supply chain (pip/npm)  | Harvester/plugin deps      | Low        | High    |
| Curious user (same OS)  | SQLite file permissions    | Low        | Medium  |
| Sensitive code in logs  | Log file exfiltration      | Medium     | High    |
| Downgraded binary       | DB schema mismatch         | Low        | Medium  |

### 9.3 Mitigations Matrix

| Threat                  | Mitigation                                         |
|-------------------------|----------------------------------------------------|
| Malicious local process | `LocalhostOnlyMiddleware` + `X-CodeDNA-Client`     |
|                         | header check; rate limiting (100 req/min default)  |
| Compromised IDE plugin  | Export endpoint requires `confirmed: true`;         |
|                         | no write endpoints exposed beyond scan/config      |
| Supply chain            | Pinned deps in `requirements.txt` + hash manifest; |
|                         | Rust binary built from source in CI                |
| DB file permissions     | DB created with `chmod 600`; documented in install |
| Sensitive code in logs  | Log redaction policy (§9.5); no content logged     |
| Downgraded binary       | `user_version` check on startup halts daemon       |

### 9.4 Sensitive Data Handling

| Data Type              | Stored?     | Logged?  | Exported?          |
|------------------------|-------------|----------|--------------------|
| Source code content    | NEVER       | NEVER    | Never              |
| Function body text     | Opt-in only | NEVER    | Only if opted in   |
| File paths             | Yes         | Redacted | On explicit export |
| Feature vectors        | Yes         | NEVER    | On explicit export |
| Commit hashes          | Yes         | OK       | On explicit export |
| Author emails (git)    | NEVER       | NEVER    | Never              |
| DNA scores             | Yes         | NEVER    | On explicit export |

**Author email rule:** The harvester must explicitly filter out author 
identity fields when reading git log. This is enforced in the harvester 
module and verified by a unit test (see §10.3).

### 9.5 Log Redaction Policy

Structured logs (JSON, written to `~/.codedna/logs/daemon.log`):

- File paths: redacted to `[REDACTED_PATH]` in logs at `INFO` level and 
  below; shown as-is only at `DEBUG` level (never in production log level)
- Function names: shown only at `DEBUG` level
- Code content: **never logged at any level**
- Error stack traces: logged but file paths redacted
- Scores: logged as numeric values (no privacy risk)
- Log rotation: 7 days, max 50MB total (configurable)
- Log files: `chmod 600` on creation

---

## 10. Testing Strategy

### 10.1 Test Pyramid

```
                    ┌─────────────────┐
                    │  E2E Tests      │  ← 5%
                    │  (platform CI)  │
                  ┌─┴─────────────────┴─┐
                  │  Integration Tests  │  ← 25%
                  │  (daemon + DB)      │
               ┌──┴─────────────────────┴──┐
               │      Unit Tests           │  ← 70%
               │  (per module, fast <5s)   │
               └───────────────────────────┘
```

**Unit (70%):** pytest, per module, no I/O, mock DB/filesystem.  
Target: < 5s total. Run on every commit.

**Integration (25%):** Full daemon startup with SQLite in-memory or 
tmp-dir. Tests: scan → score pipeline, job queue, migration idempotency, 
SSE delivery, localhost middleware rejection, export confirmation gate.  
Target: < 60s. Run on every PR.

**E2E (5%):** Against real git repo fixture. Tests: full build baseline, 
incremental scan latency (must meet SLOs), IDE plugin contract, git hook 
exit behavior. Run on release branches and platform matrix CI.

### 10.2 Platform Matrix (CI)

| Platform            | Unit | Integration | E2E | Artifact |
|---------------------|------|-------------|-----|----------|
| macOS 14 (arm64)    | ✓    | ✓           | ✓   | .dmg/pip |
| macOS 12 (x86_64)   | ✓    | ✓           | -   | pip      |
| Ubuntu 22.04        | ✓    | ✓           | ✓   | .deb/pip |
| Ubuntu 20.04        | ✓    | ✓           | -   | pip      |
| Windows 11 (native) | ✓    | ✓           | ✓   | .exe/pip |
| Windows 10 (WSL2)   | ✓    | -           | -   | pip      |

### 10.3 Key Test Cases

| Test                                   | Type        | Validates       |
|----------------------------------------|-------------|-----------------|
| Harvester extracts 32-dim vector       | Unit        | Feature contract|
| Harvester rejects function body storage| Unit        | Privacy (C2)    |
| Harvester strips author email fields   | Unit        | Privacy (§9.4)  |
| Scan error returns 200 + degraded:true | Integration | C9              |
| Non-localhost request returns 403      | Integration | C4              |
| Export with confirmed:false returns 400| Integration | C3              |
| Migration 0001 idempotency             | Integration | §7.3            |
| user_version mismatch halts daemon     | Integration | §7.3 rule 7     |
| Incremental scan p95 ≤ 500ms          | E2E         | C6, SLO-1       |
| Pre-commit overhead ≤ 2s              | E2E         | C7, SLO-2       |
| Full build ≤ 10min (500k LOC fixture) | E2E         | C8, SLO-3       |
| git hook exits 0 on scanner error     | E2E         | C9              |
| DB chmod 600 after creation            | Integration | §9.3            |
| Log file contains no code content     | Integration | §9.5            |

### 10.4 CI Gates (PRs cannot merge if any gate fails)

```
[ ] Unit tests pass (all platforms)
[ ] Integration tests pass (all platforms)
[ ] No new dependencies without pinned hashes
[ ] OpenAPI export matches committed /docs/openapi.json
[ ] PRAGMA user_version incremented if any DDL changed
[ ] Migration idempotency test passes
[ ] Log redaction test passes
[ ] Lint: ruff (Python), clippy (Rust), eslint (TS plugins)
[ ] Type check: mypy strict (Python daemon/harvester)
```

---

## 11. Reliability & Operability

### 11.1 Service Level Objectives (SLOs)

| SLO ID | Objective                              | Target   | Measurement          |
|--------|----------------------------------------|----------|----------------------|
| SLO-1  | IDE scan response latency (p95)        | ≤ 500ms  | scan_results.latency_ms |
| SLO-2  | Pre-commit hook total overhead (p95)   | ≤ 2s     | CLI timing           |
| SLO-3  | Full baseline build (500k LOC repo)    | ≤ 10min  | jobs.build_duration_s|
| SLO-4  | Daemon startup time (cold)             | ≤ 3s     | daemon startup log   |
| SLO-5  | Scan degraded rate (scanner errors)    | ≤ 1%     | scan_results.degraded|
| SLO-6  | Migration success rate (on upgrade)    | 100%     | DB integrity post-run|

SLO data is queryable from local DB. `codedna status --slo` prints a 
local SLO summary for the last 7 days.

### 11.2 Failure Modes & Degraded Operation

| Failure Mode              | Detection                    | Behavior                    |
|---------------------------|------------------------------|-----------------------------|
| Rust scanner crash/timeout| Non-zero exit or timeout >2s | Return degraded:true in API;|
|                           |                              | log error; IDE shows nothing|
| SQLite WAL lock timeout   | SQLITE_BUSY after 5s retry   | 503 DB_UNAVAILABLE; queue   |
|                           |                              | retry; no data loss          |
| Harvester OOM on large file| MemoryError caught          | Skip file; log warning;      |
|                           |                              | mark file as skipped in job  |
| Daemon not running (IDE)  | Connection refused           | IDE plugin shows "CodeDNA   |
|                           |                              | offline" badge; no errors    |
| Feature dimension mismatch| user_version check           | Halt; prompt rebuild         |
| Disk full                 | Write failure                | Log FATAL; stop job; do not |
|                           |                              | corrupt existing data        |

**Invariant:** No failure mode in CodeDNA should ever corrupt source code 
or git state. CodeDNA is strictly read-only with respect to the repo.

### 11.3 Resource Limits & Disk Management

| Resource        | Default Limit   | Configurable | Key                           |
|-----------------|-----------------|--------------|-------------------------------|
| Log files       | 50MB total, 7d  | Yes          | `logs.max_mb`, `logs.retain_days` |
| scan_results    | 90 days         | Yes          | `scan_history.retain_days`    |
| feature_vectors | Unlimited (per  |              |                               |
|                 | active FP only) | —            | Pruned on fingerprint archive |
| Job history     | 30 days         | Yes          | `jobs.retain_days`            |
| Max file size   | 1MB per file    | Yes          | `harvester.max_file_bytes`    |
|                 | (skips larger)  |              |                               |
| Daemon RAM      | ~200MB typical  | —            | Monitor via `codedna status`  |

**Pruning:** `codedna db prune` (also run by daemon weekly):
- Deletes scan_results older than `scan_history.retain_days`
- Deletes archived (is_active=0) feature_vectors
- Deletes jobs older than `jobs.retain_days`
- Runs `PRAGMA wal_checkpoint(TRUNCATE)` to reclaim WAL space
- Never deletes active fingerprints or repos without explicit user action

### 11.4 Structured Logging

All log entries are JSON lines to `~/.codedna/logs/daemon.log`:

```json
{
  "ts": 1718150400,
  "level": "INFO",
  "component": "daemon|harvester|scanner|explainer|migration",
  "event": "event_name",
  "repo_id": "uuid or null",
  "job_id": "uuid or null",
  "latency_ms": 94,
  "error": null,
  "detail": {}
}
```

Log levels: `DEBUG` (dev only), `INFO` (default), `WARN`, `ERROR`, `FATAL`  
Default level: `INFO`. Never set `DEBUG` in packaged releases.

### 11.5 Crash Recovery

**Daemon restart (clean):** All job state is persisted in SQLite. 
RUNNING jobs are marked FAILED on next startup with `error: "daemon_restart"`. 
User is notified via `GET /status` (`interrupted_jobs: [...]`).

**Binary downgrade detected:**
```
ERROR: Database schema version (4) is newer than this CodeDNA 
binary supports (3). Refusing to start to protect your data.

Options:
  1. Upgrade CodeDNA: pip install --upgrade codedna
  2. Restore previous version from your package manager
  3. Reset (WARNING: loses fingerprint data):
     codedna db reset --repo <path>
```

**DB corruption recovery:** See §7.5.

---

## 12. Rollout, Release & Upgrade

### 12.1 Phased Feature Delivery

| Phase | Duration  | Deliverables                                     | Gate to next phase      |
|-------|-----------|--------------------------------------------------|-------------------------|
| 1     | 4 weeks   | Daemon, SQLite schema, Python harvester (Python  | SLO-1/2/3 passing in    |
|       |           | only), CLI init/build/status, basic dashboard    | E2E tests               |
| 2     | 4 weeks   | Rust fast scanner, IDE plugins (VS Code),        | SLO-1 p95 ≤ 500ms in    |
|       |           | git hook integration, SSE stream                 | platform matrix CI      |
| 3     | 4 weeks   | Evolution reports, clustering, multi-language    | Language adapter tests  |
|       |           | adapters (JS/TS via language adapter interface)  | passing for all targets |
| 4     | 3 weeks   | JetBrains plugin, export (JSON/CSV), DB prune    | PRR checklist signed    |
|       |           | scheduler, full PRR checklist (Appendix A)       | off (Appendix A)        |
| 5     | 2 weeks   | Polish, perf tuning, installer packaging,        | All CI gates green on   |
|       |           | platform matrix validation, 1.0 release          | all platform targets    |

### 12.2 Release Artifact Strategy

| Artifact          | Target                  | Build Tool    | Signed? |
|-------------------|-------------------------|---------------|---------|
| pip package       | All platforms (dev use) | setuptools    | Yes (PyPI) |
| pyinstaller bundle| macOS, Linux, Windows   | pyinstaller   | Yes (code-sign) |
| .deb package      | Ubuntu/Debian           | fpm           | Yes (GPG) |
| Homebrew formula  | macOS                   | Homebrew tap  | Via tap |
| VS Code extension | All                     | vsce          | Yes (marketplace) |

Rust scanner binary is compiled per-platform in CI and bundled into 
the pip package under `codedna/bin/<platform>/codedna-scanner`.

### 12.3 Upgrade & Rollback Story

**Upgrade flow (pip):**
```
1. pip install --upgrade codedna
2. codedna daemon restart   (or daemon auto-detects new version on next start)
3. Daemon runs idempotent migrations in order
4. If all migrations succeed: normal startup
5. If any migration fails: rollback attempted via VACUUM INTO backup; 
   user notified with recovery instructions
```

**Rollback story:**
- SQLite DB is backed up automatically before any migration 
  (`~/.codedna/backup/db_pre_upgrade_<version>.sqlite`)
- Backup retained for 30 days
- If user needs to downgrade: `codedna db restore --version <N>` 
  restores from backup (loses data since that backup)
- Fingerprints survive all non-dimension-changing upgrades

**Policy:** Any upgrade that changes `vector_dims` (feature dimension) 
will archive existing fingerprints and require a rebuild. This is communicated 
in the release notes and via `codedna status` post-upgrade.

### 12.4 Feature Flags

Feature flags are stored in the `config` table with prefix `feature.`:

| Flag Key                     | Default | Effect                          |
|------------------------------|---------|----------------------------------| 
| `feature.rust_scanner`       | true    | Enables fast path; false = Python fallback |
| `feature.ide_inline_hints`   | true    | IDE plugin shows score hints     |
| `feature.evolution_report`   | false   | Phase 3 gating                  |
| `feature.multi_language`     | false   | Phase 3 gating                  |
| `feature.export`             | false   | Phase 4 gating                  |

Set via: `codedna config set feature.evolution_report true`  
Read via: `GET /api/v1/config/feature.evolution_report`

---

## 13. Architecture Decision Records (ADRs)

**ADR-001: SQLite as the only persistence layer**  
- **Decision:** Use SQLite with WAL mode. No PostgreSQL, Redis, or other deps.  
- **Context:** Constraint C5 (zero runtime deps). Local-first.  
- **Tradeoffs:** No concurrent multi-process writes; no query plan optimizer 
  at scale. Acceptable: single-user, local tool.  
- **Consequences:** Schema migration is entirely app-managed (see §7.3).  
- **Status:** Accepted. Not re-openable without a new ADR.

**ADR-002: Rust fast scanner as a subprocess (IPC), not a Python extension**  
- **Decision:** Rust binary communicates over stdin/stdout JSON, not via 
  PyO3 or ctypes.  
- **Context:** Subprocess model is simpler to ship cross-platform; no ABI 
  compatibility risk; scanner crashes do not crash the daemon.  
- **Tradeoffs:** ~1–3ms IPC overhead vs in-process call.  
- **Consequences:** Daemon must handle scanner process lifecycle (spawn, 
  health, restart).  
- **Status:** Accepted.

**ADR-003: No LLM / network dependency for explanations**  
- **Decision:** Explainer uses template-based NL generation.  
- **Context:** Constraint C1 (no data leaves machine). Reliability: 
  explanations must work offline, always.  
- **Tradeoffs:** Less natural prose.  
- **Status:** Accepted. Future "LLM mode" would require an explicit 
  opt-in ADR with data-egress consent UX.

**ADR-004: Scan endpoints return 200 + degraded:true, never 5xx**  
- **Decision:** IDE/hook-facing scan endpoints never return error HTTP codes.  
- **Context:** Constraint C9. A 503 from CodeDNA must not break a git commit 
  or IDE save.  
- **Tradeoffs:** Clients must inspect `degraded` field, not just HTTP status.  
- **Status:** Accepted. Documented in §8.3.

**ADR-005: Author identity fields explicitly excluded from harvest**  
- **Decision:** Harvester never reads or stores git author name/email.  
- **Context:** Constraint C11 (no "who wrote this" surface). Stylometry risk.  
- **Consequences:** DNA scores are self-comparison only. Team-mode (if ever 
  built) requires a new ADR with explicit consent model.  
- **Status:** Accepted. Enforced by unit test.

**ADR-006: UUIDs as primary keys (not integer ROWID)**  
- **Decision:** All PKs are TEXT UUIDs.  
- **Context:** Future-proofing for export format stability and potential 
  multi-DB merge scenarios.  
- **Tradeoffs:** Slightly larger storage vs integer ROWID.  
- **Status:** Accepted.

---

## 14. Open Questions & Risks

| ID  | Question / Risk                              | Owner  | Priority | Target     |
|-----|----------------------------------------------|--------|----------|------------|
| OQ1 | Should delta builds (incremental fingerprint | Lead   | High     | Phase 2    |
|     | update without full rebuild) be supported?   |        |          |            |
|     | What's the correctness model for partial     |        |          |            |
|     | vector merging?                              |        |          |            |
| OQ2 | Go language adapter: AST tooling choice      | Lead   | Medium   | Phase 3    |
|     | (go/ast vs tree-sitter)?                     |        |          |            |
| OQ3 | VS Code extension marketplace distribution:  | Lead   | Medium   | Phase 4    |
|     | private or public? Review timeline?          |        |          |            |
| OQ4 | pyinstaller binary size on Windows (~60MB    | Lead   | Low      | Phase 5    |
|     | typical): acceptable or need slimming?       |        |          |            |
| OQ5 | Risk: SQLite WAL contention if user runs     | Lead   | Medium   | Phase 1    |
|     | two daemons against the same DB path.        |        |          |            |
|     | Mitigation: PID lock file on daemon start?   |        |          |            |
| OQ6 | Risk: Large monorepos (>1M LOC) may exceed   | Lead   | High     | Phase 1    |
|     | the 10min build SLO. Need profiling on       |        |          |            |
|     | real-world fixture before Phase 2 gate.      |        |          |            |
| OQ7 | Feature dimension expansion (v2 vectors):    | Lead   | Low      | Future     |
|     | design migration strategy for existing       |        |          |            |
|     | fingerprints before implementing.            |        |          |            |

---

## Appendix A — Production Readiness Review (PRR) Checklist

This checklist must be completed before the Phase 4 → Phase 5 gate (1.0 release).

### Architecture & Contracts
- [ ] All endpoints in §8.2 implemented and match OpenAPI export
- [ ] `/docs/openapi.json` committed and matches running daemon output
- [ ] All ADRs in §13 reviewed and confirmed still accurate
- [ ] No open questions with Priority=High remain unresolved

### Data & Migrations
- [ ] All DDL in §7.2 implemented and matches `PRAGMA user_version`
- [ ] Migration idempotency test passes on all platform targets
- [ ] Backup-before-migrate flow tested (simulated upgrade)
- [ ] DB corruption recovery tested (simulated corruption)
- [ ] Prune job tested (data older than retention thresholds correctly removed)

### Security & Privacy
- [ ] `LocalhostOnlyMiddleware` rejection tested (attempted non-loopback call)
- [ ] Export confirmation gate tested (`confirmed: false` → 400)
- [ ] Author email exclusion unit test passing
- [ ] Function body non-storage default tested
- [ ] DB file created with `chmod 600` confirmed on all platforms
- [ ] Log redaction test passing (no file paths or code content at INFO level)
- [ ] Dependency hash manifest current and passing in CI

### Reliability & SLOs
- [ ] All SLOs in §11.1 measured against real fixture repo
- [ ] SLO-1 (IDE scan ≤ 500ms p95) passing on all E2E platforms
- [ ] SLO-2 (pre-commit ≤ 2s p95) passing on all E2E platforms
- [ ] SLO-3 (full build ≤ 10min) measured and documented
- [ ] Scanner degraded mode tested (scanner binary killed mid-scan)
- [ ] Daemon restart job recovery tested
- [ ] Disk full simulation tested (no DB corruption)
- [ ] `codedna status --slo` output reviewed for accuracy

### Testing & CI
- [ ] All CI gates in §10.4 green on all platform matrix targets
- [ ] Unit test coverage ≥ 80% for harvester and daemon modules
- [ ] Integration tests cover all §10.3 key test cases
- [ ] E2E tests cover all SLO measurements
- [ ] Rust scanner: `cargo test` passes; `clippy` clean

### Release & Distribution
- [ ] All release artifacts built and signed (§12.2)
- [ ] Upgrade flow tested: v0.x → v1.0 migration path validated
- [ ] Rollback tested: v1.0 → v0.x with backup restore
- [ ] Platform matrix smoke test (install → init → build → scan) on all targets
- [ ] Homebrew formula and VS Code marketplace listing reviewed

### Documentation
- [ ] README reflects final CLI commands
- [ ] CHANGELOG.md current through 1.0
- [ ] This document (`designdoc.md`) matches implementation (final review)
- [ ] `/docs/openapi.json` committed

---

## Appendix B — Performance Budget Reference

| Operation                  | p50 Target | p95 Target  | Constraint  |
|----------------------------|------------|-------------|-------------|
| IDE file scan (fast path)  | ≤ 100ms    | ≤ 500ms     | C6, SLO-1   |
| Pre-commit hook total      | ≤ 500ms    | ≤ 2s        | C7, SLO-2   |
| Full baseline build (500k) | ≤ 5min     | ≤ 10min     | C8, SLO-3   |
| Daemon cold start          | ≤ 1s       | ≤ 3s        | SLO-4       |
| Explainer NL generation    | ≤ 10ms     | ≤ 50ms      | §6.3        |
| DB prune job               | ≤ 5s       | ≤ 30s       | §11.3       |
| Migration (per step)       | ≤ 500ms    | ≤ 2s        | §12.3       |
| SSE event delivery lag     | ≤ 100ms    | ≤ 500ms     | §8.4        |
| Rust scanner subprocess    | ≤ 30ms     | ≤ 100ms     | §6.2        |
| Export (JSON, 1yr history) | ≤ 2s       | ≤ 10s       | §8.2        |

---

*End of document. Version 2.0.0. This is the canonical engineering specification 
for CodeDNA. All implementation, migration, and release decisions must be 
traceable to a section of this document or a new ADR entry.*
```

---

A few notes on what was deliberately structured this way:

1. **The SSOT/governance header** means anyone touching migrations, APIs, or schema knows exactly what wins in a conflict — the doc.
2. **The PRR Appendix A** is designed to be a literal checklist you hand to a reviewer before shipping 1.0 — each line is a pass/fail gate, not an opinion.
3. **The ADR section** is "append-only by convention" — this way the *why* behind every major decision is preserved even as the codebase changes.
4. **The error contract table** makes IDE plugin developers' lives easy — they can code against `degraded: true` without guessing.
5. **The migration policy rules** are numbered and binding — so no ambiguity when you're 6 months into the project about whether you can edit an old migration file (you can't).
