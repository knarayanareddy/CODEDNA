# CodeDNA Quick Start Guide

Get up and running with CodeDNA in 5 minutes.

## Prerequisites

- Python 3.10 or higher
- Git repository you want to track

## Step 1: Install CodeDNA

```bash
git clone https://github.com/knarayanareddy/CODEDNA.git
cd codedna
./scripts/install.sh
```

Verify installation:
```bash
codedna --version
```

## Step 2: Initialize a Repository

```bash
# Navigate to your repository
cd /path/to/your/project

# Initialize CodeDNA
codedna init .
```

You'll see output like:
```
Repository added: /path/to/your/project
Repository ID: abc123-def456-...
```

**Save your Repository ID** - you'll need it for subsequent commands.

## Step 3: Build Baseline Fingerprint

The baseline fingerprint captures your coding style. Build it once:

```bash
codedna build --repo abc123-def456-...
```

This analyzes all Python files in your repository. For large repos, it may take a minute.

**Progress:** The build runs in the background. Check status:
```bash
codedna status
```

## Step 4: Start the Daemon

The daemon provides API access and background processing:

```bash
codedna daemon start
```

You should see:
```
Daemon started with PID 12345
```

## Step 5: Scan Your First File

```bash
# Scan a specific file
codedna scan src/main.py

# Or scan with repo ID
codedna scan src/main.py --repo abc123-def456-...
```

**Sample output:**
```
Scan completed in 45ms
DNA Score: 0.87
Explanation: Consistent with your established patterns.
```

### Interpreting DNA Scores

| Score | Meaning |
|-------|---------|
| **0.85 - 1.00** | High confidence match - likely written by you |
| **0.70 - 0.85** | Minor style deviation - some differences detected |
| **0.50 - 0.70** | Significant deviation - may not be your style |
| **< 0.50** | Very different from your baseline |

## Step 6: Set Up Git Pre-Commit Hook (Optional)

Automatically scan files when you commit:

```bash
# Copy the hook to your repo
cp codedna/scripts/git-hooks/pre-commit .git/hooks/

# Make it executable
chmod +x .git/hooks/pre-commit
```

Now when you commit Python files:
```
CodeDNA: Scanning staged changes...
  ✓ src/main.py: 87% style match
CodeDNA: Scanned 1 of 1 files
```

**Note:** The hook always exits 0 (never blocks your commit).

## Step 7: Use VS Code Extension (Optional)

1. Copy the extension to VS Code extensions folder
2. Configure in VS Code settings:
```json
{
  "codedna.daemonUrl": "http://127.0.0.1:7842",
  "codedna.repoId": "abc123-def456-...",
  "codedna.autoScanOnSave": true
}
```
3. The extension will scan files automatically when you save

## Common Commands

```bash
# Show daemon status and stats
codedna status

# Show SLO metrics (last 7 days)
codedna status --slo

# List tracked repositories
codedna config list | grep repos

# Scan a file manually
codedna scan /path/to/file.py --repo <repo-id>

# Export repository data
codedna export --repo <repo-id> --confirmed --output export.json

# Stop the daemon
codedna daemon stop

# Restart the daemon
codedna daemon restart

# Database maintenance
codedna db prune    # Remove old data
codedna db backup   # Create backup
```

## What's Next?

- **[Configuration Guide](CONFIGURATION.md)** - Customize CodeDNA behavior
- **[API Reference](API.md)** - Integrate with other tools
- **[Architecture](ARCHITECTURE.md)** - Understand how it works
- **[Troubleshooting](TROUBLESHOOTING.md)** - Fix common issues

## Example Workflows

### Daily Development

```bash
# Morning: Check status
codedna status --slo

# Work on code...

# Evening: Scan changed files before commit
git add .
.git/hooks/pre-commit
git commit -m "Your changes"
```

### Code Review

```bash
# Compare file against baseline
curl -X POST http://127.0.0.1:7842/api/v1/scan/file \
  -H "X-CodeDNA-Client: cli" \
  -d '{"repo_id": "abc123", "file_path": "/path/to/file.py"}'
```

### CI/CD Integration

```bash
# In your CI pipeline
codedna daemon start
codedna scan test_file.py --repo $REPO_ID
RESULT=$?
codedna daemon stop
exit $RESULT
```

## Privacy Note

CodeDNA is **local-first**:
- All analysis happens on your machine
- No data sent to external servers
- Source code stays local
- Email addresses are never stored
- Function bodies are not stored

Your coding style fingerprint is yours alone.

## Quick Reference

| Action | Command |
|--------|---------|
| Initialize | `codedna init <path>` |
| Build baseline | `codedna build --repo <id>` |
| Start daemon | `codedna daemon start` |
| Stop daemon | `codedna daemon stop` |
| Scan file | `codedna scan <file>` |
| Check status | `codedna status` |
| Get help | `codedna --help` |