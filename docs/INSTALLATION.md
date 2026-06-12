# CodeDNA Installation Guide

Complete guide for installing and setting up CodeDNA.

## Requirements

### Software Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.10 | 3.12 |
| Git | 2.0 | Latest |
| Rust (optional) | 1.70 | Latest |

### For Rust Scanner (Optional)

- Rust toolchain (`rustup` recommended)
- Cargo package manager

## Installation Methods

### Method 1: Using Installation Script (Recommended)

```bash
# Clone the repository
git clone https://github.com/knarayanareddy/CODEDNA.git
cd codedna

# Run the installation script
./scripts/install.sh
```

The script will:
1. Check Python version (requires 3.10+)
2. Create `~/.codedna/` directory structure
3. Install Python dependencies
4. Build the Rust scanner (if Cargo is available)
5. Copy the Rust binary to `bin/`

### Method 2: Manual pip Installation

```bash
# Clone and navigate
git clone https://github.com/knarayanareddy/CODEDNA.git
cd codedna

# Install in development mode
pip install -e .

# If Rust scanner is needed, build manually
cd rust-scanner
cargo build --release
cd ../bin
cp ../rust-scanner/target/release/codedna-scanner .
```

### Method 3: Production Wheel Installation

```bash
# Build wheel package
pip wheel . --no-deps --wheel-dir dist

# Install wheel
pip install dist/codedna-*.whl
```

Note: Wheel installation does not include Rust compilation. The Python fallback will be used.

## Installation Structure

After installation, the following structure is created:

```
~/.codedna/
├── codedna.db          # SQLite database
├── config.json         # Configuration file
├── daemon.pid          # Daemon process ID (when running)
├── logs/               # Log files
│   └── codedna.log
└── backup/             # Database backups
```

## Verifying Installation

### Check CLI Works

```bash
$ codedna --version
CodeDNA 0.3.0
```

### Check Python Package

```bash
$ python -c "import codedna; print(codedna.__version__)"
0.3.0
```

### Check Database Initialization

```bash
$ python -c "from codedna.db.session import init_database; init_database(); print('OK')"
OK
```

### Check Rust Scanner (Optional)

```bash
$ ./bin/codedna-scanner --help  # or
$ echo '{"type":"scan_file","language":"python","content":""}' | ./bin/codedna-scanner
```

## IDE Integration

### VS Code Extension

1. Open VS Code
2. Navigate to `ide-plugins/vscode/`
3. Run `npm install` (if Node.js is available)
4. Press `F5` to debug, or
5. Copy the extension folder to `.vscode/extensions/`

**Configuration:**
```json
{
  "codedna.daemonUrl": "http://127.0.0.1:7842",
  "codedna.autoScanOnSave": true,
  "codedna.repoId": "your-repo-uuid-here"
}
```

### Git Pre-Commit Hook

Install the pre-commit hook in your repository:

```bash
# Copy the hook
cp codedna/scripts/git-hooks/pre-commit .git/hooks/pre-commit

# Make it executable
chmod +x .git/hooks/pre-commit

# Or link to the central installation
ln -s /path/to/codedna/scripts/git-hooks/pre-commit .git/hooks/pre-commit
```

Environment variables:
- `CODEDNA_DAEMON_URL` - Override daemon URL (default: `http://127.0.0.1:7842`)

## Docker Installation (Optional)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install Rust
RUN apt-get update && apt-get install -y curl && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# Copy and install
COPY . /app
RUN pip install -e .

# Build Rust scanner
RUN . $HOME/.cargo/env && cd rust-scanner && cargo build --release

CMD ["codedna", "daemon", "start"]
```

## Platform-Specific Notes

### Linux

- No special requirements
- Works with any distribution (Ubuntu, Fedora, Debian, etc.)

### macOS

- Works natively
- May need Xcode command line tools for Rust

### Windows

- **Important:** Use PowerShell or CMD, not Git Bash, for `codedna daemon start`
- The daemon uses `subprocess.Popen` with `DETACHED_PROCESS` flag on Windows
- Firewall may prompt for permission on first run

## Troubleshooting Installation

### "Python 3.10 or higher is required"

```bash
# Check your Python version
python3 --version

# If needed, install Python 3.10+
# On Ubuntu:
sudo apt install python3.10 python3.10-venv
```

### "Rust build failed"

The Rust scanner is optional. The Python fallback will be used automatically:

```bash
# Verify Python fallback works
codedna scan --help

# If you still want Rust, install Rust properly
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
cargo build --release
```

### "Permission denied" on installation

```bash
# Check ~/.codedna permissions
ls -la ~/.codedna

# Fix if needed
chmod 755 ~/.codedna
```

### "Module not found" after pip install

```bash
# Reinstall in development mode
pip install -e .

# Verify
python -c "from codedna import __version__; print(__version__)"
```

## Upgrading

### From v0.2.x to v0.3.x

```bash
# Pull latest changes
git pull origin main

# Reinstall (preserves database)
pip install -e .

# Restart daemon
codedna daemon stop
codedna daemon start
```

### Database Migration

The daemon automatically runs migrations on startup. No manual steps required.

## Uninstallation

```bash
# Stop daemon
codedna daemon stop

# Remove package
pip uninstall codedna

# Remove configuration (optional)
rm -rf ~/.codedna

# Remove git hook (if installed)
rm .git/hooks/pre-commit
```

## Next Steps

After installation:

1. [Initialize a repository](QUICKSTART.md#initialize)
2. [Build baseline fingerprint](QUICKSTART.md#build)
3. [Start the daemon](QUICKSTART.md#daemon)
4. [Configure IDE integration](INSTALLATION.md#ide-integration)