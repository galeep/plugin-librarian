# Suspicious scaffold clusters

This is the scaffold-cluster list referred to from the paper's appendix on the behavioral
pattern scan. The text is the paper's own, set in Markdown.

A *scaffold* cluster is a single-marketplace cluster of at least 5 files at at least 98%
mean pairwise similarity, as defined in the paper's Section 3.3. The clusters below carry
campaign-consistent patterns but not enough evidence for confirmed classification, so they
are recorded rather than counted.

Several scaffold-type clusters (single marketplace, >= 5 files, >= 98% similarity) showed
campaign-consistent patterns without sufficient evidence for confirmed classification.
`orlyjamie` published `testing-maliicous-vt` (8 copies) and `peacefulskill` (7 copies),
consistent with staging activity; the 8 `polymarketbtc` copies from `krajekisbtc` match
the Polymarket-themed targeting of Campaigns 1 and 4; and one cluster spanned five
nominally independent accounts (`aisadocs`, `0xjordansg-yolo`, `aisapay`, `chaimengphp`,
`bowen-dotcom`), suggesting a single operator. We document these for completeness;
attribution requires further investigation.

## Summary

| account | skill | copies | note |
|---|---|---:|---|
| `orlyjamie` | `testing-maliicous-vt` | 8 | consistent with staging activity |
| `orlyjamie` | `peacefulskill` | 7 | consistent with staging activity |
| `krajekisbtc` | `polymarketbtc` | 8 | matches the Polymarket-themed targeting of Campaigns 1 and 4 |
| `aisadocs`, `0xjordansg-yolo`, `aisapay`, `chaimengphp`, `bowen-dotcom` | (one cluster spanning all five) | | five nominally independent accounts, suggesting a single operator |

Source scan: `scan_20260314_threshold90_skillonly.json`, the 90% Jaccard, SKILL.md-only
scan of the 2026-03-14 corpus. Corpus commit SHAs are in `repository-commits.md`.
