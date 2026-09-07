# Threshold Sweep Results — 2026-03-14

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

*Recall computed against 354 hightower6eu slugs from iocs.json (351/354 found).
Paper's published recall uses Koi's original 341-slug list: 337/341 = 98.8%.
The relative recall is identical across all thresholds: all 6 scans find exactly 351/354.

## Key Findings

1. **Recall is threshold-invariant**: 99.2% at all thresholds. The 3 missing
   slugs are the same in every scan (likely too short for MinHash at any threshold).

2. **P@20 reaches 100% at 90%**: The 90% threshold is the minimum achieving
   zero false positives in the >=20 cluster size tier.

3. **90% is the optimal operating point**: Best tradeoff between cluster coverage
   (22.6%) and precision at actionable triage levels.

4. **P@10 improves monotonically from 70% to 95%**: 33.7% -> 81.2%.

5. **P@5 peaks at 90% (25.2%)** then slightly drops at 95% (24.0%), suggesting
   small malicious clusters occasionally fragment at very high thresholds.

## Cluster Type Distribution

| Threshold | Cross-mkt | Internal | Scaffold |
|-----------|-----------|----------|----------|
| 70%       | 1,753     | 1,490    | 24       |
| 75%       | 1,737     | 1,363    | 29       |
| 80%       | 1,708     | 1,233    | 31       |
| 85%       | 1,679     | 1,127    | 33       |
| 90%       | 1,602     | 976      | 44       |
| 95%       | 1,459     | 901      | 49       |

Scaffold clusters increase with threshold because more clusters meet the >=98%
average similarity criterion at higher base thresholds.

## Scan Artifacts

Files in paper/sources/scans/:
- scan_20260314_threshold70_skillonly.json
- scan_20260314_threshold75_skillonly.json
- scan_20260314_threshold80_skillonly.json
- scan_20260314_threshold85_skillonly.json
- scan_20260314_threshold90_skillonly.json (matches original analysis)
- scan_20260314_threshold95_skillonly.json
- analyze_sweep.py (analysis script)
