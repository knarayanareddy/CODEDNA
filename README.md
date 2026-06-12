# CodeDNA

**Local-first, privacy-preserving developer identity and code intelligence tool**

[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)](https://github.com/knarayanareddy/CODEDNA)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

---

## Overview

CodeDNA is a local-first developer identity tool that analyzes coding style patterns to create a unique "DNA fingerprint" for each developer. It provides stylometric code analysis for:

- **Author attribution** - Identify if code matches your established patterns
- **Code review** - Detect potential style deviations during development
- **Privacy-first** - All analysis happens locally, no cloud dependencies
- **IDE integration** - Real-time feedback as you code

### Key Features

- **32-dimensional feature vectors** capturing coding style patterns
- **Sub-100ms scanning** with Rust-based fast scanner
- **AST-based extraction** for accurate Python analysis
- **Baseline comparison** with cosine similarity scoring
- **Git pre-commit hooks** for automatic style checking
- **VS Code extension** for inline IDE hints
- **Real-time SSE events** for build progress tracking

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CodeDNA Architecture                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌───────────┐    ┌──────────────────────────┐ │
│  │  VS Code │    │ Git Hook  │    │      CLI / API           │ │
│  │ Extension│    │pre-commit │    │  (build, scan, status)   │ │
│  └────┬─────┘    └─────┬─────┘    └────────────┬─────────────┘ │
│       │                │                       │               │
│       └────────────────┼───────────────────────┘               │
│                        │ X-CodeDNA-Client Header               │
│                        ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    FastAPI Daemon (7842)                    ││
│  │  ┌─────────────┐ ┌─────────────┐ ┌────────────────────────┐ ││
│  │  │ Rate Limit  │ │Client Valid.│ │   SSE Event Stream     │ ││
│  │  │ Middleware  │ │ Middleware  │ │   /events              │ ││
│  │  └─────────────┘ └─────────────┘ └────────────────────────┘ ││
│  │  ┌─────────────┐ ┌─────────────┐ ┌────────────────────────┐ ││
│  │  │   Routes    │ │  Job Queue  │ │    EventBus            │ ││
│  │  │ /scan/file  │ │  Workers    │ │    (pub/sub)           │ ││
│  │  └─────────────┘ └─────────────┘ └────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────┘│
│                        │                                        │
│       ┌────────────────┼────────────────┐                      │
│       │                │                │                      │
│       ▼                ▼                ▼                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐             │
│  │ Scanner  │    │ Harvester│    │  Explainer   │             │
│  │ (Rust)   │    │ (Python) │    │  (Templates) │             │
│  │ Fast     │    │ AST      │    │  NL Output   │             │
│  └──────────┘    └──────────┘    └──────────────┘             │
│                        │                                        │
│                        ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    SQLite Database                          ││
│  │  repos | fingerprints | scan_results | jobs | audit_log    ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/knarayanareddy/CODEDNA.git
cd codedna

# Install with all dependencies (includes Rust build)
./scripts/install.sh

# Or install with pip (Python fallback if Rust build fails)
pip install -e .
```

### Basic Usage

```bash
# Initialize a repository for tracking
codedna init /path/to/your/project

# Build baseline fingerprint (one-time setup)
codedna build --repo <REPO_ID>

# Start the daemon (runs in background)
codedna daemon start

# Scan a file manually
codedna scan /path/to/file.py

# Check status and SLO metrics
codedna status --slo

# Stop the daemon
codedna daemon stop
```

---

## Configuration

CodeDNA stores configuration in `~/.codedna/config.json`:

```json
{
    "daemon": {
        "host": "127.0.0.1",
        "port": 7842
    },
    "scanner": {
        "timeout_ms": 2000,
        "max_file_size_kb": 1024
    },
    "privacy": {
        "no_author_emails": true,
        "no_function_bodies": true
    },
    "retention": {
        "scan_days": 90,
        "job_days": 30
    }
}
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/status` | GET | Daemon status and repo info |
| `/api/v1/repos` | GET/POST | List or add repositories |
| `/api/v1/repos/{id}` | DELETE | Remove a repository |
| `/api/v1/repos/{id}/build` | POST | Enqueue baseline build |
| `/api/v1/repos/{id}/data` | DELETE | Erase repo data |
| `/api/v1/jobs/{id}` | GET | Get job status |
| `/api/v1/scan/file` | POST | Scan a file |
| `/api/v1/evolution/{id}` | GET | Get scan history |
| `/api/v1/events` | GET | SSE event stream |
| `/api/v1/export` | POST | Export data |

All API endpoints require `X-CodeDNA-Client` header.

---

## Development

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
python -m pytest tests/e2e/ -v

# Run with coverage
python -m pytest tests/ --cov=codedna --cov-report=html
```

### Project Structure

```
codedna/
├── src/codedna/           # Python package
│   ├── cli/               # CLI commands
│   ├── daemon/            # FastAPI daemon
│   │   ├── app.py         # Main application
│   │   ├── routes.py      # API endpoints
│   │   ├── middleware.py  # Security middleware
│   │   ├── job_queue.py   # Background job processor
│   │   ├── events.py      # SSE event system
│   │   ├── scanner_client.py  # Rust scanner interface
│   │   └── daemon_manager.py  # Cross-platform daemon control
│   ├── db/                # Database layer
│   │   ├── schema.py      # Schema operations
│   │   ├── session.py     # DB session management
│   │   └── models.py      # SQLAlchemy models
│   ├── harvester/         # Feature extraction
│   │   ├── features.py    # 32-dim feature vector
│   │   └── harvester.py   # Repository analysis
│   ├── explainer/         # Natural language output
│   └── config.py          # Configuration management
├── migrations/            # SQL migrations
├── rust-scanner/          # Rust fast scanner
├── ide-plugins/           # IDE integrations
│   └── vscode/            # VS Code extension
├── scripts/               # Installation scripts
│   └── git-hooks/         # Git pre-commit hook
├── dashboard/             # Web dashboard (HTML)
├── tests/                 # Test suite
└── docs/                  # Documentation
```

---

## Privacy & Security

CodeDNA is designed with privacy as a core principle:

- **No cloud dependencies** - All processing happens locally
- **No author emails stored** - Per ADR-005
- **No function bodies stored** - Only fingerprints (C2)
- **Localhost only** - Daemon binds to 127.0.0.1 (C4)
- **CSRF protection** - X-CodeDNA-Client header validation
- **Rate limiting** - 100 req/min per client, 1000/min per IP

---

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues and solutions.

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Ensure all tests pass
5. Submit a pull request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## References

- [Design Document](https://github.com/knarayanareddy/CODEDNA/blob/main/codednadesigndoc.md)
- [Architecture Docs](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Installation Guide](docs/INSTALLATION.md)