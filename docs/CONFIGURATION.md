# CodeDNA Configuration Guide

Detailed guide for configuring CodeDNA.

## Configuration Files

CodeDNA uses two configuration mechanisms:

### 1. User Configuration (`~/.codedna/config.json`)

Main configuration file for user preferences.

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
  },
  "logging": {
    "level": "INFO",
    "file": "~/.codedna/logs/codedna.log"
  }
}
```

### 2. Database Configuration

Stored in the `config` table within the SQLite database. Use the CLI to manage:

```bash
codedna config get <key>
codedna config set <key> <value>
codedna config list
```

## Configuration Options

### Daemon Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `daemon.host` | string | `"127.0.0.1"` | Bind address (loopback only) |
| `daemon.port` | integer | `7842` | Bind port |
| `daemon.workers` | integer | `2` | Background job workers |

### Scanner Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `scanner.timeout_ms` | integer | `2000` | Rust scanner timeout |
| `scanner.max_file_size_kb` | integer | `1024` | Max file size to scan |
| `scanner.prefer_rust` | boolean | `true` | Prefer Rust over Python |

### Privacy Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `privacy.no_author_emails` | boolean | `true` | Don't store email addresses |
| `privacy.no_function_bodies` | boolean | `true` | Don't store function bodies |
| `privacy.hash_content` | boolean | `true` | Hash source code for matching |

### Data Retention

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `retention.scan_days` | integer | `90` | Days to keep scan results |
| `retention.job_days` | integer | `30` | Days to keep job history |
| `retention.auto_prune` | boolean | `true` | Auto-prune old data on startup |

### Logging

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `logging.level` | string | `"INFO"` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `logging.file` | string | `"~/.codedna/logs/codedna.log"` | Log file path |
| `logging.max_size_mb` | integer | `10` | Max log file size before rotation |
| `logging.backup_count` | integer | `3` | Number of backup files to keep |

## CLI Configuration Commands

### Get Configuration

```bash
# Get specific value
codedna config get daemon.host

# List all configuration
codedna config list
```

### Set Configuration

```bash
# Set daemon port
codedna config set daemon.port 8080

# Enable debug logging
codedna config set logging.level DEBUG

# Set retention period
codedna config set retention.scan_days 180
```

### Reset Configuration

```bash
# Reset to defaults (creates backup)
codedna config reset
```

## Environment Variables

Override configuration via environment variables:

| Variable | Description | Overrides |
|----------|-------------|-----------|
| `CODEDNA_CONFIG` | Path to config file | `~/.codedna/config.json` |
| `CODEDNA_DB` | Path to database | `~/.codedna/codedna.db` |
| `CODEDNA_DAEMON_URL` | Daemon URL for CLI | `daemon.host`, `daemon.port` |
| `CODEDNA_LOG_LEVEL` | Log level | `logging.level` |
| `RUST_LOG` | Rust scanner log level | - |

Example:
```bash
export CODEDNA_DB=/custom/path/codedna.db
export CODEDNA_LOG_LEVEL=DEBUG
codedna daemon start
```

## Repository-Specific Configuration

Per-repository settings stored in the database:

```sql
-- View repo configuration
SELECT * FROM repos WHERE id = 'repo-id';

-- Feature weights (future)
ALTER TABLE repos ADD COLUMN feature_weights TEXT;
```

## Advanced Configuration

### Custom Feature Weights

Future: customize which features matter most for your use case.

```json
{
  "feature_weights": {
    "nesting_depth": 2.0,
    "type_hint_rate": 1.5,
    "docstring_rate": 1.0
  }
}
```

### Custom Explainer Templates

Modify `src/codedna/explainer/explainer.py` for custom natural language output.

### Rate Limiting Configuration

Adjust rate limits in middleware (not configurable via file):

```python
# In src/codedna/daemon/middleware.py
class RateLimitMiddleware:
    def __init__(self, app, requests_per_minute: int = 100, ip_requests_per_minute: int = 1000):
```

### Database Encryption (Future)

Not currently implemented. For sensitive environments, use encrypted filesystems.

## Configuration Validation

The daemon validates configuration on startup:

```python
# Validates:
# - Port is in range 1024-65535
# - Timeout is positive
# - Retention days are positive
# - Log level is valid
```

Invalid configuration causes startup failure with clear error message.

## Production Configuration Example

```json
{
  "daemon": {
    "host": "127.0.0.1",
    "port": 7842,
    "workers": 4
  },
  "scanner": {
    "timeout_ms": 3000,
    "max_file_size_kb": 2048,
    "prefer_rust": true
  },
  "privacy": {
    "no_author_emails": true,
    "no_function_bodies": true,
    "hash_content": true
  },
  "retention": {
    "scan_days": 365,
    "job_days": 90,
    "auto_prune": true
  },
  "logging": {
    "level": "WARNING",
    "file": "/var/log/codedna/codedna.log",
    "max_size_mb": 50,
    "backup_count": 5
  }
}
```

## Troubleshooting Configuration

### "Config file not found"

```bash
# Create default config
codedna init
ls ~/.codedna/config.json
```

### "Invalid configuration value"

Check the schema in this document. Common issues:
- Port must be 1024-65535
- Log level must be DEBUG, INFO, WARNING, or ERROR
- Days must be positive integers

### "Config changes not applied"

Restart the daemon after configuration changes:

```bash
codedna daemon restart
```

## Configuration Migration

When upgrading CodeDNA, configuration is preserved. New options get default values.

To see what changed in new versions:

```bash
# Compare with defaults
codedna config list > current.conf
# (check documentation for defaults)
```