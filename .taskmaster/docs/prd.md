# Plugin Librarian - Bug Fixes and Improvements PRD

## Overview
Plugin Librarian helps users discover and compare Claude Code plugins across marketplaces. This PRD captures the bug fixes and improvements identified during January 2026 testing.

## Critical Bug Fixes

### 1. Fix MinHash/LSH Similarity Detection (GitHub #11)
**Priority: High**

The similarity clustering algorithm (70% threshold) failed to detect 98% identical files between claude-scientific-skills and the broader ecosystem. The tool incorrectly reported "0 files in similarity clusters" when direct comparison showed 136/139 skills had near-identical content elsewhere.

**Acceptance Criteria:**
- Files with >70% similarity appear in clusters
- Cross-marketplace duplicates are reliably detected
- Add test case with known duplicate files to prevent regression

### 2. Add Sanity Checks for Surprising Results (GitHub #12)
**Priority: Medium**

When results are statistically improbable (e.g., 0% overlap for a large marketplace), the tool should flag this rather than present it confidently.

**Acceptance Criteria:**
- Flag marketplaces with 0 cluster membership when ecosystem has thousands of clusters
- Warn when similarity ratios are extreme (<5% or >95%) for large datasets
- Output includes confidence indicators

## Feature Improvements

### 3. Add Progress Feedback (GitHub #2)
**Priority: Medium**

Long-running operations (scanning, indexing) provide no feedback. Users don't know if the tool is working or hung.

**Acceptance Criteria:**
- Progress bar or percentage for scans
- Estimated time remaining for long operations
- Clear indication when processing completes

### 4. Show Content Differences (GitHub #3)
**Priority: Medium**

When files are similar but not identical, show what differs. Currently only similarity percentage is shown.

**Acceptance Criteria:**
- Diff view for similar files
- Highlight meaningful differences vs whitespace/formatting

### 5. Marketplace-to-Marketplace Comparison (GitHub #1)
**Priority: Medium**

Compare two marketplaces directly to see overlap.

**Acceptance Criteria:**
- Command to compare marketplace A vs B
- Output shows shared content, unique to A, unique to B

### 6. Marketplace-Level Similarity Queries (GitHub #4)
**Priority: Low**

Query similarity at the marketplace level rather than file level.

### 7. Improve similarity_report.json Query Ergonomics (GitHub #5)
**Priority: Low**

The JSON output is hard to query. Make it more accessible.

### 8. Semantic Capability Search (GitHub #6)
**Priority: Low**

Find skills by what they do, not just by filename or content hash.

### 9. Add Describe Command (GitHub #7)
**Priority: Low**

Introspect a skill to understand what it does.

### 10. Add Checkout Command (GitHub #8)
**Priority: Low**

Copy skills for local use/modification.

### 11. Extract Shared Core (GitHub #9)
**Priority: Low**

Architecture work to enable plugin-toolkit ecosystem.

## Dependencies
- Bug #11 (similarity detection) should be fixed before feature work
- Sanity checks (#12) can be done in parallel with bug fix
- Progress feedback (#2) improves all long-running operations

## Success Metrics
- Similarity detection catches >95% of true duplicates
- No false negatives for files with >70% similarity
- Users can trust tool output without manual verification
