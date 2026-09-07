# Corpus-reading scripts run on the pinned March corpus (2026-09-07)

## Provenance

- Corpus root: `$LIBRARIAN_CORPUS`
- Step 0 verification: every row of the three tables in `paper/supplementary/repository-commits.md`
  (1 Primary Archive + 34 Community Marketplace + 24 Curated Sub-Repositories = 59 rows) has a
  worktree under the corpus root whose `git rev-parse HEAD` starts with the recorded SHA, and
  `git status --porcelain` is empty for every row except `clawhub-archive`, which shows exactly 28
  modified files (the expected macOS case-collision artifact). 0 mismatches. Result: PASS.
- Python: 3.13.5
- datasketch: 1.8.0
- Repo git HEAD at time of these runs: `<private-history>`, a commit in the
  authors' private drafting repository that cannot be resolved from this one
- Exact commands:

```
LIBRARIAN_CORPUS=$LIBRARIAN_CORPUS \
  CLUSTER_GAP_OUT=out \
  python paper/sources/scans/cluster_gap_recompute.py

LIBRARIAN_CORPUS=$LIBRARIAN_CORPUS \
  python paper/sources/scans/seed_robustness.py

LIBRARIAN_CORPUS=$LIBRARIAN_CORPUS \
  python paper/sources/scans/order_permutation.py

LIBRARIAN_CORPUS=$LIBRARIAN_CORPUS \
  python paper/sources/scans/file_level_precision.py

python paper/sources/scans/table2_distinct_files.py --check
```

All five commands exited 0. No tolerance guard fired.

## a. `cluster_gap_recompute.py`

| metric | value |
|---|---:|
| files in index | 31,634 |
| signatures computed | 31,634 |
| skipped (missing) | 0 |
| recomputed clusters | 2,622 |
| recomputed slots | 7,147 |
| recomputed distinct | 7,061 |
| archived clusters | 2,622 |
| archived slots | 7,147 |
| archived distinct | 7,061 |
| clusters only in archive | 0 |
| clusters only in recompute | 0 |
| files whose membership differs | 0 |

The recompute reproduces the archived clustering exactly.

## b. `seed_robustness.py`

Per-seed cluster counts, files in clusters, and distinct files:

| seed | clusters | files (sum) | distinct |
|---:|---:|---:|---:|
| 1 | 2622 | 7147 | 7061 |
| 42 | 2562 | 6998 | 6940 |
| 123 | 2558 | 6991 | 6935 |
| 456 | 2604 | 7103 | 7035 |
| 789 | 2592 | 7052 | 6987 |

Pairwise ARI (Hubert-Arabie), 10 seed pairs:

| seed pair | ARI |
|---|---:|
| 1 vs 42 | 0.9697 |
| 1 vs 123 | 0.9699 |
| 1 vs 456 | 0.9589 |
| 1 vs 789 | 0.9627 |
| 42 vs 123 | 0.9694 |
| 42 vs 456 | 0.9663 |
| 42 vs 789 | 0.9690 |
| 123 vs 456 | 0.9667 |
| 123 vs 789 | 0.9592 |
| 456 vs 789 | 0.9491 |

ARI range: minimum 0.9491 (456 vs 789), maximum 0.9699 (1 vs 123). Rand index range: minimum
0.9999 (456 vs 789), maximum 1.0000.

Seed-1 (default) baseline differs from the archived scan by +0.00% clusters, with 0 unresolved
files. `TOLERANCE_PCT` (1.0%) was not breached.

## c. `order_permutation.py`

| metric | value |
|---|---:|
| files with signatures | 31,634 of 31,634 |
| skipped (missing) | 0 |
| baseline clusters | 2,622 |
| baseline slots | 7,147 |
| baseline distinct | 7,061 |
| baseline vs archived scan | +0.00% clusters, +0.00% files |

Per-shuffle (K=10, seeds 1000-1009):

| shuffle | clusters | ARI |
|---:|---:|---:|
| 0 | 2616 | 0.9864 |
| 1 | 2617 | 0.9859 |
| 2 | 2618 | 0.9906 |
| 3 | 2616 | 0.9909 |
| 4 | 2612 | 0.9820 |
| 5 | 2616 | 0.9921 |
| 6 | 2616 | 0.9865 |
| 7 | 2614 | 0.9843 |
| 8 | 2618 | 0.9849 |
| 9 | 2617 | 0.9843 |

ARI range: minimum 0.9820 (shuffle 4), maximum 0.9921 (shuffle 5). The baseline cluster count of
2,622 matches the archived scan exactly.

## d. `file_level_precision.py`

Corpus-independent figures (read the archived scan and `iocs.json`, never the filesystem):

| metric | value |
|---|---:|
| strict precision, >=20 | 305/307 = 0.993 |
| study precision, >=20 | 305/307 = 0.993 |
| content precision, >=20 | 307/307 = 1.000 |
| strict precision, >=10 | 557/682 = 0.817 |
| study precision, >=10 | 557/682 = 0.817 |
| content precision, >=10 | 559/682 = 0.820 |

The `>= 20` and `>= 10` rows matched Table 4 under the `study` definition; the STOP guard did not
fire (exit 0).

Exploratory content-marker column, which does read the corpus:

| metric | value |
|---|---:|
| unreadable locations | 0 of 7,147 |
| unreadable, >=20 cluster set (307 files) | 0 |
| unreadable, >=10 cluster set (682 files) | 0 |
| unreadable, >=5 cluster set (1,480 files) | 0 |
| `clawdhub.com`-driven content-only files, all clusters | 31 of 44 |

Every corpus worktree resolves, so no location is unreadable. The all-clusters content-only count
is 31 of 44 (`file-level-precision-20260907.md` line 12); those files sit in clusters below size 5
and fall outside every threshold this report cites.

## e. `table2_distinct_files.py --check`

No corpus access. Self-test passed. Recomputed table matched the committed
`table2-distinct-files-20260907.md` byte for byte. Exit 0.

| threshold | clusters | memberships | distinct |
|---:|---:|---:|---:|
| 70% | 3,267 | 9,922 | 9,202 |
| 75% | 3,129 | 8,874 | 8,587 |
| 80% | 2,972 | 8,199 | 8,068 |
| 85% | 2,839 | 7,739 | 7,657 |
| 90% | 2,622 | 7,147 | 7,061 |
| 95% | 2,409 | 6,547 | 6,509 |

This script has no dependence on the corpus, only on the archived scans.
