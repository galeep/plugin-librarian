# Threshold Sweep Results, 2026-03-14

This file records the output of `python paper/sources/scans/analyze_sweep.py` over
the six archived scans `scan_20260314_threshold{70,75,80,85,90,95}_skillonly.json`
in this directory. The script reads those scans and `paper/iocs.json`; it does not
read the corpus, so LIBRARIAN_CORPUS is not needed to reproduce this file.

It supports Table 2 (Section 4.1, "Threshold sensitivity on 31,634 \texttt{SKILL.md}
files.") and Figure 1 (Section 4.1, "P@$\geq$20 and P@$\geq$10 versus Jaccard
threshold."), and the following sentences in Section 3.3: "Recall against the Koi IOC
list held constant at 99.2\% across all six thresholds, confirming that malicious
campaigns cluster well above the 70\% floor. Precision at the $\geq$20 cluster size
threshold reached 100\% only at 90\% and above, establishing 90\% as the lowest
threshold that eliminates false positives for large-cluster triage."

Column mapping. The Clusters, P@20 and P@10 columns below are Table 2's Clusters,
P@$\geq$20 and P@$\geq$10 columns. The "In clusters" and "Rate" columns count cluster
memberships (the scan's `files_in_clusters`, a sum of cluster sizes); Table 2's Files
and % columns count distinct clustered files, which run lower because clusters
overlap (7,147 memberships over 7,061 distinct files at 90%, Section 4.1). The
distinct-file counts are computed by `table2_distinct_files.py`.

## Configuration
- Corpus: $LIBRARIAN_CORPUS (32 repositories)
- File filter: SKILL.md only (--skill-only)
- Total files: 31,634
- Thresholds tested: 70%, 75%, 80%, 85%, 90%, 95%
- MinHash permutations: 128
- Shingle size: 3-word

## Summary Table

| Threshold | Clusters | In clusters | Rate   | Recall* | P@20   | P@10   | P@5    |
|-----------|----------|-------------|--------|---------|--------|--------|--------|
| 70%       | 3,267    | 9,922       | 31.4%  | 99.2%   | 69.2%  | 33.7%  | 12.3%  |
| 75%       | 3,129    | 8,874       | 28.1%  | 99.2%   | 89.5%  | 48.3%  | 16.2%  |
| 80%       | 2,972    | 8,199       | 25.9%  | 99.2%   | 88.2%  | 69.0%  | 18.5%  |
| 85%       | 2,839    | 7,739       | 24.5%  | 99.2%   | 88.2%  | 68.3%  | 22.6%  |
| 90%       | 2,622    | 7,147       | 22.6%  | 99.2%   | 100.0% | 78.9%  | 25.2%  |
| 95%       | 2,409    | 6,547       | 20.7%  | 99.2%   | 100.0% | 81.2%  | 24.0%  |

*Recall computed against 354 hightower6eu slugs from `paper/iocs.json` (351/354 found).
Recall against Koi's full 341-slug list, reported in Table 4 (Section 4.4), is
337/341 = 98.8%.
The relative recall is identical across all thresholds: all 6 scans find exactly 351/354.

Precision here is cluster-level with the account-path criterion described in
`analyze_sweep.py`: a cluster is a true positive when any of its files sits under one
of the attacker accounts in `paper/iocs.json`. Table 4 (Section 4.4) reports precision
at the 90% threshold from the triage record; its caption states that only the
$\geq$20 and $\geq$10 rows reproduce from the released ground truth, so the P@5 column
here is not the $\geq$5 row of Table 4.

## Findings

1. **Recall is threshold-invariant**: 99.2% at all thresholds. The 3 missing
   slugs are the same in every scan. Section 4.4 accounts for them: 2 are skipped by
   the backup-path filter (Section 3.2), and of the 352 scanned, 351 appear in
   clusters.

2. **P@20 reaches 100% at 90%**: The 90% threshold is the lowest at which no cluster
   of 20 or more files lacks a known-malicious file.

3. **90% is the threshold of the primary analysis**: Section 3.3 selects it as the
   lowest threshold that eliminates false positives for large-cluster triage, with
   memberships covering 22.6% of files. The Table 2 caption records that the choice was
   made post-hoc from this sweep.

4. **P@10 rises from 33.7% at 70% to 81.2% at 95%**, with one dip between 80%
   (69.0%) and 85% (68.3%); the Figure 1 caption describes precision as generally
   increasing with threshold.

5. **P@5 peaks at 90% (25.2%)** and is lower at 95% (24.0%). Figure 1 omits
   P@$\geq$5; Table 4 gives the $\geq$5 row at 90% from the triage record.

## Cluster Type Distribution

| Threshold | Cross-mkt | Internal | Scaffold |
|-----------|-----------|----------|----------|
| 70%       | 1,753     | 1,490    | 24       |
| 75%       | 1,737     | 1,363    | 29       |
| 80%       | 1,708     | 1,233    | 31       |
| 85%       | 1,679     | 1,127    | 33       |
| 90%       | 1,602     | 976      | 44       |
| 95%       | 1,459     | 901      | 49       |

The three types are those of Section 3.3: a scaffold cluster holds 5 or more files
from a single marketplace with mean pairwise similarity of 98% or more, an internal
cluster holds files from one marketplace without meeting the scaffold criteria, and a
cross-marketplace cluster spans two or more marketplaces. Scaffold clusters increase
with threshold because more clusters meet the >=98% average similarity criterion at
higher base thresholds.

## Scan Artifacts

Files in paper/sources/scans/:
- scan_20260314_threshold70_skillonly.json
- scan_20260314_threshold75_skillonly.json
- scan_20260314_threshold80_skillonly.json
- scan_20260314_threshold85_skillonly.json
- scan_20260314_threshold90_skillonly.json (the scan behind the primary analysis)
- scan_20260314_threshold95_skillonly.json
- analyze_sweep.py (analysis script)
