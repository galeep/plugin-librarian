# Plugin Librarian

A similarity-aware index for Agent Skills ecosystems (Claude Code, OpenClaw/ClawHub, and other platforms using the format). Scans all installed marketplaces, computes MinHash signatures for every skill and agent file, and answers questions about overlap, duplication, and coverage before you install anything.

## Installation

```bash
# Add the marketplace and install the plugin
claude plugin marketplace add galeep/plugin-librarian
claude plugin install librarian

# One-time setup (creates venv, installs deps, builds index)
/librarian init
```

Requires Python 3.10+. The init step scans every marketplace you have registered and builds a similarity index at `~/.librarian/similarity_report.json`. Takes about a minute for a typical setup.

## Commands

| Command | What it does |
|---------|-------------|
| `/librarian init` | One-time setup: venv, dependencies, initial scan |
| `/librarian find <query>` | Search plugins by what they do, not just by name |
| `/librarian where <file>` | Show every location where similar content appears |
| `/librarian compare <target>` | Compare a marketplace or plugin against what you have installed |
| `/librarian impact <target>` | Estimate what's new vs. redundant before installing |
| `/librarian installed` | List currently installed plugins |
| `/librarian stats` | Show index statistics (file counts, cluster counts, coverage) |
| `/librarian scan` | Rebuild the similarity index |

## Examples

```
/librarian find code review
/librarian where backend-architect.md
/librarian compare claude-code-templates
/librarian impact claude-code-workflows/backend-development
```

## How it works

The scanner reads every `.md` file across all registered marketplaces, computes word-level MinHash signatures (128 permutations, 3-shingle), and indexes them in a locality-sensitive hash. Queries against this index run in milliseconds. Two files are considered similar at 70%+ estimated Jaccard similarity.

The tool reports observable facts about content similarity and location. It does not make claims about provenance or authorship.

## Citation

If you use Plugin Librarian in your research, please cite:

Fagan, G. (2026). Librarian Catches Thief: Surfacing Supply Chain Attack Campaigns via Document Similarity in an AI Agent Skill Registry. Zenodo. https://doi.org/10.5281/zenodo.19035380
