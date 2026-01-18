---
description: Rebuild the similarity index by scanning all marketplaces
allowed-tools: ["Bash"]
---

# Rebuild Similarity Index

Scan all marketplaces and rebuild the similarity index. Run this after adding new marketplaces or updating existing ones.

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/run-librarian" scan
```

This will:
- Scan all markdown files across marketplaces
- Compute MinHash signatures for similarity detection
- Build clusters of similar files
- Save the index for fast queries
