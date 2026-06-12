#!/bin/bash
set -e

echo "Installing CodeDNA..."

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.10"

if ! printf '%s\n%s\n' "$required_version" "$python_version" | sort -V -C; then
    echo "Error: Python $required_version or higher is required. Found: $python_version"
    exit 1
fi

# Create config directory
CONFIG_DIR="$HOME/.codedna"
mkdir -p "$CONFIG_DIR"
mkdir -p "$CONFIG_DIR/logs"
mkdir -p "$CONFIG_DIR/backup"

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -e .

# Build Rust scanner
if command -v cargo &> /dev/null; then
    echo "Building Rust scanner..."
    cd rust-scanner
    if cargo build --release 2>/dev/null; then
        echo "Rust scanner built successfully"
        
        # Copy binary to the expected location for the Python client
        cd ..
        mkdir -p bin
        if [ -f "rust-scanner/target/release/codedna-scanner" ]; then
            cp "rust-scanner/target/release/codedna-scanner" "bin/codedna-scanner"
            chmod +x "bin/codedna-scanner"
            echo "Copied Rust scanner to bin/codedna-scanner"
        elif [ -f "rust-scanner/target/release/codedna-scanner.exe" ]; then
            cp "rust-scanner/target/release/codedna-scanner.exe" "bin/codedna-scanner.exe"
            chmod +x "bin/codedna-scanner.exe"
            echo "Copied Rust scanner to bin/codedna-scanner.exe"
        fi
    else
        echo "Rust build skipped (or failed)"
        cd ..
    fi
else
    echo "Cargo not found - Rust scanner will not be built"
fi

echo ""
echo "Installation complete!"
echo ""
echo "Quick start:"
echo "  1. codedna init /path/to/repo"
echo "  2. codedna build --repo <repo-id>"
echo "  3. codedna daemon start"
echo "  4. Open http://127.0.0.1:7842 for dashboard"
