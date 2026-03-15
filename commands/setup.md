---
description: One-time setup - creates Python environment and builds the similarity index
allowed-tools: ["Bash"]
---

# Plugin Librarian Setup

Run this once after installing the plugin. It creates a Python venv, installs dependencies, and scans all your marketplaces to build a similarity index. The scan reads every .md file across all registered marketplaces and computes MinHash signatures, so it takes 1-3 minutes depending on how many marketplaces you have.

Tell the user this will take a minute or two before running the script.

```bash
cd "${CLAUDE_PLUGIN_ROOT}"

echo "Setting up Plugin Librarian..."
echo "This creates a Python environment, installs dependencies, and scans"
echo "all your marketplaces. Expect 1-3 minutes depending on marketplace count."
echo ""

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
    echo "ERROR: Python 3.8+ is required but not found in PATH."
    echo ""
    echo "Install Python 3 and ensure it's in your PATH."
    exit 1
fi

# Check prerequisites
if [ ! -d ".venv" ]; then
    echo "Using $PYTHON ($("$PYTHON" --version 2>&1))"
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
        echo "Then run /librarian:setup again."
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

echo ""
echo "Building similarity index..."
echo "Scanning all registered marketplaces (this is the slow part)."
echo ""
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
