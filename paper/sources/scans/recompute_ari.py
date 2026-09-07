#!/usr/bin/env python3
"""Adjusted Rand index between MinHash clusterings of the pinned March 2026 corpus.

This script recomputes the seed-robustness and order-permutation adjusted Rand
index figures of the paper by a route independent of `seed_robustness.py`. It
shares no code with that script, and its adjusted Rand index is computed from a
contingency table via sums of C(n,2), which is the Hubert-Arabie form written a
different way from the a/b/c/d pair-count loop `seed_robustness.py` uses.
Agreement between the two routes is the check.

Paper statements supported, both in Section 3.3 (Similarity Analysis): "Over the
10 pairwise comparisons among the five seeds, computed over every file clustered
under either seed, with the remainder as singletons, and flattened by
last-cluster-wins, adjusted Rand index scores ranged from 0.931 to 0.955" and
"Permuting the assignment order (10 shuffles, signatures fixed) gave adjusted
Rand index scores of 0.982 to 0.992 over the files clustered under both
orderings, so ordering perturbs membership only at the margin." Section 6
(Limitations) restates both ranges: "the adjusted Rand index runs 0.931 to 0.955
across seeds (all files clustered under either seed) and 0.982 to 0.992 across
orderings".

Three populations are reported for every comparison, each as its own key in the
results file:

  intersection (`ari_inter`) - only files clustered under both labelings. This is
                 the population of the ordering range, 0.982 to 0.992, and of the
                 pairwise table in `seed-robustness-20260907.md`, on which the two
                 scripts agree.
  union (`ari_union`) - every file clustered under at least one labeling; a file
                 not clustered under one of them is its own singleton there. This
                 is the population of the seed range, 0.931 to 0.955.
  corpus (`ari_corpus`) - every file with a signature; unclustered files are
                 singletons under both labelings.

The seed comparison scores all ten pairs among the five seeds, each seed's
clustering produced by the greedy first-match loop over files in sorted index
order. The order comparison holds the seed-1 signatures fixed (seed 1 is the
datasketch default and reproduces the archived scan), takes the sorted-order
clustering as the baseline, and rescores it against ten shuffled processing
orders drawn from `random.Random(1000)` through `random.Random(1009)`.

`self_test()` pins the adjusted Rand index against hand-computed pair counts on a
toy partition pair, checks an identical pair scores 1, and checks a random
relabeling scores near 0; the run stops if any check fails.

Inputs. LIBRARIAN_CORPUS (required) names the pinned March 2026 corpus; see
paper/supplementary/repository-commits.md for the SHAs. The file list is the
`file_index` of `scan_20260314_threshold90_skillonly.json`, committed beside this
script. Parameters: 0.9 LSH threshold, 100-character minimum file length, 128
permutations (`librarian.core.NUM_PERM`), seeds 1/42/123/456/789, shuffle seeds
1000-1009.

Outputs, written beside this script: `recompute-ari-results.json` holding the
resolution tally, per-seed cluster counts, the ten seed rows and the ten order
rows, each row carrying the three populations' sizes and adjusted Rand indices;
and one `clusterings-*.json` per labeling. When OUT_SUFFIX is set, it is inserted
before the file extension of every output name so that two runs can be kept side
by side; it affects no computation. The results file in this artifact,
`recompute-ari-results-20260907.json`, was produced with OUT_SUFFIX=-20260907. The
per-labeling clusterings are intermediates and are not part of this artifact.

Run, with LIBRARIAN_CORPUS set:
  python paper/sources/scans/recompute_ari.py
"""

import json
import os
from pathlib import Path
import random
import sys
from collections import Counter, defaultdict

REPO = str(Path(__file__).resolve().parents[3])  # repository root, for the librarian package
sys.path.insert(0, REPO)

from datasketch import MinHash, MinHashLSH  # noqa: E402
from librarian.core import tokenize, NUM_PERM  # noqa: E402

