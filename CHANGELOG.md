# Changelog

All notable changes to CodeDNA are documented here.

## [0.3.0] - 2024-06-12

### Added
- **setuptools-rust integration** for native wheel builds
- **Cross-platform daemonization** - Windows support via subprocess.Popen
- **DELETE /repos/{id}/data** endpoint for data erasure
- **Baseline comparison** properly wired through database layer
- **Explainer improvements** - now generates summaries with baseline comparison
- **List append tracking** with node ID tracking to prevent double-counting
- **Per-function nesting depth** calculation (averaged, not divided)

### Fixed
- **Migrations folder** now included in wheel builds (MANIFEST.in)
- **Nesting depth math** - was dividing global max by function count (wrong)
- **List append double-counting** in nested loops
- **SLO epoch date filtering** - was using hardcoded 1970 epoch
- **Windows crash** - os.fork() not available on Windows

### Changed
- **Rust scanner** now accepts baseline_vector parameter for comparison
- **Scanner client** passes baseline vector to Rust when available
- **Version** bumped to 0.3.0 (Beta)

---

## [0.2.0] - 2024-06-12

### Added
- **Single-pass AST visitor** - eliminates O(N²) complexity
- **SSE event system** - EventBus with pub/sub for real-time updates
- **Security middleware** - ClientValidation and RateLimit
- **Daemon manager** - proper PID file management
- **VS Code extension** - real HTTP calls to scan API
- **Git pre-commit hook** - scans staged files via API
- **Test suite** - 48 tests covering critical fixes

### Fixed
- **ZeroDivisionError** in /evolution endpoint
- **Rust scanner path** - searches multiple locations
- **SLO epoch date** - now uses time.time() instead of hardcoded value

### Changed
- **Version** bumped to 0.2.0 (Beta)

---

## [0.1.0] - 2024-06-11

### Added
- Initial release with core functionality:
  - FastAPI daemon with 15+ endpoints
  - 32-dimensional feature vector extraction
  - SQLite persistence with WAL mode
  - Rust scanner scaffold
  - Basic CLI commands (init, build, scan, status)
  - Template-based NL explanation
  - VS Code extension structure
  - Git pre-commit hook structure
  - Web dashboard

### Known Issues
- Many features were stubbed/mock implementations
- Windows support broken
- Baseline comparison not wired through
- Various bugs in feature extraction

---

## Architecture Decision Records (ADRs)

| ADR | Decision |
|-----|----------|
| ADR-001 | 32-dimensional feature vector |
| ADR-002 | Subprocess IPC for Rust scanner |
| ADR-003 | SQLite with WAL mode |
| ADR-004 | Localhost-only daemon |
| ADR-005 | No author emails stored |
| ADR-006 | C9 - Never block developer workflow |

---

## Migration Notes

### Upgrading from v0.1.x to v0.2.x
- Database schema unchanged (version 1)
- No manual migration steps required
- Daemon auto-runs migrations on startup

### Upgrading from v0.2.x to v0.3.x
- Configuration preserved automatically
- Database unchanged
- Restart daemon after upgrade

---

## Deprecation Notes

None yet. This project is in Beta.