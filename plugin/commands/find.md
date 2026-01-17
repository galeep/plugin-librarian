---
description: Search for plugins by capability (what they do)
argument-hint: capability query (e.g., "code review", "docker", "testing")
allowed-tools: ["Bash"]
---

# Search Plugins by Capability

Search across all marketplaces to find skills and agents that match your needs.

**Query:** $ARGUMENTS

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/run-librarian" find "$ARGUMENTS"
```

Present the results to the user, grouping by marketplace and highlighting:
- Whether results are skills or agents
- Which plugin they belong to
- Brief description of what they do
