# Baseline Comparison: Trivial Methods vs. MinHash Clustering

Computed 2026-03-14 against the ClawHub skill corpus (31,634 files)
from the similarity report and filesystem archive.

## Known Malicious Authors in Archive

| Author | Skills | Source |
|--------|--------|--------|
| anisafifi | 4 | Undocumented |
| aslaep123 | not in archive | Antiy CERT |
| danman60 | not in archive | Antiy CERT |
| gpaitai | not in archive | Antiy CERT |
| hightower6eu | 354 | Antiy CERT |
| jordanprater | 16 | Antiy CERT |
| kenblive | 2 | Undocumented |
| lvy19811120-gif | 1 | Antiy CERT |
| moonshine-100rze | 3 | Antiy CERT |
| mupengi-bot | 45 | Undocumented |
| noreplyboter | 2 | Antiy CERT |
| noypearl | 2 | Antiy CERT |
| rjnpage | 1 | Antiy CERT |
| sakaen736jih | 212 | Antiy CERT |
| stveenli | 5 | Trend Micro |
| thiagoruss0 | 38 | Trend Micro |
| timclawbot | 1 | Undocumented |
| zaycv | 28 | Antiy CERT |

Total known malicious authors: 18
Present in archive: 15

## Baseline 1: Author Submission Count Thresholding

Flag all ClawHub authors who published N or more skills.
Compare against known malicious author list.

### Results

| Threshold | Authors flagged | Malicious | Benign | Precision | Author recall | Koi skill recall |
|-----------|----------------|-----------|--------|-----------|---------------|------------------|
| >= 5 | 745 | 7 | 738 | 0.9% | 46.7% (7/15) | 100.0% (566/566) |
| >= 10 | 266 | 6 | 260 | 2.3% | 40.0% (6/15) | 100.0% (566/566) |
| >= 15 | 150 | 6 | 144 | 4.0% | 40.0% (6/15) | 100.0% (566/566) |
| >= 20 | 94 | 5 | 89 | 5.3% | 33.3% (5/15) | 100.0% (566/566) |

### Comparison with MinHash Clustering (Paper Table 2)

Note: these are not directly comparable units. MinHash precision is
cluster-level (fraction of clusters containing confirmed malicious
content). Baseline precision is author-level (fraction of flagged
authors that are known malicious). Both measure the analyst's triage
burden, but at different granularities.

| Threshold | MinHash precision | MinHash recall | Baseline precision | Baseline author recall | Baseline Koi recall |
|-----------|-------------------|----------------|--------------------|------------------------|---------------------|
| >= 5 | 36.8% | 98.8% | 0.9% | 46.7% | 100.0% |
| >= 10 | 84.2% | 98.8% | 2.3% | 40.0% | 100.0% |
| >= 15 | 100.0% | 98.8% | 4.0% | 40.0% | 100.0% |
| >= 20 | 100.0% | 98.8% | 5.3% | 33.3% | 100.0% |

### Top 30 ClawHub Authors by Skill Count

| Rank | Author | Skills | Malicious? |
|------|--------|--------|------------|
| 1 | ivangdavila | 880 |  |
| 2 | hightower6eu | 354 | Yes |
| 3 | 1kalin | 281 |  |
| 4 | sakaen736jih | 212 | Yes |
| 5 | lxgicstudios | 209 |  |
| 6 | sa9saq | 164 |  |
| 7 | alirezarezvani | 157 |  |
| 8 | membranedev | 139 |  |
| 9 | gora050 | 136 |  |
| 10 | byungkyu | 134 |  |
| 11 | wpank | 119 |  |
| 12 | mosonchan2023 | 109 |  |
| 13 | edwardrodriguez703-design | 105 |  |
| 14 | hhhh124hhhh | 105 |  |
| 15 | aiwithabidi | 104 |  |
| 16 | mrgoodb | 70 |  |
| 17 | googleworkspace-bot | 68 |  |
| 18 | cinience | 67 |  |
| 19 | eftalyurtseven | 66 |  |
| 20 | okaris | 66 |  |
| 21 | xiaoyinqu | 66 |  |
| 22 | steipete | 58 |  |
| 23 | guohongbin-git | 57 |  |
| 24 | veeramanikandanr48 | 55 |  |
| 25 | yipintangzsp | 50 |  |
| 26 | mailnike | 49 |  |
| 27 | daniellummis | 47 |  |
| 28 | lijie420461340 | 47 |  |
| 29 | danyangliu-sandwichlab | 45 |  |
| 30 | jk-0001 | 45 |  |

### Malicious Authors Detected at Each Threshold

**>= 5:** hightower6eu, jordanprater, mupengi-bot, sakaen736jih, stveenli, thiagoruss0, zaycv

**>= 10:** hightower6eu, jordanprater, mupengi-bot, sakaen736jih, thiagoruss0, zaycv

**>= 15:** hightower6eu, jordanprater, mupengi-bot, sakaen736jih, thiagoruss0, zaycv

**>= 20:** hightower6eu, mupengi-bot, sakaen736jih, thiagoruss0, zaycv

## Baseline 2: Exact File Hash Deduplication

Compute SHA-256 of every SKILL.md file; group by identical hash.

### Summary

