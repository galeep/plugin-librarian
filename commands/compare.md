---
description: Compare a marketplace or plugin against your currently installed plugins
argument-hint: marketplace or marketplace/plugin (e.g., "claude-code-templates" or "claude-code-workflows/backend-development")
allowed-tools: ["Bash"]
---

# Compare Against Installed Plugins

Compare the target marketplace or plugin against what you currently have installed.
Shows what's novel, redundant, or partially overlapping.

**Target:** $ARGUMENTS

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/run-librarian" compare "$ARGUMENTS" -v
```

Summarize findings for the user:
- How many files are novel (new content)
- How many are redundant (already have similar)
- Recommendation on whether to install
