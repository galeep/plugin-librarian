# Suspicious scaffold clusters

This file is the scaffold-cluster list that accompanies the paper. It lists the scaffold
clusters in the archived scan whose publishing pattern is consistent with a documented
campaign but whose evidence does not support confirmed classification, giving for each the
publishing account, a representative skill name, the number of near-identical files in the
cluster, and the pattern the cluster shares with a campaign. It supports the closing
sentence of Appendix B (Behavioral Pattern Scan): "Further campaign-consistent but
unconfirmed scaffold clusters accompany the artifact (Appendix C)." It is also the
"scaffold-cluster list" named in Appendix C (Reproduction): "That repository is the
artifact: it holds the tool, the commit table, the similarity matrix, the scaffold-cluster
list, the results files behind the figures reported here, and the reproduction commands
with the tool commit the published scan ran at."

Section 3.3 (Similarity Analysis) defines the cluster type: "A *scaffold* cluster contains
5 or more files from a single marketplace with mean pairwise similarity ≥ 98%, representing
near-duplicate template files originating from one source." The clusters below meet that
definition and carry campaign-consistent patterns, but the evidence does not support
confirmed classification, so they are recorded here rather than counted among the campaigns
of Table 3.

Several scaffold clusters showed campaign-consistent patterns without sufficient evidence
for confirmed classification. `orlyjamie` published `testing-maliicous-vt` (8 copies) and
`peacefulskill` (7 copies), consistent with staging activity; the 8 `polymarketbtc` copies
from `krajekisbtc` match the Polymarket-themed targeting of Campaigns 1 and 4; and one
cluster spanned five nominally independent accounts (`aisadocs`, `0xjordansg-yolo`,
`aisapay`, `chaimengphp`, `bowen-dotcom`), suggesting a single operator. We document these
for completeness; attribution requires further investigation.

## Summary

| account | skill | copies | note |
|---|---|---:|---|
| `orlyjamie` | `testing-maliicous-vt` | 8 | consistent with staging activity |
| `orlyjamie` | `peacefulskill` | 7 | consistent with staging activity |
| `krajekisbtc` | `polymarketbtc` | 8 | matches the Polymarket-themed targeting of Campaigns 1 and 4 |
| `aisadocs`, `0xjordansg-yolo`, `aisapay`, `chaimengphp`, `bowen-dotcom` | (one cluster spanning all five) | | five nominally independent accounts, suggesting a single operator |

The `copies` column is the size of the scaffold cluster that contains the named skill. The
other members of each cluster are near-identical files published by the same account under
different skill names. The Polymarket theme in the third row is visible in the same scan
report: the Campaign 1 account (`hightower6eu`) and both Campaign 4 accounts (`zaycv`,
`jordanprater`) listed in Table 3 publish skill paths named for Polymarket.

## Source

Input: `paper/sources/scans/scan_20260314_threshold90_skillonly.json`, the archived 90%
Jaccard, SKILL.md-only scan report generated on 2026-03-14. Each row corresponds to a
cluster of `type` `scaffold` in that report's `clusters` array; the account and skill names
in the row appear in the `path` field of the cluster's `locations` entries. No script
regenerates this file and no environment variable is required. Corpus commit SHAs are in
`paper/supplementary/repository-commits.md`.
