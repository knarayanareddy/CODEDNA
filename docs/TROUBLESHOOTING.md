# CodeDNA Troubleshooting Guide

Common issues and their solutions.

## Installation Issues

### "Python 3.10 or higher is required"

**Symptom:**
```
Error: Python 3.10 or higher is required. Found: 3.8.10
```

**Solution:**
```bash
# Check Python version
python3 --version

# Install Python 3.10+ (Ubuntu/Debian)
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev

# Create virtual environment with new Python
python3.10 -m venv venv
source venv/bin/activate
pip install -e .

# Or use pyenv
pyenv install 3.12.0
pyenv local 3.12.0
```

---

### "Rust build failed"

**Symptom:**
```
error: failed to run custom build command for ...
```

**Solution:**
This is non-critical. CodeDNA uses Python fallback automatically:

```bash
# Verify Python fallback works
codedna scan --help

# If you want Rust, install Rust properly
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
cd rust-scanner && cargo build --release

# Copy binary
cp target/release/codedna-scanner ../../bin/
```

---

### "Permission denied" errors

**Symptom:**
```
PermissionError: [Errno 13] Permission denied: '/home/user/.codedna'
```

**Solution:**
```bash
# Fix permissions
chmod 755 ~/.codedna
chmod 755 ~/.codedna/logs 2>/dev/null || mkdir ~/.codedna/logs
```

---

## Daemon Issues

### "Daemon is not running" - but it's running

**Symptom:**
```bash
$ codedna status
Daemon is not running.

$ curl http://127.0.0.1:7842/health
{"status":"healthy"}
```

**Solution:**
The PID file may be stale. Clean up:

```bash
# Remove stale PID file
rm ~/.codedna/daemon.pid

# Restart
codedna daemon stop 2>/dev/null
codedna daemon start
```

---

### "Address already in use"

**Symptom:**
```
ERROR: Cannot start daemon: Address already in use (port 7842)
```

**Solution:**
```bash
# Find and kill existing process
lsof -i :7842
kill <PID>

# Or use codedna to stop
codedna daemon stop

# Then restart
codedna daemon start
```

---

### Daemon crashes on Windows

**Symptom:**
```
AttributeError: module 'os' has no attribute 'fork'
```

**Solution:**
This was fixed in v0.3.0. Upgrade:

```bash
pip install --upgrade codedna
```

---

### High memory usage

**Symptom:**
```
RSS: 500MB (expected < 100MB)
```

**Solution:**
1. Check for memory leaks:
```bash
# Restart daemon
codedna daemon stop
codedna daemon start
```

2. Prune old data:
```bash
codedna db prune
```

3. Reduce retention:
```bash
codedna config set retention.scan_days 30
codedna config set retention.job_days 7
```

---

## Scanner Issues

### "Scanner timed out"

**Symptom:**
```json
{
  "scan_id": "...",
  "dna_score": null,
  "degraded": true,
  "error": "Scanner timed out"
}
```

**Solution:**
1. Check file size (large files timeout):
```bash
ls -la large_file.py
# If > 1MB, that's the issue
```

2. Increase timeout:
```bash
codedna config set scanner.timeout_ms 5000
codedna daemon restart
```

3. Use Python fallback (slower but more reliable):
```bash
codedna config set scanner.prefer_rust false
```

---

### "No fingerprint available"

**Symptom:**
```json
{
  "scan_id": "...",
  "dna_score": null,
  "degraded": true,
  "explanation": {"summary": "No fingerprint available"}
}
```

**Solution:**
Build the baseline fingerprint first:

```bash
# Get repository ID
codedna status

# Build baseline (this may take a while)
codedna build --repo <REPO_ID>

# Or start daemon and build via API
codedna daemon start
curl -X POST http://127.0.0.1:7842/api/v1/repos/<REPO_ID>/build \
  -H "X-CodeDNA-Client: cli"
```

---

### "Database out of disk space"

**Symptom:**
```
sqlite3.OperationalError: database or disk is full
```

**Solution:**
1. Prune old data:
```bash
codedna db prune
```

2. Create backup and reset:
```bash
codedna db backup
codedna config set retention.scan_days 30
codedna daemon restart
```

3. Move database to larger partition:
```bash
# Stop daemon
codedna daemon stop

# Move database
mv ~/.codedna/codedna.db /new/path/

# Update config
codedna config set database.path /new/path/codedna.db
```

---

## API Issues

### "X-CodeDNA-Client header is required"

**Symptom:**
```json
{
  "error": {
    "code": "MISSING_CLIENT_HEADER",
    "message": "X-CodeDNA-Client header is required for all API requests"
  }
}
```

