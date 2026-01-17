---
description: Quick impact assessment of installing a marketplace or plugin
argument-hint: marketplace or marketplace/plugin
allowed-tools: ["Bash"]
---

# Quick Impact Assessment

Get a quick summary of what installing this target would add to your current setup.

**Target:** $ARGUMENTS

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/run-librarian" impact "$ARGUMENTS"
```

Give the user a clear recommendation based on the novelty vs redundancy ratio.
