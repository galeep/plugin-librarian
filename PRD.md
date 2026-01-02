# Plugin Librarian: Mini-PRD

## Problem (Validated by Spike)

The Claude Code plugin ecosystem has:
- **Low barrier to entry**: Anyone can create/fork plugins
- **No attribution protocol**: Copies don't reference sources
- **Agent-generated churn**: Shallow adaptations proliferate
- **Massive similarity**: 35% of files exist in near-duplicate clusters

### Spike Results

```
Files scanned:              7,183
Files in similarity clusters: 2,483 (35%)
Redundant copies:           1,511 (21%)
Similarity threshold:       70%
```

**Similarity by marketplace:**

| Marketplace | Files from official sources | Copies of other content |
|-------------|----------------------------|------------------------|
| claude-scientific-skills | 687 | 13 |
| anthropic-agent-skills | 37 | 0 |
| claude-code-templates | 19 | 863 |
| claude-code-plugins-plus | 77 | 443 |

claude-code-templates is 98% similar content from elsewhere.

### Root Cause

Installation is `cp(1)`. No deduplication, no linking, no protocol. The same `backend-architect.md` gets copied into 6 different workflow bundles. Installing multiple bundles = multiple copies of the same content consuming tokens.

## Vision

Plugin Librarian provides **awareness before install**:

1. **Similarity detection**: "These 12 files are 87% similar"
2. **Location mapping**: "They appear in these 5 marketplaces"
3. **User-designated reference**: "Compare everything to what I already have"
4. **Install impact**: "This bundle adds 40 files, 15 are redundant with your reference"

**No claims about provenance or origin.** Just observable facts about similarity and location.

## Key Concepts

### Similarity Clusters
Groups of files with >70% content similarity (configurable). Detected via MinHash/LSH.

### Locations
Every place a similar file appears: `(marketplace, plugin, path)`

### Official Sources
Observable fact: files from `anthropic-*` or `claude-plugins-official` marketplaces. Flagged, not privileged.

### User Reference
User-designated baseline for comparison. "I trust X, compare everything against it."

## Commands

```bash
# Find where similar content exists
/librarian where "backend-architect.md"
# -> Shows all 12 locations where similar files exist

# Set your reference baseline
/librarian set-reference anthropic-agent-skills
# -> "Reference set. 724 files indexed."

# Compare a marketplace against your reference
/librarian compare claude-code-templates
# -> "863 files >70% similar to your reference"
# -> "Installing would add 1,247 files, 33% redundant"

# Check before installing a specific plugin
/librarian check claude-code-workflows/backend-development
# -> "6 of 12 files are >90% similar to files in your reference"

# Search by capability
/librarian find "code review"
# -> Lists agents/skills matching, grouped by similarity cluster
```

## Technical Approach

### Phase 1: Similarity Scan (done)
- MinHash signatures for all content files
- LSH indexing for fast similarity lookup
- Cluster detection at configurable threshold
- Output: `similarity_report.json`

### Phase 2: Location Index
- Map every file to all locations where similar content exists
- Flag official sources
- Support queries by filename, path pattern, or content hash

### Phase 3: Reference System
- User sets reference (marketplace, plugin, or custom set)
- All comparisons measured against reference
- Persists across sessions via memory integration

### Phase 4: Discovery Skill
- Query interface for similarity data
- Pre-install impact analysis
- Capability search via frontmatter parsing

## Success Criteria

1. Before installing a bundle, user sees overlap with what they have
2. User can find all locations of similar content
3. User can set their own trusted reference for comparisons
4. No false claims about provenance or "canonical" sources

## Non-Goals

- **Provenance determination**: We don't claim to know who copied from whom
- **Automatic deduplication**: We inform, user decides
- **Quality ranking**: Similarity != quality

## Appendix: Technical Details

**MinHash parameters:**
- 128 permutations
- 3-word shingles
- 70% default similarity threshold

**File inclusion:**
- All `.md` files >100 characters
- Excludes backup directories

**Largest clusters found:**
- 75 files at 100% similarity (scaffold templates)
- 27 files at 82% similarity (SKILL.md variants)
- 12 files at 87% similarity (backend-architect.md)
