# Reproduction run of the scan scripts (2026-09-07)

This file records one run, on 2026-09-07, of the five scripts in `paper/sources/scans/` that
recompute the paper's clustering figures from the pinned corpus and the archived scans:
`cluster_gap_recompute.py`, `seed_robustness.py`, `order_permutation.py`,
`file_level_precision.py` and `table2_distinct_files.py --check`. Sections a to e give each
script's figures as printed. Four of the scripts also write a results file beside this one
(`seed-robustness-20260907.md`, `order-permutation-20260907.md`,
`file-level-precision-20260907.md`, `table2-distinct-files-20260907.md`);
`cluster_gap_recompute.py` reports on stdout only, so section a is its record.

Paper statements each section supports:

- Section a. Section 3.3 (Similarity Analysis): "the default seed reproduces the archived scan
  exactly." Section 4.1 (Ecosystem Characterization (RQ1)): "At a 90% Jaccard similarity
  threshold, 2,622 clusters held 7,147 memberships over 7,061 distinct SKILL.md files, 22.3% of
  the 31,634 indexed; clusters may overlap, so memberships exceed files."
- Section b. Section 3.3: "Running the full analysis with five fixed seeds (the library default,
  1, and four arbitrary others: 42, 123, 456, 789) produced cluster counts of 2,558 to 2,622; the
  default seed reproduces the archived scan exactly." and, from the same paragraph,
  "distinct clustered files moved from 7,061 to 6,935, a 1.8% spread."
- Section c. Section 3.3: "Permuting the assignment order (10 shuffles, signatures fixed) gave
  adjusted Rand index scores of 0.982 to 0.992 over the files clustered under both orderings, so
  ordering perturbs membership only at the margin."
- Section d. Section 4.4 (IOC Validation): "File-level precision, promised in Section 3.4, is
  305 of 307 files (0.993) at ≥ 20; at ≥ 10 the corresponding figure is membership-level, 557 of
  682 memberships over 643 distinct files, 0.817 (per-cluster results are among the files
  released with the code, Appendix C)." and the Table 4 caption in the same section: "Only the
  ≥ 20 and ≥ 10 rows reproduce from the released ground truth."
- Section e. Table 2 ("Threshold sensitivity on 31,634 SKILL.md files", Section 4.1), whose
  *Files* column is the *distinct* column of section e.

## Provenance

- Corpus root: `$LIBRARIAN_CORPUS`
- Corpus verification, run before the scripts: every row of the three tables in
  `paper/supplementary/repository-commits.md` (1 Primary Archive + 34 Community Marketplace + 24
  Curated Sub-Repositories = 59 rows) has a worktree under the corpus root whose
  `git rev-parse HEAD` starts with the recorded SHA, and `git status --porcelain` is empty for
  every row except `clawhub-archive`, which shows exactly 28 modified files (that commit holds
  path pairs that differ only by case, so a checkout on a case-insensitive filesystem
  reports the second of each pair as modified; no file in the scan index is affected).
  0 mismatches. Result: PASS.
- Python: 3.13.5
- datasketch: 1.8.0
- Repository commit at the time of these runs: `<private-history>`
- Commands, run from the repository root with `LIBRARIAN_CORPUS` set:

```
CLUSTER_GAP_OUT=out python paper/sources/scans/cluster_gap_recompute.py
python paper/sources/scans/seed_robustness.py
python paper/sources/scans/order_permutation.py
python paper/sources/scans/file_level_precision.py
python paper/sources/scans/table2_distinct_files.py --check
```

All five commands exited 0. No tolerance guard fired.

## a. `cluster_gap_recompute.py`

Figures as printed on stdout. The script rebuilds the default-seed 90% clustering from the
corpus files and diffs it against the archived scan; an exact reproduction prints zero for
every row from "clusters only in archive" down.

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

These pairwise values score the files clustered under both seeds. The adjusted Rand index range
the paper quotes for this experiment, 0.931 to 0.955, is computed over every file clustered under
either seed, with the remainder as singletons; `recompute_ari.py` reports that population as
`ari_union` in `recompute-ari-results-20260907.json`, and the `ari_inter` values in the same file
are the ones tabulated above.

The seed-1 (default) baseline differs from the archived scan by +0.00% clusters, and 0 indexed
files were missing under the corpus root. `TOLERANCE_PCT` (1.0%) was not breached.

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

The cluster-level true positives at `>= 20` and `>= 10` under the `study` definition match the
corresponding rows of Table 4 (Section 4.4), so the script's STOP guard did not fire (exit 0).

Exploratory content-marker column, which does read the corpus:

| metric | value |
|---|---:|
| unreadable locations | 0 of 7,147 |
| unreadable, >=20 cluster set (307 files) | 0 |
| unreadable, >=10 cluster set (682 files) | 0 |
| unreadable, >=5 cluster set (1,480 files) | 0 |
| `clawdhub.com`-driven content-only files, all clusters | 31 of 44 |

Every corpus worktree resolves, so no location is unreadable. The all-clusters content-only count
is 31 of 44 (the content-match paragraph under Definitions in `file-level-precision-20260907.md`);
that file's per-threshold sections report 0 `clawdhub.com`-only files in the `>= 20` set and 0 in
the `>= 10` set, so the two figures the paper quotes carry none of them.

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

This script depends only on the six archived scans, not on the corpus.
