---
description: Find all locations where similar content exists across plugin marketplaces
argument-hint: filename or pattern (e.g., "backend-architect.md" or "*architect*")
allowed-tools: ["Bash"]
---

# Find Similar Content Locations

Search for files matching the query and show all locations where similar content exists.

**Query:** $ARGUMENTS

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/run-librarian" where "$ARGUMENTS"
```

Present the results to the user, highlighting:
- Number of clusters found
- Which marketplaces contain similar content
- Whether any are from official sources
