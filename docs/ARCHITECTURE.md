# CodeDNA Architecture

This document provides a detailed architectural overview of the CodeDNA system.

## System Overview

CodeDNA follows a client-server architecture with a FastAPI daemon as the central component:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Layer                                 │
│  ┌──────────┐  ┌──────────────┐  ┌─────────┐  ┌───────────────┐   │
│  │  CLI     │  │ VS Code      │  │Git Hook │  │ Other Clients │   │
│  │ (Python) │  │ Extension    │  │(Bash)   │  │ (via REST)    │   │
│  └────┬─────┘  └──────┬───────┘  └───┬─────┘  └───────┬───────┘   │
└───────┼───────────────┼──────────────┼───────────────┼────────────┘
        │               │              │              │
        └───────────────┴──────────────┴──────────────┘
                           │
                    X-CodeDNA-Client Header
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Daemon (FastAPI)                               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     Middleware Stack                          │   │
│  │  ┌────────────┐  ┌───────────────┐  ┌────────────────────┐   │   │
│  │  │ RateLimit  │→ │ ClientValid.  │→ │ LocalhostOnly      │   │   │
│  │  │ 100/min    │  │ X-CodeDNA-Cli │  │ 127.0.0.1 only     │   │   │
│  │  └────────────┘  └───────────────┘  └────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Routes (API)                               │   │
│  │  ┌─────────┐ ┌───────────┐ ┌──────────┐ ┌────────────────┐   │   │
│  │  │ /status │ │ /scan/file│ │ /repos/* │ │ /events (SSE)  │   │   │
│  │  └─────────┘ └───────────┘ └──────────┘ └────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  ┌───────────────────────────┼───────────────────────────────────┐ │
│  │                    Service Layer                               │ │
│  │  ┌───────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐   │ │
│  │  │ Scanner   │ │ Harvester│ │ Explainer  │ │ EventBus     │   │ │
│  │  │ (Rust)    │ │ (Python) │ │ (Templates)│ │ (pub/sub)    │   │ │
│  │  └───────────┘ └──────────┘ └────────────┘ └──────────────┘   │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                              │                                       │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Data Layer (SQLite)                               │
│                                                                      │
│  ┌─────────┐ ┌─────────────┐ ┌──────────────┐ ┌───────────────┐   │
│  │  repos  │ │ fingerprints│ │ scan_results │ │     jobs      │   │
│  └─────────┘ └─────────────┘ └──────────────┘ └───────────────┘   │
│                                                                      │
│  ┌─────────────┐ ┌──────────┐ ┌────────────┐                       │
│  │ config      │ │audit_log │ │ feature_vec│                       │
│  └─────────────┘ └──────────┘ └────────────┘                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Descriptions

### 1. CLI (`src/codedna/cli/`)

Command-line interface for all user interactions:

```
codedna init <path>              # Initialize repository
codedna build --repo <id>        # Build baseline fingerprint
codedna scan <file>              # Scan a single file
codedna status [--slo]           # Show daemon status
codedna daemon start|stop|status # Manage daemon
codedna export --repo <id>       # Export data
```

**Key files:**
- `main.py` - Entry point and command routing
- Uses `X-CodeDNA-Client: cli` header for API calls

### 2. Daemon (`src/codedna/daemon/`)

FastAPI application running on localhost:7842.

#### Middleware Stack

1. **RateLimitMiddleware** - Prevents abuse
   - 100 requests/minute per client
   - 1000 requests/minute per IP
   - Returns 429 with `Retry-After` header

2. **ClientValidationMiddleware** - Security
   - Validates `X-CodeDNA-Client` header presence
   - Exempts `/health`, `/docs`, `/redoc`

3. **LocalhostOnlyMiddleware** - Network security
   - Rejects non-loopback requests
   - Allows `testclient` for testing

#### API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/status` | GET | Daemon health and repo status |
| `/repos` | GET/POST | List/add repositories |
| `/repos/{id}` | DELETE | Remove repository |
| `/repos/{id}/build` | POST | Enqueue baseline build |
| `/repos/{id}/data` | DELETE | Erase repo data |
| `/jobs/{id}` | GET | Get job status |
| `/scan/file` | POST | Scan file against baseline |
| `/evolution/{id}` | GET | Get scan history |
| `/events` | GET | SSE event stream |
| `/export` | POST | Export data |

#### Job Queue (`job_queue.py`)

Background processor for baseline builds:

- **Workers:** 2 concurrent workers
- **Status:** QUEUED → RUNNING → COMPLETE/FAILED
- **Progress:** Real-time progress updates via SSE

```
Worker Flow:
1. Poll for QUEUED jobs (oldest first)
2. Update status to RUNNING
3. Process job (harvest features)
4. Update status to COMPLETE
5. Emit job.complete event
```

#### Event System (`events.py`)

Pub/sub system for real-time updates:

**Event Types:**
- `job.queued` - Job enqueued
- `job.started` - Job processing started
- `job.progress` - Progress update (0.0-1.0)
- `job.complete` - Job completed successfully
- `job.failed` - Job failed with error
- `daemon.status` - Periodic status broadcast
- `scan.complete` - File scan completed
- `build.complete` - Baseline build completed

**SSE Format:**
```
event: job.progress
data: {"job_id": "...", "repo_id": "...", "progress": 0.5}

```

### 3. Database (`src/codedna/db/`)

SQLite database with WAL mode enabled.

#### Schema

```sql
-- Core tables
repos (id, path, name, language, created_at, updated_at, deleted_at)
fingerprints (id, repo_id, version, vector_dims, model_blob, 
              commit_hash, commit_count, file_count, build_duration_s,
              created_at, updated_at, is_active, deleted_at)
scan_results (id, repo_id, fingerprint_id, scan_type, trigger,
              file_path, dna_score, latency_ms, degraded, created_at)
jobs (id, repo_id, type, status, progress, error,
      started_at, completed_at, created_at)
audit_log (id, event_type, entity_type, entity_id, detail, created_at)
config (key, value, updated_at)
feature_vectors (id, repo_id, fingerprint_id, file_path, vector_dims, 
                 vector_data, created_at)
```

#### Session Management

- SQLite with WAL mode for concurrent reads
- Connection pooling via SQLAlchemy
- Automatic migration on startup

### 4. Harvester (`src/codedna/harvester/`)

Feature extraction from Python source code.

#### Feature Vector (32 dimensions)

| Index | Feature | Description |
|-------|---------|-------------|
| 0 | snake_case_ratio | Ratio of snake_case identifiers |
| 1 | single_char_var_rate | Rate of single-char variable names |
| 2 | abbrev_rate | Rate of abbreviations (2-char, 4-char caps) |
| 3 | avg_function_length | Average function body length |
| 4 | nesting_depth | Average nesting depth per function |
| 5 | class_ratio | Class to total definitions ratio |
| 6 | comprehension_rate | List/dict/set comprehension usage |
| 7 | lambda_rate | Lambda expression usage |
| 8 | decorator_rate | Decorator usage |
| 9 | try_except_ratio | Exception handling ratio |
| 10 | bare_except_rate | Bare except clause rate |
| 11 | assert_rate | Assert statement usage |
| 12 | docstring_rate | Docstring presence ratio |
| 13 | inline_comment_density | Comment density |
| 14 | todo_comment_rate | TODO/FIXME comment ratio |
| 15 | stdlib_ratio | Standard library import ratio |
| 16 | relative_import_rate | Relative import ratio |
| 17 | star_import_rate | Star import ratio |
| 18 | line_length_avg | Average line length |
| 19 | line_length_max | Maximum line length |
| 20 | blank_line_density | Blank line density |
| 21 | max_function_params | Maximum parameter count |
| 22 | type_hint_rate | Type hint usage |
| 23 | async_def_rate | Async function ratio |
| 24 | yield_rate | Yield statement ratio |
| 25 | match_case_rate | Match/case usage |
| 26 | walrus_operator_rate | Walrus operator usage |
| 27 | fstring_rate | F-string usage |
| 28 | list_append_in_loop | Loop append usage |
| 29 | dict_get_rate | Dict.get() usage |
| 30 | context_manager_rate | With statement usage |
| 31 | generator_rate | Generator expression usage |

#### Single-Pass AST Visitor

The `FeatureExtractor` class uses a single-pass AST visitor to avoid O(N²) complexity:

```python
class FeatureExtractor(ast.NodeVisitor):
    # Tracks counts per category
    # Uses node ID tracking to avoid double-counting
    # Calculates per-function nesting depths
```

### 5. Scanner (`src/codedna/daemon/scanner_client.py` + `rust-scanner/`)

#### Scanner Pipeline

1. **Python Fallback** (default)
   - Uses `FeatureExtractor` for accurate AST parsing
   - Computes cosine similarity against baseline

2. **Rust Scanner** (when available)
   - Fast pattern-based feature extraction
   - Accepts baseline vector for comparison
   - IPC via stdin/stdout JSON

#### Baseline Comparison

```python
def compute_baseline_similarity(target: List[float], baseline: List[float]) -> float:
    """Cosine similarity between two 32-dim vectors"""
    dot = sum(t * b for t, b in zip(target, baseline))
    mag_t = sqrt(sum(t * t for t in target))
    mag_b = sqrt(sum(b * b for b in baseline))
    return dot / (mag_t * mag_b)

# DNA Score = 0.5 + (similarity * 0.5)
# Range: 0.5 (no match) to 1.0 (perfect match)
```

### 6. Explainer (`src/codedna/explainer/`)

Template-based natural language generation:

```python
def explain(partial_vector, baseline_vector, dna_score, verbosity):
    # Compare vectors, detect changes
    # Generate human-readable summary
    # Categories: very_high, high, medium, low, very_low
```

### 7. IDE Integration (`ide-plugins/vscode/`)

VS Code extension features:

- **Status bar** - Shows daemon online/offline
- **Auto-scan on save** - Monitors `*.py` files
- **Scan command** - Manual scan via command palette
- **Inline feedback** - DNA score in status bar

### 8. Git Hooks (`scripts/git-hooks/pre-commit`)

Pre-commit hook for automated scanning:

```bash
# Reads staged Python files from git index
# Calls /scan/file API for each file
# Shows style match percentages
# Always exits 0 (C9: never block workflow)
```

## Design Decisions (ADRs)

### ADR-001: 32-Dimensional Feature Vector
- Balanced between granularity and performance
- Covers naming, structure, patterns, and style

### ADR-002: Subprocess IPC for Rust Scanner
- JSON over stdin/stdout
- Timeout at 2 seconds
- Fallback to Python on failure

### ADR-003: SQLite with WAL Mode
- Single file, portable
- WAL mode for concurrent reads
- Migrations via SQL files

### ADR-004: Localhost-Only Daemon
- Binds to 127.0.0.1 only
- No network exposure
- Single-user per machine

### ADR-005: No Author Emails
- Privacy by design
- Email addresses not stored anywhere

### ADR-006: C9 Constraint (Never Block)
- Git hooks exit 0 on error
- Daemon never blocks developer workflow

## Performance Characteristics

| Operation | Target | Constraint |
|-----------|--------|------------|
| File scan | <100ms | C6 |
| Baseline build | <30s for 1000 files | C7 |
| Memory usage | <100MB idle | C8 |
| CPU usage | <5% when idle | - |

## Security Model

1. **Network:** Loopback-only, no external exposure
2. **CSRF:** X-CodeDNA-Client header required
3. **Rate Limiting:** Per-client and per-IP limits
4. **Privacy:** No source code or emails stored
5. **Audit:** All operations logged to audit_log table

## Extension Points

- **Custom scanners:** Implement `invoke_scanner()` protocol
- **Additional languages:** Extend `FeatureExtractor`
- **Template explanations:** Modify `explainer.py` templates
- **Storage backends:** Swap SQLite for PostgreSQL (future)