- Files hashed: 31634
- Files missing/unresolvable: 0
- Unique hashes: 28264
- Duplicate hash groups (2+ identical files): 1946
- Total files in duplicate groups: 5316

### Malicious Content Detection

- Duplicate groups containing known malicious authors: 71
- Duplicate groups without known malicious authors: 1875
- Precision (groups): 3.6%

### Koi IOC Skill Capture

- Total Koi author (hightower6eu + sakaen736jih) skills in archive: 564
- Unique SHA-256 hashes among Koi author files: 75
- Koi skills with at least one exact hash duplicate: 538
- **Recall via exact hash matching: 95.4%**
- MinHash clustering recall (paper): 98.8%

### Comparison: Exact Hash vs. MinHash

| Method | Recall (Koi IOC skills) | Groups/Clusters | Notes |
|--------|------------------------|-----------------|-------|
| Exact SHA-256 hash | 95.4% | 1946 dup groups | Only identical files |
| MinHash (90% Jaccard) | 98.8% | 2,622 clusters | Near-duplicate detection |

### Interpretation

The 95.4% recall for exact hashing is higher than expected, indicating that
the campaign tooling produced many byte-identical SKILL.md files across
skills. However, the 75 unique hashes among 564 Koi-author files means
each template was reused an average of 7.5 times with zero variation. The
remaining 26 files (4.6%) had per-skill modifications that broke exact
matching but preserved enough structural similarity for MinHash to capture.

CORRECTED 2026-09-07: the per-file diffs do not bear out the March reading of
those 26. Classifying each against its nearest sibling gives four groups: ten
differ in template-slot text (provider version strings, whitespace, bullet
style, escaping, one C2 path), eight are sakaen736jih copies of a hightower6eu
skill with the payload block absent (gas-tracker, insider-wallets-finder,
phantom, solana, wallet-tracker, yt-summarize, yt-thumbnail-grabber,
yt-video-downloader), seven are distinct skills by the same accounts
(sakaen736jih ethereum, leo-wallet, metamask, solflare, tron, tronlink, and
hightower6eu/pdf-1wso5), and one is body-identical to a sibling and differs
only in its frontmatter. Fourteen of the 26 carry no payload text in the body
at all, and iocs.json lists 24 of the 26 under skill_slugs_without_payload, so
"preserved enough structural similarity" holds for the template-slot group but
not for the set. One of those 24 entries is wrong about its file:
hightower6eu/pdf-1wso5 carries an openclaw-core download and a base64 dropper.
Recomputed figures: paper/sources/scans/exact-hash-baseline-20260907.md, which
reproduces every number above from paper/sources/scans/exact_hash_baseline.py.

The precision gap is the more significant finding. Exact hash deduplication
produces 1,946 duplicate groups, of which only 71 (3.6%) contain known
malicious content. An analyst triaging by hash duplicates faces a 96.4%
false positive rate. MinHash clustering at the >= 20 threshold produces
11 clusters, all confirmed malicious (100% precision).

Note: the paper's 341 IOC count refers to specific Koi-listed skill slugs;
the 564 count here reflects all SKILL.md files from hightower6eu (354) and
sakaen736jih (212) in the archive, which is a superset. The discrepancy
likely reflects skills published after Koi's initial report but before the
archive snapshot.

## Discussion

### Why Author Count Fails as a Detector

Author submission count is a useful triage signal but not a reliable
detector on its own:

1. **High false positive rate at useful thresholds.** At >= 5 skills,
   the majority of flagged authors are legitimate power users. Precision
   only becomes acceptable at thresholds where few authors remain.

2. **No structural signal.** Author count says nothing about whether
   the skills are similar to each other. A legitimate author publishing
   20 diverse skills is indistinguishable from an attacker publishing
   20 templated malicious skills.

3. **Cannot detect cross-author campaigns.** MinHash clustering groups
   files by content similarity regardless of author, detecting campaigns
   that span multiple sock puppet accounts.

### Why Exact Hashing Fails as a Detector

1. **Template variation defeats exact matching.** Campaign tools
   generate per-skill variations (unique names, descriptions) that
   change enough bytes to produce different hashes while preserving
   the malicious payload structure.

   CORRECTED 2026-09-07: the mechanism is real but is not what the 26
   misses show. Only one of the 26 differs from a sibling in its
   frontmatter alone, and none differ only in body lines echoing the
   frontmatter name or description. The four groups are ten
   template-slot differences (version strings, formatting, a payload
   URL), eight same-skill copies with the payload block absent, seven
   distinct skills by the same accounts (six sakaen736jih plus
   hightower6eu/pdf-1wso5, which carries its own payload family), and
   that single frontmatter-only file. Stripping the
   frontmatter before hashing recovers exactly one of the 26 (recall
   538 -> 539 of 564) while raising the duplicate-group count from
   1,946 to 2,185 and the false-positive rate from 96.4% to 96.6%.
   See paper/sources/scans/exact-hash-baseline-20260907.md.

2. **No fuzzy matching.** Even a single byte difference (e.g., a
   different skill name in YAML frontmatter) produces a completely
   different hash.

3. **MinHash's advantage is precisely this gap.** Locality-sensitive
   hashing detects structural similarity at configurable thresholds,
   capturing the 90%+ content overlap that templated campaigns exhibit.