**Solution:**
Add the header to your requests:

```bash
curl -H "X-CodeDNA-Client: cli" http://127.0.0.1:7842/api/v1/status
```

---

### "Rate limit exceeded"

**Symptom:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded..."
  }
}
```

**Response headers include:**
```
Retry-After: 60
```

**Solution:**
1. Wait and retry
2. Reduce request frequency
3. Check for runaway processes

---

### "Connection refused" on localhost

**Symptom:**
```
requests.exceptions.ConnectionError: Connection refused
```

**Solution:**
1. Check if daemon is running:
```bash
curl http://127.0.0.1:7842/health
```

2. Start daemon if not running:
```bash
codedna daemon start
```

3. Check port in config:
```bash
codedna config get daemon.port
```

---

## Feature Extraction Issues

### "Nesting depth seems wrong"

**Symptom:**
Nesting depth values are too low (e.g., 0.04 instead of 4.0).

**Solution:**
Fixed in v0.3.0. Upgrade if on older version:

```bash
pip install --upgrade codedna
```

---

### "Append counts are inflated"

**Symptom:**
`list_append_in_loop` count is much higher than expected.

**Solution:**
Fixed in v0.3.0 with node ID tracking to prevent double-counting in nested loops.

---

### "Feature extraction is slow"

**Symptom:**
Scans take > 100ms.

**Solution:**
1. Check for O(N²) complexity (should be fixed):
```bash
time codedna scan large_file.py
```

2. Use Rust scanner for speed:
```bash
codedna config set scanner.prefer_rust true
```

3. Skip large files:
```bash
codedna config set scanner.max_file_size_kb 512
```

---

## VS Code Extension Issues

### "Extension not activating"

**Solution:**
1. Check extension output:
   - Open Command Palette (`Ctrl+Shift+P`)
   - Run "Developer: Open Extension Host Logs"

2. Verify daemon is running:
```bash
curl http://127.0.0.1:7842/health
```

3. Check configuration:
   - Set `codedna.daemonUrl` to `http://127.0.0.1:7842`
   - Set `codedna.repoId` to your repository UUID

---

### "Extension shows offline even when daemon is running"

**Solution:**
1. Check VS Code settings:
```json
{
  "codedna.daemonUrl": "http://127.0.0.1:7842"
}
```

2. Restart extension:
   - Run "Developer: Reload Window"

3. Check network:
```bash
curl -v http://127.0.0.1:7842/health
```

---

## Git Hook Issues

### "Hook not running"

**Solution:**
```bash
# Check hook is installed
ls -la .git/hooks/pre-commit

# Make it executable
chmod +x .git/hooks/pre-commit

# Test hook manually
.git/hooks/pre-commit
```

---

### "Hook always shows 'No Python files'"

**Solution:**
1. Check staged files:
```bash
git diff --cached --name-only
```

2. Ensure Python files are staged:
```bash
git add *.py
git commit -m "test"
```

---

## Database Issues

### "no such table: fingerprints"

**Symptom:**
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: fingerprints
```

**Solution:**
Run migrations:

```bash
# Reinitialize database
python -c "from codedna.db.session import init_database; init_database()"

# Or use CLI
codedna db repair
```

---

### "Database is locked"

**Symptom:**
```
sqlite3.OperationalError: database is locked
```

**Solution:**
1. Stop all CodeDNA processes:
```bash
codedna daemon stop
pkill -f codedna
```

2. Clear WAL files:
```bash
rm ~/.codedna/codedna.db-wal
rm ~/.codedna/codedna.db-shm
```

3. Restart:
```bash
codedna daemon start
```

---

## Getting Help

### Enable Debug Logging

```bash
export CODEDNA_LOG_LEVEL=DEBUG
codedna daemon stop
codedna daemon start
# Check logs
tail -f ~/.codedna/logs/codedna.log
```

### Check System Info

```bash
# Python version
python --version

# Package version
codedna --version

# Configuration
codedna config list

# Daemon status
codedna daemon status

# Database version
python -c "from codedna.db.schema import get_schema_version; from codedna.db.session import get_raw_connection; print(get_schema_version(get_raw_connection()))"
```

### Run Diagnostics

```bash
# Full diagnostic report
python -c "
import sys
print('Python:', sys.version)
import codedna
print('CodeDNA:', codedna.__version__)
from codedna.db.session import init_database
init_database()
print('Database: OK')
from codedna.daemon.scanner_client import get_rust_scanner_path
print('Rust scanner:', get_rust_scanner_path())
"
```

### Report Issues

When reporting a bug, include:
1. Output of `codedna --version`
2. Python version
3. Full error message
4. Debug logs (if applicable)
5. Steps to reproduce