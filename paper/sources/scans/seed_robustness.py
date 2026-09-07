#!/usr/bin/env python3
"""MinHash seed robustness on the pinned March 2026 corpus.

Recomputes MinHash signatures under five permutation seeds (1, 42, 123, 456, 789),
clusters the corpus under each, and reports per-seed cluster counts plus the Rand
index and Hubert-Arabie adjusted Rand index over all ten seed pairs.

Paper statements supported, both in Section 3.3 (Similarity Analysis): "Running the
full analysis with five fixed seeds (the library default, 1, and four arbitrary
others: 42, 123, 456, 789) produced cluster counts of 2,558 to 2,622; the default
seed reproduces the archived scan exactly." and, from a later sentence in the same
paragraph, "distinct clustered files moved from 7,061 to 6,935, a 1.8% spread." Both
come from the per-seed table this script writes. The adjusted Rand index range that
same sentence quotes, 0.931 to 0.955, is computed over every file clustered under
either seed with the remainder as singletons; `recompute_ari.py` reports that
population as `ari_union` in `recompute-ari-results-20260907.json`. The pairwise
table here scores the files clustered under both seeds, the `ari_inter` population of
`recompute-ari-results-20260907.json`, and the two scripts agree on it.

The adjusted Rand index is the Hubert-Arabie form, which subtracts E[a] =
(a+c)(a+d)/n from the observed agreement count. `self_test` pins the formula against
hand-computed pair counts on toy partitions and fails the run on a mismatch, so a
statistic that is not the ARI cannot be reported as one.

Parameters: 0.9 LSH threshold, 100-character minimum file length, greedy first-match
clustering, all-pairs seed comparison.

Inputs. LIBRARIAN_CORPUS (required) names the pinned March corpus; see
paper/supplementary/repository-commits.md for the SHAs. The file list is the
`file_index` of `scan_20260314_threshold90_skillonly.json`, committed beside this
script, 31,634 entries, read in its stored order.

Output: `seed-robustness-<UTC date>.md` beside this script, or the full path in
SCAN_RESULTS_OUT. A second run on the same UTC day overwrites the day's file.

Run, with LIBRARIAN_CORPUS set:
  python paper/sources/scans/seed_robustness.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import datetime
import json
import math
import subprocess

from datasketch import MinHash, MinHashLSH
from librarian.core import tokenize, NUM_PERM

THRESHOLD = 0.9
SEEDS = [1, 42, 123, 456, 789]  # 5 different seeds

def require_corpus():
    """Corpus root from LIBRARIAN_CORPUS, or exit; there is no default.

    DESIGN RATIONALE: a default corpus path would hand a reproducer plausible
    numbers computed against the wrong tree. No default is right, so there is
    none, and a missing or wrong value stops the run.
    """
    value = os.environ.get("LIBRARIAN_CORPUS")
    if not value:
        sys.exit("LIBRARIAN_CORPUS is unset; set it to the pinned March snapshot "
                 "(see paper/supplementary/repository-commits.md) and rerun.")
    root = os.path.expanduser(value)
    if not os.path.isdir(root):
        sys.exit(f"LIBRARIAN_CORPUS={value} is not a directory; set it to the pinned "
                 "March snapshot (see paper/supplementary/repository-commits.md) and rerun.")
    return root


CORPUS_DIR = require_corpus()

# DESIGN RATIONALE: the file list comes from the archived scan committed beside
# this script, not from a live report under the tool's data directory, so the
# input is pinned with the corpus. The archived scan's `file_index` is the index
# of the 2026-03-14T13:10Z 90% scan that is the paper's primary analysis, 31,634
# entries in stored order.
SCAN = os.path.join(os.path.dirname(__file__), "scan_20260314_threshold90_skillonly.json")
# The default output name carries today's UTC date, so a run on another day cannot overwrite
# a tracked file; SCAN_RESULTS_OUT (a full path) overrides it.
_DEFAULT_OUT_NAME = "seed-robustness-{}.md".format(
    datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d"))
OUT = os.environ.get("SCAN_RESULTS_OUT") or os.path.join(os.path.dirname(__file__), _DEFAULT_OUT_NAME)


def compute_minhash_with_seed(shingles, seed):
    m = MinHash(num_perm=NUM_PERM, seed=seed)
    for s in shingles:
        m.update(s.encode('utf-8'))
    return m


def run_with_seed(files, seed):
    """Run clustering with a specific seed, return set of frozensets (clusters).

    Also returns a tally of how each indexed file was resolved or skipped, so
    that a corpus that half-resolves cannot look like a corpus that clusters
    loosely.
    """
    lsh = MinHashLSH(threshold=THRESHOLD, num_perm=NUM_PERM)

    tally = {"marketplace_path": 0, "bare_path": 0, "missing": 0,
             "short": 0, "empty": 0, "error": 0}

    minhashes = {}
    for i, f in enumerate(files):
        # Read file and tokenize
        try:
            filepath = None
            # Try to find the file
            for base in [CORPUS_DIR]:
                candidate = os.path.join(base, f.marketplace, f.relative_path)
                if os.path.exists(candidate):
                    filepath = candidate
                    tally["marketplace_path"] += 1
                    break
                # Also try without marketplace prefix
                candidate = os.path.join(base, f.relative_path)
                if os.path.exists(candidate):
                    filepath = candidate
                    tally["bare_path"] += 1
                    break

            if filepath is None:
                tally["missing"] += 1
                continue

            with open(filepath, encoding="utf-8", errors="replace") as fh:
                text = fh.read()

            if len(text) < 100:
                tally["short"] += 1
                continue

            shingles = tokenize(text)
            if not shingles:
                tally["empty"] += 1
                continue

            m = compute_minhash_with_seed(shingles, seed)
            minhashes[i] = m
            lsh.insert(str(i), m)
        except Exception as exc:
            tally["error"] += 1
            print(f"  read/hash failed for index {i}: {exc!r}", file=sys.stderr)
            continue

    # Build clusters
    assigned = set()
    clusters = []

    for i in sorted(minhashes.keys()):
        if i in assigned:
            continue
        result = lsh.query(minhashes[i])
        similar = frozenset(int(r) for r in result)
        if len(similar) > 1:
            clusters.append(similar)
            assigned.update(similar)

    return clusters, minhashes, tally


def cluster_similarity(clusters_a, clusters_b):
    """Rand index and Hubert-Arabie adjusted Rand index between two clusterings.

    Returns `(ri, ari, (a, b, c, d))`. Clusters may overlap, because one file
    can be returned by more than one LSH query, so each clustering is first
    flattened to a hard partition by last-cluster-wins; both indices describe
    that flattened assignment, not the overlapping cluster lists.

    Pair counts over the files common to both clusterings: a = together in
    both, b = apart in both, c = together in A only, d = together in B only.
    So a + c is the number of within-cluster pairs in A, and a + d that in B.
    """
    # Build membership maps
    membership_a = {}
    for i, cluster in enumerate(clusters_a):
        for item in cluster:
            membership_a[item] = i

    membership_b = {}
    for i, cluster in enumerate(clusters_b):
        for item in cluster:
            membership_b[item] = i

    # Find common items. Sorted and walked as a nested loop rather than
    # materialized as a list of ~23 million tuples; the pair set, and therefore
    # every count below, is identical either way.
    common = sorted(set(membership_a.keys()) & set(membership_b.keys()))

    a = 0  # same in both
    b = 0  # different in both
    c = 0  # same in A, different in B
    d = 0  # different in A, same in B

    for idx, i in enumerate(common):
        ma_i, mb_i = membership_a[i], membership_b[i]
        for j in common[idx + 1:]:
            same_a = ma_i == membership_a[j]
            same_b = mb_i == membership_b[j]
            if same_a and same_b:
                a += 1
            elif not same_a and not same_b:
                b += 1
            elif same_a and not same_b:
                c += 1
            else:
                d += 1

    n = a + b + c + d
    if n == 0:
        # Fewer than two files in common: agreement is undefined, not zero.
        return float("nan"), float("nan"), (a, b, c, d)

    # Rand Index
    ri = (a + b) / n

    # Adjusted Rand Index (Hubert-Arabie). The numerator counts `a` alone, so
    # the term subtracted is E[a] = (a+c)(a+d)/n, not the expected count of all
    # agreements E[a] + E[b].
    expected = (a + c) * (a + d) / n
    max_val = ((a + c) + (a + d)) / 2
    if max_val == expected:
        # Degenerate: both clusterings place every common pair the same way, so
        # the index has no range to normalize over. Undefined, not zero:
        # returning 0.0 would read as chance-level agreement on a perfect match.
        return ri, float("nan"), (a, b, c, d)
    ari = (a - expected) / (max_val - expected)

    return ri, ari, (a, b, c, d)


def self_test():
    """Check cluster_similarity against hand-computed pair counts.

    Runs before the corpus work and exits the script non-zero on failure. The
    expected values are derived by hand and written out beside each case, so
    the check needs nothing beyond the standard library.
    """
    a3 = [{0, 1, 2}, {3, 4, 5}, {6, 7, 8}]

    # Identical clusterings over 9 items, C(9,2) = 36 pairs.
    # Within-cluster pairs in each: 3 * C(3,2) = 9. So a = 9, c = d = 0,
    # b = 36 - 9 = 27. RI = (9+27)/36 = 1.
    # E[a] = 9*9/36 = 2.25, max = (9+9)/2 = 9, ARI = (9-2.25)/(9-2.25) = 1.
    ri, ari, counts = cluster_similarity(a3, [set(c) for c in a3])
    if counts != (9, 27, 0, 0) or not (math.isclose(ri, 1.0) and math.isclose(ari, 1.0)):
        print(f"self-test FAILED: identical clusterings gave counts={counts}, "
              f"RI={ri}, ARI={ari}; expected (9, 27, 0, 0), 1.0, 1.0", file=sys.stderr)
        return 1

    # A = [{0,1,2},{3,4,5},{6,7,8}] vs B = [{0,1},{2,3,4},{5,6,7,8}], 36 pairs.
    # Within-cluster pairs: A = 9; B = C(2,2 items)=1, C(3,2)=3, C(4,2)=6, so 10.
    # Together in both: (0,1) from A's first and B's first; (3,4) from A's
    # second and B's second; (6,7), (6,8), (7,8) from A's third and B's third.
    # So a = 5, c = 9 - 5 = 4, d = 10 - 5 = 5, b = 36 - 5 - 4 - 5 = 22.
    # RI = (5+22)/36 = 0.75.
    # E[a] = 9*10/36 = 2.5, max = (9+10)/2 = 9.5, ARI = (5-2.5)/(9.5-2.5) = 2.5/7
    #      = 0.35714285714285715.
    ri, ari, counts = cluster_similarity(a3, [{0, 1}, {2, 3, 4}, {5, 6, 7, 8}])
    if counts != (5, 22, 4, 5) or not (math.isclose(ri, 0.75) and math.isclose(ari, 2.5 / 7)):
        print(f"self-test FAILED: got counts={counts}, RI={ri}, ARI={ari}; "
              f"expected (5, 22, 4, 5), 0.75, {2.5 / 7!r}", file=sys.stderr)
        return 1

    # A formula that subtracts E[a]+E[b] = (9*10 + 27*26)/36 = 22.0 instead of
    # E[a] gives (5-22)/(9.5-22) = 1.36 on the case above, outside [-1, 1] for
    # a clustering that agrees on three quarters of its pairs. Asserting the
    # value above rules that form out.

    # Degenerate: every common pair sits together in both clusterings, so the
    # adjusted index has no range to normalize over.
    ri, ari, _ = cluster_similarity([{0, 1}, {0, 1, 2}], [{0, 1, 2}])
    if not (math.isclose(ri, 1.0) and math.isnan(ari)):
        print(f"self-test FAILED: degenerate case gave RI={ri}, ARI={ari}; "
              f"expected 1.0, nan", file=sys.stderr)
        return 1

    print("self-test passed: identical, hand-computed and degenerate cases all match.")
    return 0


def corpus_provenance(root):
    """(directory, short HEAD) for every marketplace directory under the root.

    A directory with no `.git` entry is reported as not a git checkout rather
    than resolved against an ancestor repository, so a stray parent checkout
    cannot lend its SHA to a plain directory.
    """
    rows = []
    if not os.path.isdir(root):
        return rows
    for entry in sorted(os.listdir(root)):
        directory = os.path.join(root, entry)
        if not os.path.isdir(directory):
            continue
        if os.path.exists(os.path.join(directory, ".git")):
            proc = subprocess.run(["git", "-C", directory, "rev-parse", "--short", "HEAD"],
                                  capture_output=True, text=True)
            head = proc.stdout.strip() if proc.returncode == 0 else "git rev-parse failed"
            rows.append((entry, head))
        else:
            rows.append((entry, "not a git checkout"))
    return rows


ARCHIVED_CLUSTERS = 2622
ARCHIVED_FILES_IN_CLUSTERS = 7147
# Same gate as order_permutation.py: past this the baseline is not the archived
# scan's file set, and the absolute cluster counts here are not the paper's.
TOLERANCE_PCT = 1.0


def main():
    print(f"Corpus root: {CORPUS_DIR}")
    print(f"Loading file index from archived scan: {os.path.basename(SCAN)}")
    with open(SCAN, encoding="utf-8") as f:
        data = json.load(f)

    file_index = data["file_index"]
    print(f"Total files in index: {len(file_index)}")

    # Create lightweight file objects
    class SimpleFile:
        def __init__(self, entry):
            self.marketplace = entry["marketplace"]
            self.relative_path = entry["path"]

    files = [SimpleFile(e) for e in file_index]

    results = {}
    tallies = {}
    for seed in SEEDS:
        print(f"\nRunning with seed={seed}...")
        clusters, minhashes, tally = run_with_seed(files, seed)
        files_in_clusters = sum(len(c) for c in clusters)
        print(f"  Signatures: {len(minhashes)}, Clusters: {len(clusters)}, "
              f"Files in clusters: {files_in_clusters}")
        print(f"  Resolution tally: {tally}")
        results[seed] = clusters
        tallies[seed] = tally

    # Compare all pairs
    print("\n" + "=" * 60)
    print("Pairwise Rand Index / Adjusted Rand Index:")
    seeds = list(results.keys())
    rows = []
    for i, s1 in enumerate(seeds):
        for s2 in seeds[i + 1:]:
            ri, ari, (a, b, c, d) = cluster_similarity(results[s1], results[s2])
            common = len({x for cl in results[s1] for x in cl} &
                         {x for cl in results[s2] for x in cl})
            print(f"  Seed {s1} vs {s2}: RI={ri:.4f}, ARI={ari:.4f} "
                  f"(common={common}, a={a}, b={b}, c={c}, d={d})")
            rows.append((s1, s2, common, a, b, c, d, ri, ari))

    # Summary stats
    print("\nCluster count summary:")
    for seed in SEEDS:
        n_clusters = len(results[seed])
        n_files = sum(len(c) for c in results[seed])
        print(f"  Seed {seed}: {n_clusters} clusters, {n_files} files")

    return write_results(data, files, results, tallies, rows)


def write_results(scan, files, results, tallies, rows):
    """Write the dated results file. No timestamps, so reruns are byte-identical."""
    ari_values = [r[8] for r in rows if not math.isnan(r[8])]
    ri_values = [r[7] for r in rows if not math.isnan(r[7])]
    tally = tallies[SEEDS[0]]
    tally_varies = any(tallies[s] != tally for s in SEEDS)
    resolved = tally["marketplace_path"] + tally["bare_path"]

    lines = [
        "# MinHash seed robustness (90% threshold, SKILL.md only)",
        "",
        f"Generated by `paper/sources/scans/{os.path.basename(__file__)}`. Rerun from the "
        "repository root, with `LIBRARIAN_CORPUS` set:",
        "",
        "```",
        f"python paper/sources/scans/{os.path.basename(__file__)}",
        "```",
        "",
        "This file reports, for each of five MinHash permutation seeds, the number of clusters, "
        "files in clusters and distinct clustered files on the pinned March 2026 corpus, and the "
        "Rand index and adjusted Rand index for every pair of seeds. It supports two statements in "
        "Section 3.3 (Similarity Analysis) of the paper: \"Running the full analysis with five fixed "
        "seeds (the library default, 1, and four arbitrary others: 42, 123, 456, 789) produced "
        "cluster counts of 2,558 to 2,622; the default seed reproduces the archived scan exactly.\" "
        "and, from a later sentence in the same paragraph, \"distinct clustered files moved from 7,061 to 6,935, "
        "a 1.8% spread.\" Both come from the per-seed table below. The adjusted Rand index range "
        "that same sentence quotes, 0.931 to 0.955, is computed over every file clustered under "
        "either seed with the remainder as singletons; `recompute_ari.py` reports that population "
        "as `ari_union` in `recompute-ari-results-20260907.json`. The pairwise table here scores "
        "the files clustered under both seeds, which is that file's `ari_inter` population, and the "
        "two agree on it.",
        "",
        f"Output defaults to `seed-robustness-<UTC date>.md`; set "
        "`SCAN_RESULTS_OUT` to a full path to write elsewhere instead of overwriting a "
        "previously dated results file.",
        "",
        f"Input file list: `{os.path.basename(SCAN)}` ({len(files)} entries in `file_index`), "
        "the archived 2026-03-14T13:10Z 90% scan that is the paper's primary analysis, read in "
        "its stored order.",
        "",
        f"Seeds: {', '.join(str(s) for s in SEEDS)}. Similarity threshold: {THRESHOLD}. "
        f"MinHash permutations: {NUM_PERM}. Signatures are recomputed per seed; the clustering "
        "is the same greedy first-match loop over the LSH index, in sorted file-index order.",
        "",
        "## Corpus",
        "",
        "Corpus root: the directory `LIBRARIAN_CORPUS` names, which has no default. "
        "The marketplaces below are git "
        "worktrees pinned to the snapshot SHAs in `paper/supplementary/repository-commits.md`.",
        "",
        "| marketplace directory | HEAD |",
        "|---|---|",
    ]
    for name, head in corpus_provenance(CORPUS_DIR):
        lines.append(f"| `{name}` | `{head}` |")

    lines += [
        "",
        "## File resolution",
        "",
        f"{resolved} of {len(files)} indexed files resolved under the corpus root "
        f"({tally['marketplace_path']} as `<marketplace>/<path>`, {tally['bare_path']} as a bare "
        f"`<path>`), {tally['missing']} did not resolve, {tally['short']} were shorter than 100 "
        f"characters, {tally['empty']} produced no shingles, and {tally['error']} raised while "
        f"being read or hashed. Signatures were computed for "
        f"{resolved - tally['short'] - tally['empty'] - tally['error']} files."
        + ("" if not tally_varies else
           " **The tally differs between seeds, which it should not: file resolution is seed-independent.**"),
        "",
        "## Cluster counts per seed",
        "",
        f"The archived {scan.get('metadata', {}).get('generated_at', '')[:10]} scan reports "
        f"{ARCHIVED_CLUSTERS} clusters and {ARCHIVED_FILES_IN_CLUSTERS} files in clusters (a sum "
        "of cluster sizes). Clusters may overlap, because a file can be returned by more than one "
        "LSH query, so the sum of sizes exceeds the distinct-file count.",
        "",
        "| seed | clusters | vs archived | files in clusters (sum of sizes) | distinct files |",
        "|---:|---:|---:|---:|---:|",
    ]
    for seed in SEEDS:
        clusters = results[seed]
        n_clusters = len(clusters)
        n_slots = sum(len(c) for c in clusters)
        n_distinct = len({x for c in clusters for x in c})
        delta = 100.0 * (n_clusters - ARCHIVED_CLUSTERS) / ARCHIVED_CLUSTERS
        lines.append(f"| {seed} | {n_clusters} | {delta:+.2f}% | {n_slots} | {n_distinct} |")

    seed1 = results[SEEDS[0]]
    seed1_delta = 100.0 * (len(seed1) - ARCHIVED_CLUSTERS) / ARCHIVED_CLUSTERS
    worst = max(SEEDS, key=lambda s: abs(len(results[s]) - ARCHIVED_CLUSTERS))
    worst_delta = 100.0 * (len(results[worst]) - ARCHIVED_CLUSTERS) / ARCHIVED_CLUSTERS
    # DESIGN RATIONALE: the "the corpus under test is the March one" claim is the
    # whole evidential value of this run, so it is asserted only when the default
    # seed actually lands within TOLERANCE_PCT of the archived scan and the file
    # shortfall is no larger than the files that failed to resolve. Otherwise the
    # file states the breach, and main() fails on it.
    seed1_files = sum(len(c) for c in seed1)
    seed1_file_delta = 100.0 * (seed1_files - ARCHIVED_FILES_IN_CLUSTERS) / ARCHIVED_FILES_IN_CLUSTERS
    not_resolved = tally["missing"] + tally["short"] + tally["empty"] + tally["error"]
    baseline_breach = (abs(seed1_delta) > TOLERANCE_PCT
                       or abs(seed1_file_delta) > TOLERANCE_PCT
                       or abs(seed1_files - ARCHIVED_FILES_IN_CLUSTERS) > not_resolved)
    lead = (f"Seed {SEEDS[0]} is datasketch's default, and so is the configuration the scanner "
            f"itself runs under: `librarian/core.py` builds `MinHash(num_perm={NUM_PERM})` with no "
            f"explicit seed. It is therefore the seed the archived scan used, and it differs from "
            f"that scan by {abs(len(seed1) - ARCHIVED_CLUSTERS)} clusters "
            f"({seed1_delta:+.2f}%) and {abs(seed1_files - ARCHIVED_FILES_IN_CLUSTERS)} clustered "
            f"files ({seed1_file_delta:+.2f}%). ")
    if baseline_breach:
        lead += (f"**That is more than the {not_resolved} files this run could not resolve, or more "
                 f"than the {TOLERANCE_PCT:.0f}% tolerance, so the corpus under test is not the "
                 f"one the archived scan was built from and the absolute cluster counts here are "
                 f"not the paper's.** Compare the snapshot table above against the SHAs in "
                 f"`paper/supplementary/repository-commits.md`. The pairwise figures below remain "
                 f"internally valid, because every seed is measured against this same file set.")
    else:
        lead += (f"The {not_resolved} files this run could not resolve account for that difference, "
                 f"so the corpus under test is the March one.")
    lines += [
        "",
        lead + f" The wider spread at the other four seeds, up to "
        f"{worst_delta:+.2f}% at seed {worst}, is the seed sensitivity this experiment measures "
        f"rather than a change in the input; the pairwise table below scores it directly.",
    ]

    lines += [
        "",
        "## Pairwise agreement",
        "",
        "*Rand index (RI)*: the share of file pairs that the two seeds place the same way, "
        "together in a cluster or apart in both.",
        "",
        "*Adjusted Rand index (ARI)*: the Hubert-Arabie chance-corrected form of the Rand index, "
        "`(a - E[a]) / (max - E[a])` with `E[a] = (a+c)(a+d)/n`; 1.0 for identical clusterings, "
        "0.0 for agreement no better than chance, negative for worse than chance.",
        "",
        "Pair counts are taken over the files both seeds cluster, after flattening each seed's "
        "possibly overlapping clusters to a hard partition by last-cluster-wins: `a` together in "
        "both, `b` apart in both, `c` together under the first seed only, `d` together under the "
        "second seed only.",
        "",
        "| seed pair | common files | a | b | c | d | RI | ARI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s1, s2, common, a, b, c, d, ri, ari in rows:
        lines.append(f"| {s1} vs {s2} | {common} | {a} | {b} | {c} | {d} | {ri:.4f} | {ari:.4f} |")

    if ari_values:
        lines += ["", f"Adjusted Rand index over the {len(rows)} seed pairs: minimum "
                      f"{min(ari_values):.4f}, maximum {max(ari_values):.4f}. "
                      f"Rand index: minimum {min(ri_values):.4f}, maximum {max(ri_values):.4f}. "
                      "Both are taken over the files clustered under both seeds; the "
                      "union-population range the paper quotes is described at the top of this "
                      "file."]
    else:
        lines += ["", "No defined ARI values were produced; every pair was degenerate or empty."]
    lines.append("")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"\nWrote {OUT}")
    if baseline_breach:
        print(f"baseline differs from the archived scan by more than {TOLERANCE_PCT:.0f}% or by "
              "more than the files that did not resolve account for; the corpus is not the archived "
              "scan's", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    rc = self_test()
    sys.exit(rc or main())
