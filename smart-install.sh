#!/bin/bash
# Smart LLM Stack Installer - Linux/macOS wrapper

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/smart_installer/smart_install.py"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# Run installer
exec python3 "$PYTHON_SCRIPT" "$@"