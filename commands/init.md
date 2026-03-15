---
description: One-time setup - creates Python environment and builds the similarity index (alias for setup)
allowed-tools: ["Bash"]
---

# Plugin Librarian Setup

Run this once after installing the plugin to set up the Python environment and build the similarity index.

```bash
cd "${CLAUDE_PLUGIN_ROOT}"

# Find a working Python 3 interpreter
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "ERROR: Python 3.8+ is required but not found in PATH."
    echo ""
    echo "Install Python 3 and ensure it's in your PATH."
    exit 1
fi

# Check prerequisites
if [ ! -d ".venv" ]; then
    echo "Using $PYTHON ($(\"$PYTHON\" --version 2>&1))"
    echo "Checking prerequisites..."
    if ! "$PYTHON" -c "import venv" 2>/dev/null; then
        echo ""
        echo "ERROR: python3-venv is required but not installed."
        echo ""
        echo "Install it with:"
        echo "  sudo apt install python3-venv    # Debian/Ubuntu"
        echo "  sudo dnf install python3-venv    # Fedora"
        echo "  brew install python3             # macOS (Homebrew)"
        echo "  sudo port install python3        # macOS (MacPorts)"
        echo "  winget install Python.Python.3   # Windows"
        echo ""
        echo "Or download from https://python.org/downloads/"
        echo ""
        echo "Then run /librarian:init again."
        exit 1
    fi
    echo "Creating Python virtual environment..."
    if ! "$PYTHON" -m venv .venv; then
        echo ""
        echo "ERROR: Failed to create virtual environment."
        echo "Ensure python3-venv is installed and try again."
        exit 1
    fi
fi

echo "Installing dependencies..."
if ! .venv/bin/pip install -q .; then
    echo ""
    echo "ERROR: Failed to install dependencies."
    exit 1
fi

echo "Building similarity index (this may take a minute)..."
if ! .venv/bin/librarian scan; then
    echo ""
    echo "ERROR: Failed to build similarity index."
    exit 1
fi

echo ""
echo "Setup complete! You can now use:"
echo "  /librarian find <query>     - Search by capability"
echo "  /librarian where <file>     - Find similar files"
echo "  /librarian compare <target> - Compare against installed"
echo "  /librarian impact <target>  - Quick install assessment"
```

This will:
1. Create a Python virtual environment in the plugin directory
2. Install the librarian CLI and dependencies
3. Scan all marketplaces and build the similarity index

After setup, all other `/librarian` commands will work automatically.
