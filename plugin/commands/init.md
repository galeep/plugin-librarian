---
description: One-time setup - creates Python environment and builds the similarity index (alias for setup)
allowed-tools: ["Bash"]
---

# Plugin Librarian Setup

Run this once after installing the plugin to set up the Python environment and build the similarity index.

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && \
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi && \
echo "Installing dependencies..." && \
.venv/bin/pip install -q . && \
echo "Building similarity index (this may take a minute)..." && \
.venv/bin/librarian scan && \
echo "" && \
echo "Setup complete! You can now use:" && \
echo "  /librarian find <query>     - Search by capability" && \
echo "  /librarian where <file>     - Find similar files" && \
echo "  /librarian compare <target> - Compare against installed" && \
echo "  /librarian impact <target>  - Quick install assessment"
```

This will:
1. Create a Python virtual environment in the plugin directory
2. Install the librarian CLI and dependencies
3. Scan all marketplaces and build the similarity index

After setup, all other `/librarian` commands will work automatically.