def require_corpus():
    """Corpus root from LIBRARIAN_CORPUS, or exit; there is no default.

    DESIGN RATIONALE: a default corpus path would hand a reproducer plausible
    numbers computed against the wrong tree. No default is right, so there is
    none, and a missing or wrong value stops the run.
    """
    value = os.environ.get("LIBRARIAN_CORPUS")
    if not value:
        sys.exit("LIBRARIAN_CORPUS is unset; set it to the pinned March 2026 snapshot "
                 "(see paper/supplementary/repository-commits.md) and rerun.")
    root = os.path.expanduser(value)
    if not os.path.isdir(root):
        sys.exit(f"LIBRARIAN_CORPUS={value} is not a directory; set it to the pinned "
                 "March 2026 snapshot (see paper/supplementary/repository-commits.md) and rerun.")
    return root


CORPUS = require_corpus()
SCAN = os.path.join(REPO, "paper/sources/scans/scan_20260314_threshold90_skillonly.json")
OUTDIR = os.path.dirname(os.path.abspath(__file__))
# Output-name suffix only, so two runs can be kept side by side; affects no computation.
# The shipped results file was written with OUT_SUFFIX=-20260907.
SUFFIX = os.environ.get("OUT_SUFFIX", "")

THRESHOLD = 0.9
SEEDS = [1, 42, 123, 456, 789]
MIN_CHARS = 100
SHUFFLE_SEEDS = list(range(1000, 1010))


# --------------------------------------------------------------------------
# adjusted Rand index by contingency table
# --------------------------------------------------------------------------

def _choose2(k):
    return k * (k - 1) // 2


def ari_from_labels(labels_a, labels_b):
    """Hubert-Arabie adjusted Rand index between two label dicts over one key set.

    Returns (ari, n_items, index, expected, maximum) where `index` is
    sum_ij C(n_ij, 2) over the contingency table, `expected` is
    sum_i C(a_i,2) * sum_j C(b_j,2) / C(N,2), and `maximum` is the mean of the
    two marginal pair sums. The result is (index - expected) / (maximum -
    expected), or NaN when the denominator is zero.
    """
    keys = labels_a.keys()
    assert keys == labels_b.keys() or set(labels_a) == set(labels_b)

    joint = Counter()
    marg_a = Counter()
    marg_b = Counter()
    for k in labels_a:
        la, lb = labels_a[k], labels_b[k]
        joint[(la, lb)] += 1
        marg_a[la] += 1
        marg_b[lb] += 1

    n = len(labels_a)
    total_pairs = _choose2(n)
    if total_pairs == 0:
        return float("nan"), n, 0, 0.0, 0.0

    index = sum(_choose2(v) for v in joint.values())
    sum_a = sum(_choose2(v) for v in marg_a.values())
    sum_b = sum(_choose2(v) for v in marg_b.values())

    expected = sum_a * sum_b / total_pairs
    maximum = (sum_a + sum_b) / 2.0
    if maximum == expected:
        return float("nan"), n, index, expected, maximum
    return (index - expected) / (maximum - expected), n, index, expected, maximum


def flatten(clusters):
    """Last-cluster-wins hard assignment: file -> cluster ordinal.

    A file that the greedy loop returned into more than one cluster keeps the
    label of the last cluster listed, which is the flattening the paper names.
    """
    lab = {}
    for k, members in enumerate(clusters):
        for m in members:
            lab[m] = k
    return lab


def three_populations(clusters_a, clusters_b, universe):
    """(intersection, union, corpus) adjusted Rand index for one pair of clusterings.

    `universe` is every file with a signature. Singleton labels are made unique
    per labeling by tagging them with the file id, so no two unclustered files
    ever share a label. Returns the three `ari_from_labels` tuples followed by
    the intersection and union sizes.
    """
    la = flatten(clusters_a)
    lb = flatten(clusters_b)

    inter = set(la) & set(lb)
    union = set(la) | set(lb)

    def restrict(base, keys):
        out = {}
        for k in keys:
            v = base.get(k)
            out[k] = ("c", v) if v is not None else ("s", k)
        return out

    res_i = ari_from_labels(restrict(la, inter), restrict(lb, inter))
    res_u = ari_from_labels(restrict(la, union), restrict(lb, union))
    res_c = ari_from_labels(restrict(la, universe), restrict(lb, universe))
    return res_i, res_u, res_c, len(inter), len(union)


# --------------------------------------------------------------------------
# self-test
# --------------------------------------------------------------------------

