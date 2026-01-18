# Plugin Librarian

Navigate the Claude Code plugin ecosystem with awareness before install.

## Installation

```bash
# 1. Add the marketplace
claude plugin marketplace add galeep/plugin-librarian

# 2. Install the plugin
claude plugin install librarian

# 3. Run init (one-time, in a Claude session)
/librarian init
```

Init creates the Python environment and builds the similarity index.

## Commands

| Command | Description |
|---------|-------------|
| `/librarian init` | One-time setup (run after install) |
| `/librarian find <query>` | Search plugins by capability |
| `/librarian where <file>` | Find all locations of similar content |
| `/librarian compare <target>` | Compare marketplace/plugin against installed |
| `/librarian impact <target>` | Quick install impact assessment |
| `/librarian installed` | List currently installed plugins |
| `/librarian stats` | Show ecosystem statistics |
| `/librarian scan` | Rebuild the similarity index |

## Examples

```
/librarian find code review
/librarian where backend-architect.md
/librarian compare claude-code-templates
/librarian impact claude-code-workflows/backend-development
```

## What It Does

- **Similarity detection**: Find files that are 70%+ similar across marketplaces
- **Location mapping**: See where the same content appears in different plugins
- **Install impact**: Know what's new vs redundant before installing
- **Capability search**: Find plugins by what they do, not just by name

No claims about provenance. Just observable facts about similarity and location.