def self_test():
    """Pin the adjusted Rand index against hand-computed values; False on any miss.

    For the partitions A and B below the contingency table has cell counts
    2, 1, 2, 1, 3, so index = 5, the marginal pair sums are 9 and 10 over
    C(9,2) = 36 pairs, expected = 2.5, maximum = 9.5, and the adjusted Rand
    index is 2.5 / 7.
    """
    a = [{0, 1, 2}, {3, 4, 5}, {6, 7, 8}]
    b = [{0, 1}, {2, 3, 4}, {5, 6, 7, 8}]

    ari, n, idx, exp, mx = ari_from_labels(flatten(a), flatten(b))
    want = 2.5 / 7
    ok1 = abs(ari - want) < 1e-12 and n == 9 and idx == 5 and abs(exp - 2.5) < 1e-12 and mx == 9.5
    print(f"  self-test A vs B: ARI={ari:.9f} (want {want:.9f}), "
          f"index={idx} expected={exp} max={mx} -> {'PASS' if ok1 else 'FAIL'}")

    ari2, _, _, _, _ = ari_from_labels(flatten(a), flatten([set(c) for c in a]))
    ok2 = abs(ari2 - 1.0) < 1e-12
    print(f"  self-test identical: ARI={ari2:.9f} (want 1.0) -> {'PASS' if ok2 else 'FAIL'}")

    # A labeling against a random relabeling of the same items should sit near
    # 0, not near 1.
    rng = random.Random(7)
    items = list(range(300))
    l1 = {i: i // 3 for i in items}
    shuf = items[:]
    rng.shuffle(shuf)
    l2 = {v: i // 3 for i, v in enumerate(shuf)}
    ari3, _, _, _, _ = ari_from_labels(l1, l2)
    ok3 = abs(ari3) < 0.05
    print(f"  self-test random relabeling: ARI={ari3:.6f} (want ~0) -> {'PASS' if ok3 else 'FAIL'}")

    return ok1 and ok2 and ok3


# --------------------------------------------------------------------------
# corpus pass
# --------------------------------------------------------------------------

def build_signatures():
    """One read/tokenize pass over the scan's `file_index`; five MinHash signatures per file.

    Returns the signatures keyed by seed and then by file-index position, and a
    tally of how each entry resolved: `ok`, `missing` (no file at that path
    under LIBRARIAN_CORPUS), `error` (read failed), `short` (under MIN_CHARS),
    or `empty` (no shingles). Only `ok` files receive signatures.
    """
    with open(SCAN, encoding="utf-8") as fh:
        scan = json.load(fh)
    index = scan["file_index"]
    print(f"file_index entries: {len(index)}")

    sigs = {s: {} for s in SEEDS}
    tally = defaultdict(int)

    for i, entry in enumerate(index):
        path = os.path.join(CORPUS, entry["marketplace"], entry["path"])
        if not os.path.exists(path):
            tally["missing"] += 1
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            tally["error"] += 1
            print(f"  read failed at {i}: {exc!r}", file=sys.stderr)
            continue
        if len(text) < MIN_CHARS:
            tally["short"] += 1
            continue
        shingles = tokenize(text)
        if not shingles:
            tally["empty"] += 1
            continue
        encoded = [s.encode("utf-8") for s in shingles]
        for seed in SEEDS:
            m = MinHash(num_perm=NUM_PERM, seed=seed)
            for e in encoded:
                m.update(e)
            sigs[seed][i] = m
        tally["ok"] += 1
        if tally["ok"] % 5000 == 0:
            print(f"  hashed {tally['ok']} files...", flush=True)

    print(f"resolution tally: {dict(tally)}")
    return sigs, dict(tally)


def greedy_clusters(sigs, order):
    """Greedy first-match loop, as `librarian/cli.py` runs it; returns (clusters, lsh).

    Every signature is indexed, then files are visited in `order`; an unassigned
    file whose query returns more than one hit forms a cluster with all of its
    hits, and all of them are marked assigned. The LSH index is returned so the
    order permutation can requery it without rebuilding.
    """
    lsh = MinHashLSH(threshold=THRESHOLD, num_perm=NUM_PERM)
    for i, m in sigs.items():
        lsh.insert(str(i), m)
    assigned = set()
    clusters = []
    for i in order:
        if i in assigned:
            continue
        hits = frozenset(int(r) for r in lsh.query(sigs[i]))
        if len(hits) > 1:
            clusters.append(hits)
            assigned.update(hits)
    return clusters, lsh


def greedy_with_lsh(lsh, sigs, order):
    """The same greedy loop over an already-built LSH index and a new visiting order."""
    assigned = set()
    clusters = []
    for i in order:
        if i in assigned:
            continue
        hits = frozenset(int(r) for r in lsh.query(sigs[i]))
        if len(hits) > 1:
            clusters.append(hits)
            assigned.update(hits)
    return clusters


def dump(clusters, name):
    """Write one labeling as a JSON list of sorted member lists beside this script."""
    p = os.path.join(OUTDIR, name)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump([sorted(c) for c in clusters], fh)
    return p


def main():
    print("Self-test:")
    if not self_test():
        print("SELF-TEST FAILED", file=sys.stderr)
        return 1

    print("\nBuilding signatures for all five seeds (one read/tokenize pass)...")
    sigs, tally = build_signatures()
    universe = set(sigs[SEEDS[0]])
    print(f"universe (files with signatures): {len(universe)}")

    per_seed = {}
    lshes = {}
    for seed in SEEDS:
        order = sorted(sigs[seed])
        clusters, lsh = greedy_clusters(sigs[seed], order)
        lshes[seed] = lsh
        per_seed[seed] = clusters
        slots = sum(len(c) for c in clusters)
        distinct = len({x for c in clusters for x in c})
        print(f"seed {seed}: clusters={len(clusters)} memberships={slots} distinct={distinct}")
        dump(clusters, f"clusterings{SUFFIX}-{seed}.json")

    seed_rows = []
    for a_i, s1 in enumerate(SEEDS):
        for s2 in SEEDS[a_i + 1:]:
            (ri_, ru_, rc_, n_i, n_u) = three_populations(per_seed[s1], per_seed[s2], universe)
            seed_rows.append({
                "pair": f"{s1} vs {s2}",
                "n_inter": n_i, "n_union": n_u, "n_corpus": len(universe),
                "ari_inter": ri_[0], "ari_union": ru_[0], "ari_corpus": rc_[0],
            })
            print(f"  {s1} vs {s2}: inter n={n_i} ARI={ri_[0]:.4f} | "
                  f"union n={n_u} ARI={ru_[0]:.4f} | corpus ARI={rc_[0]:.4f}", flush=True)

    # ---- order permutation on the seed-1 signatures (seed 1 is the datasketch default)
    print("\nOrder permutation on default-seed signatures...")
    dsigs = sigs[1]
    dlsh = lshes[1]
    keys = sorted(dsigs)
    # The baseline is the sorted-order greedy run on the seed-1 signatures, which
    # is the seed-1 clustering computed above and matches the archived scan.
    base = per_seed[1]
    dump(base, f"clusterings{SUFFIX}-order-baseline.json")
    order_rows = []
    for k, ss in enumerate(SHUFFLE_SEEDS):
        rng = random.Random(ss)
        order = keys[:]
        rng.shuffle(order)
        cl = greedy_with_lsh(dlsh, dsigs, order)
        dump(cl, f"clusterings{SUFFIX}-order-{k}.json")
        (ri_, ru_, rc_, n_i, n_u) = three_populations(base, cl, universe)
        order_rows.append({
            "shuffle": k, "seed": ss, "clusters": len(cl),
            "n_inter": n_i, "n_union": n_u,
            "ari_inter": ri_[0], "ari_union": ru_[0], "ari_corpus": rc_[0],
        })
        print(f"  shuffle {k} (rng {ss}): clusters={len(cl)} inter n={n_i} ARI={ri_[0]:.4f} | "
              f"union n={n_u} ARI={ru_[0]:.4f} | corpus ARI={rc_[0]:.4f}", flush=True)

    summary = {
        "tally": tally,
        "universe": len(universe),
        "per_seed": {str(s): {"clusters": len(per_seed[s]),
                              "memberships": sum(len(c) for c in per_seed[s]),
                              "distinct": len({x for c in per_seed[s] for x in c})}
                     for s in SEEDS},
        "seed_rows": seed_rows,
        "order_rows": order_rows,
    }
    with open(os.path.join(OUTDIR, f"recompute-ari-results{SUFFIX}.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nWrote recompute-ari-results{SUFFIX}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
