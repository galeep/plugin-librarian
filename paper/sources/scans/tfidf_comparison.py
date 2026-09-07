#!/usr/bin/env python3
"""TF-IDF cosine-similarity baseline against the MinHash clustering.

Supports the TF-IDF paragraph of Section 5.2, Comparison with Simple Baselines
("TF-IDF produced 3,170 clusters covering 9,208 files (29.1%), with comparable
recall (99.7%) but substantially lower precision"), and the TF-IDF bars of Figure 3
("Similarity method comparison on 31,634 SKILL.md files"). The script vectorises
each file, clusters greedily at 0.9 cosine similarity in batches, and scores
precision and recall against the IOC account list under the definitions of
Section 5.2. Sparse matrix operations throughout, so there is no O(n^2) per-file
pass.

Inputs. LIBRARIAN_CORPUS (required) names the pinned corpus snapshot; see
paper/supplementary/repository-commits.md. The file list is the `file_index` of
`scan_20260314_threshold90_skillonly.json`, beside this script, resolved through
`order_permutation.load_files` so this run and the order-permutation run see the same
files. Ground truth comes from `paper/iocs.json`. Parameters: 0.9 threshold,
100-character minimum, batch size 1000.

Decoding is selectable and it moves the totals. Eight indexed files are not valid
UTF-8. `--decode strict` skips and lists them, clustering 31,626 documents, which is
the population behind the Section 5.2 figures. `--decode replace`, the default,
substitutes U+FFFD and keeps all 31,634, giving 9,212 files in clusters rather than
9,208. Everything else matches under either mode.

Output: `tfidf-comparison-<UTC date>.md` beside this script, or the full path in
SCAN_RESULTS_OUT. A second run on the same UTC day overwrites the day's file.

To reproduce the Section 5.2 numbers, with LIBRARIAN_CORPUS set:
  python paper/sources/scans/tfidf_comparison.py --decode strict
"""

import argparse
import datetime
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))              # sibling scan scripts
sys.path.insert(0, str(HERE.parents[2]))   # repository root

import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

# Reused rather than reimplemented so this script and the order-permutation run
# resolve the same file list from the same snapshot and describe it the same way.
from order_permutation import git_head, load_files, provenance, require_corpus
# Only for the equivalence check in check_attribution_rule(); the rule this
# script scores with is get_author() below.
from file_level_precision import account_of

CORPUS = Path(require_corpus())
SCAN = HERE / "scan_20260314_threshold90_skillonly.json"
IOCS = HERE.parents[1] / "iocs.json"
# DESIGN RATIONALE: a fixed output name would let any rerun clobber a tracked
# results file. The default carries today's UTC date; SCAN_RESULTS_OUT (a full
# path) overrides it.
_DEFAULT_OUT_NAME = "tfidf-comparison-{}.md".format(
    datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d"))
OUT = Path(os.environ["SCAN_RESULTS_OUT"]) if os.environ.get("SCAN_RESULTS_OUT") \
    else HERE / _DEFAULT_OUT_NAME

THRESHOLD = 0.9
MIN_CHARS = 100          # files shorter than this are skipped
BATCH_SIZE = 1000
# Census bands around THRESHOLD, counted but never acted on. A pair inside a band
# is one whose membership of a cluster would flip under a small change in the
# feature set, which is the population any difference against the paper's figures
# has to come out of. Reported so "a handful of borderline pairs" is a measured
# claim rather than an assertion. DESIGN RATIONALE for collecting pairs in a set
# rather than incrementing a counter: a pair (i, j) is reachable from row i and
# again from row j, so a counter double-counts every pair whose two endpoints
# are both visited as unassigned seeds and reports up to twice the true figure.
# The bands hold a few thousand pairs, so the set costs nothing.
CENSUS_BANDS = ((0.895, 0.905), (0.88, 0.92))

# Figure 3's caption ("Wall-clock runtime (8-core i9-9880H)") and the Conclusion
# ("on a single workstation (Intel i9-9880H, 64 GB RAM)") give the paper's bench
# as an 8-core Intel i9-9880H with 64 GB. Recorded here so a rerun states whether
# it is the same machine instead of leaving the runtime comparison to a reader's
# assumption.
PAPER_MACHINE = ('Intel i9-9880H, 8 cores, 64 GB (Figure 3 caption and the '
                 'Conclusion; the caption reads "Wall-clock runtime (8-core i9-9880H)")')

# The 11 accounts the Section 5.2 figures were computed with. Kept as a literal
# ONLY so the set read out of iocs.json can be checked against it; the run uses
# the iocs.json set.
PAPER_MALICIOUS_AUTHORS = frozenset({
    "hightower6eu", "sakaen736jih", "thiagoruss0", "zaycv",
    "jordanprater", "stveenli", "anisafifi", "timclawbot",
    "kenblive", "mupengi-bot", "moonshine-100rze",
})

# Section 5.2 ("TF-IDF produced 3,170 clusters covering 9,208 files (29.1%)")
# and the hardcoded TF-IDF bars of figures/generate_figures.py (the `p_at_20`,
# `p_at_10` and `runtime` lists of `fig_method_comparison`), checked row by row
# below.
PAPER = {
    "clusters": 3170,
    "files_in_clusters": 9208,
    "rate_pct": 29.1,
    "recall_pct": 99.7,
    "p20_pct": 75.0, "p20_tp": 15, "p20_n": 20,
    "p10_pct": 41.1, "p10_tp": 30, "p10_n": 73,
    "runtime_s": 465,
}
# The MinHash column of the same paragraph, for the side-by-side print. Cluster
# and file counts come from the archived scan's own summary; the rest is quoted.
MINHASH_RECALL_PCT = 99.2
MINHASH_P20_PCT = 100.0
MINHASH_P10_PCT = 78.9
MINHASH_RUNTIME_S = 305

# The companion run in the other decode mode, so each results file can point at
# the other instead of leaving a reader to guess why two file counts exist.
# Recorded rather than recomputed: naming it costs one line, reproducing it costs
# a run.
RECORDED_RUNS = {
    "replace": {"date": "2026-09-07", "clusters": 3170, "files": 9212, "docs": 31634},
    "strict": {"date": "2026-09-07", "clusters": 3170, "files": 9208, "docs": 31626},
}


def machine() -> str:
    """CPU, core count and memory of the machine this run used, best effort.

    DESIGN RATIONALE: the only paper number this script cannot score as match or
    no-match is the 465 s runtime, because a wall-clock figure means nothing
    without the hardware and the load it was measured under. Both are recorded
    rather than described in prose. A probe that fails degrades to "unknown"
    for that field: an unreadable sysctl is a missing provenance field, not a
    reason to abandon the run.
    """
    def sysctl(key):
        try:
            r = subprocess.run(["sysctl", "-n", key], capture_output=True,
                               text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None
        return r.stdout.strip() or None if r.returncode == 0 else None

    cpu = sysctl("machdep.cpu.brand_string") or platform.processor() or "unknown CPU"
    cores = sysctl("hw.ncpu") or str(os.cpu_count() or "unknown")
    mem = sysctl("hw.memsize")
    mem = f"{int(mem) / 1024**3:.0f} GB" if mem and mem.isdigit() else "unknown RAM"
    return f"{cpu}, {cores} logical CPUs, {mem}"


def load_average() -> str:
    """1/5/15-minute load average, or a reason string."""
    try:
        return ", ".join(f"{v:.2f}" for v in os.getloadavg())
    except (OSError, AttributeError):
        return "unavailable"


def get_author(marketplace, path):
    """Account owning a file, or None."""
    parts = path.split("/")
    if marketplace == "clawhub-archive" and parts[0] == "skills" and len(parts) >= 3:
        return parts[1]
    return None


def load_malicious_authors():
    """The ground-truth account set, read out of paper/iocs.json.

    The rule is `set(iocs["clawhub_authors"])`: the 11 ClawHub accounts this
    study confirmed by payload inspection. That is neither of the two rules
    file_level_precision.py reports (the Antiy CERT 12, "strict", or their
    18-account union, "study"), so account_of's ground truth is deliberately
    NOT imported. The Section 5.2 precision figures were computed with this
    set, so changing it here would change what is being reproduced. The
    equality check below pins that: iocs.json is the source, and the literal is
    kept only to prove the source agrees with it.
    """
    iocs = json.loads(IOCS.read_text())
    authors = frozenset(iocs["clawhub_authors"])
    if authors != PAPER_MALICIOUS_AUTHORS:
        raise ValueError(
            "iocs.json clawhub_authors does not match the account set the Section 5.2 "
            f"figures were computed with; only in iocs.json: "
            f"{sorted(authors - PAPER_MALICIOUS_AUTHORS)}; only in the literal: "
            f"{sorted(PAPER_MALICIOUS_AUTHORS - authors)}")
    return authors


def check_attribution_rule(entries):
    """Confirm get_author agrees with file_level_precision.account_of on this scan.

    The two differ as functions: get_author takes a ClawHub path of three or
    more segments, account_of requires four. Reported rather than silently
    assumed, because a reader comparing this file's precision figures against
    file-level-precision-*.md needs to know whether the attribution rule is the
    same one. Returns (agree, disagreements).
    """
    bad = [e for e in entries
           if get_author(e["marketplace"], e["path"]) != account_of(e)]
    return not bad, bad


def build_matrix(texts):
    """TF-IDF matrix with the Section 5.2 settings (50,000 features, 1-3-grams,
    sublinear TF), L2-normalised so dot == cosine."""
    vectorizer = TfidfVectorizer(
        max_features=50000,
        ngram_range=(1, 3),
        min_df=2,
        max_df=0.95,
        sublinear_tf=True,
    )
    return normalize(vectorizer.fit_transform(texts), norm="l2"), vectorizer


def load_corpus(scan, decode):
    """File texts and metadata for the archived scan's file_index, from CORPUS.

    Path resolution mirrors order_permutation.signatures: only
    <marketplace>/<relative> is a real corpus path, and a miss stays a miss
    rather than falling back to CORPUS/<relative>, which can resolve a different
    marketplace's file.

    `decode` is "strict" or "replace". DESIGN RATIONALE: this is the one place
    where a choice silently changes the document set rather than the inputs.
    Eight file_index entries are not valid UTF-8. "strict" skips and lists them,
    vectorising 31,626 documents, which is the population behind the Section 5.2
    figures; "replace" keeps all 31,634 by substituting U+FFFD.
    The skipped paths are returned rather than only counted, because which files
    left the corpus is the whole point of offering the choice.
    """
    entries = scan["file_index"]
    pairs = load_files(scan)
    texts, metadata = [], []
    skipped = {"missing": 0, "short": 0, "undecodable": 0}
    dropped = {"missing": [], "short": [], "undecodable": []}

    def drop(reason, market, rel):
        skipped[reason] += 1
        dropped[reason].append(f"{market}/{rel}")

    for entry, (market, rel) in zip(entries, pairs):
        p = CORPUS / market / rel
        try:
            text = p.read_text(encoding="utf-8") if decode == "strict" \
                else p.read_text(encoding="utf-8", errors="replace")
        except UnicodeDecodeError:
            # Only reachable under --decode strict; "replace" cannot raise it.
            drop("undecodable", market, rel)
            continue
        except OSError:
            drop("missing", market, rel)
            continue
        if len(text) < MIN_CHARS:
            drop("short", market, rel)
            continue
        texts.append(text)
        metadata.append(entry)
    print(f"Loaded {len(texts)} files (decode={decode}; {skipped['missing']} missing, "
          f"{skipped['undecodable']} not valid UTF-8, {skipped['short']} under "
          f"{MIN_CHARS} characters)", flush=True)
    return texts, metadata, skipped, dropped


def cluster_tfidf_batched(texts, threshold):
    """Cluster using TF-IDF with batched sparse cosine similarity.

    Greedy first-match, as in Section 5.2 ("the same greedy first-match
    algorithm"). Timing is split three ways: vectorising, the sparse similarity
    products, and the thresholding and assignment loop.
    """
    print("Building TF-IDF matrix...", flush=True)
    t0 = time.time()
    tfidf_matrix, _ = build_matrix(texts)
    t_vec = time.time() - t0
    print(f"TF-IDF matrix: {tfidf_matrix.shape} in {t_vec:.1f}s", flush=True)

    print("Computing cosine similarity (batched sparse)...", flush=True)
    n = tfidf_matrix.shape[0]
    assigned = set()
    clusters = []
    census = [set() for _ in CENSUS_BANDS]
    t_sim = t_clu = 0.0

    for start in range(0, n, BATCH_SIZE):
        end = min(start + BATCH_SIZE, n)
        if start % 5000 == 0:
            print(f"  Batch {start}-{end} of {n} ({len(clusters)} clusters so far)...",
                  flush=True)

        ts = time.time()
        batch_sim = tfidf_matrix[start:end] @ tfidf_matrix.T
        t_sim += time.time() - ts

        tc = time.time()
        for local_i in range(end - start):
            global_i = start + local_i
            if global_i in assigned:
                continue

            row = batch_sim.getrow(local_i)
            indices = row.indices
            values = row.data

            matches = set()
            for idx, val in zip(indices, values):
                if idx != global_i and idx not in assigned and val >= threshold:
                    matches.add(idx)
                # Census only. This branch reads `val` and writes `census`; it
                # cannot reach `matches`, so the clustering is unchanged.
                if idx != global_i:
                    for b, (lo, hi) in enumerate(CENSUS_BANDS):
                        if lo <= val < hi:
                            census[b].add((min(global_i, idx), max(global_i, idx)))

            if matches:
                cluster = frozenset({global_i} | matches)
                clusters.append(cluster)
                assigned.update(cluster)
        t_clu += time.time() - tc

    timings = {"vectorise": t_vec, "similarity": t_sim, "cluster": t_clu,
               "total": t_vec + t_sim + t_clu}
    census = [len(pairs) for pairs in census]
    print(f"Clustering done: {len(clusters)} clusters in {timings['total']:.1f}s "
          f"(near-threshold census, distinct pairs: {census})", flush=True)
    return clusters, timings, census


def evaluate_clusters(clusters, metadata, malicious):
    """Cluster-level precision by size and hightower6eu recall, as in Section 5.2.

    Precision at size s: of the clusters with at least s files, the share holding
    at least one file whose ClawHub account is in `malicious`. Recall: the share
    of hightower6eu files that landed in any cluster.
    """
    size_thresholds = [5, 10, 15, 20]
    results = {}

    for min_size in size_thresholds:
        large_clusters = [c for c in clusters if len(c) >= min_size]
        if not large_clusters:
            results[min_size] = {"precision": None, "count": 0, "malicious": 0}
            continue

        mal_count = 0
        for cluster in large_clusters:
            is_mal = False
            for idx in cluster:
                fi = metadata[idx]
                author = get_author(fi["marketplace"], fi["path"])
                if author and author in malicious:
                    is_mal = True
                    break
            if is_mal:
                mal_count += 1

        results[min_size] = {
            "precision": mal_count / len(large_clusters) * 100,
            "count": len(large_clusters),
            "malicious": mal_count,
        }

    clustered_indices = set()
    for c in clusters:
        clustered_indices.update(c)

    h6_total = 0
    h6_in_cluster = 0
    for i, fi in enumerate(metadata):
        author = get_author(fi["marketplace"], fi["path"])
        if author == "hightower6eu":
            h6_total += 1
            if i in clustered_indices:
                h6_in_cluster += 1

    recall = h6_in_cluster / h6_total * 100 if h6_total else 0
    return results, recall, h6_in_cluster, h6_total


# --- self-test -------------------------------------------------------------

# Three documents built from three shared blocks, so that under the vectoriser
# above every surviving feature has document frequency exactly 2. max_df=0.95
# over three documents drops any feature present in all three (cutoff 2.85), and
# min_df=2 drops any feature present in one, so a block shared by exactly two
# documents survives whole: its L unigrams, L-1 bigrams and L-2 trigrams, i.e.
# 3L-3 features. Block lengths 6 / 3 / 2 give feature counts 15 / 6 / 3.
# Cross-block n-grams sit in one document only and drop out, as does the unique
# tail token of each document.
_ST_D12 = "alpha bravo charlie delta echo foxtrot"   # in documents 1 and 2 -> 15 features
_ST_D13 = "golf hotel india"                         # in documents 1 and 3 ->  6 features
_ST_D23 = "juliett kilo"                             # in documents 2 and 3 ->  3 features
SELF_TEST_DOCS = [
    f"{_ST_D12} {_ST_D13} lima",
    f"{_ST_D12} {_ST_D23} mike",
    f"{_ST_D13} {_ST_D23} november",
]
# Every feature occurs once in its document, so sublinear TF leaves tf = 1, and
# every feature has df = 2, so all idf weights are equal. A document's vector is
# therefore a flat vector over the features of the two blocks it holds, and
# cos(i,j) = shared / sqrt(|i| * |j|) with |1| = 21, |2| = 18, |3| = 9:
#   cos(1,2) = 15 / sqrt(21*18) = 0.771517...
#   cos(1,3) =  6 / sqrt(21* 9) = 0.436436...
#   cos(2,3) =  3 / sqrt(18* 9) = 0.235702...
SELF_TEST_FEATURES = 15 + 6 + 3
SELF_TEST_EXPECTED = {
    (0, 1): 15 / math.sqrt(21 * 18),
    (0, 2): 6 / math.sqrt(21 * 9),
    (1, 2): 3 / math.sqrt(18 * 9),
}


def self_test() -> int:
    """Check the vectoriser against three documents with hand-computed cosines.

    DESIGN RATIONALE: every number this script reports depends on the vectoriser
    settings and on dot-product-equals-cosine holding after normalisation. A
    silently changed default (sklearn's max_df/min_df semantics, or the
    normalisation dropping out) would move every figure without any visible
    error, so the settings are pinned by a test that fails the script. The
    expected values are derived in the comment above and written out, not
    recomputed from the code under test.
    """
    matrix, vectorizer = build_matrix(SELF_TEST_DOCS)
    n_features = matrix.shape[1]
    if n_features != SELF_TEST_FEATURES:
        print(f"self-test FAILED: expected {SELF_TEST_FEATURES} features under "
              f"min_df=2/max_df=0.95 over 3 documents, got {n_features}: "
              f"{sorted(vectorizer.vocabulary_)}", file=sys.stderr)
        return 1
    sim = (matrix @ matrix.T).toarray()
    for (i, j), expected in sorted(SELF_TEST_EXPECTED.items()):
        if not math.isclose(sim[i][j], expected, rel_tol=1e-9):
            print(f"self-test FAILED: cos(d{i+1},d{j+1}) expected {expected!r}, "
                  f"got {sim[i][j]!r}", file=sys.stderr)
            return 1
    # The ordering is the property the baseline rests on: more shared text must
    # score higher. Asserted separately from the values so a future change that
    # keeps three plausible numbers but inverts their order still fails.
    if not sim[0][1] > sim[0][2] > sim[1][2] > 0:
        print(f"self-test FAILED: expected cos(d1,d2) > cos(d1,d3) > cos(d2,d3) > 0, "
              f"got {sim[0][1]!r}, {sim[0][2]!r}, {sim[1][2]!r}", file=sys.stderr)
        return 1
    # Self-similarity is 1 after L2 normalisation; if it is not, the dot product
    # is not a cosine and every threshold comparison below is meaningless.
    for i in range(3):
        if not math.isclose(sim[i][i], 1.0, rel_tol=1e-9):
            print(f"self-test FAILED: cos(d{i+1},d{i+1}) = {sim[i][i]!r}, not 1.0; "
                  "rows are not L2-normalised", file=sys.stderr)
            return 1
    # None of the three pairs reaches the clustering threshold, so a run over
    # these documents produces no cluster at all.
    if any(sim[i][j] >= THRESHOLD for i, j in SELF_TEST_EXPECTED):
        print(f"self-test FAILED: a self-test pair reached the {THRESHOLD} "
              "clustering threshold", file=sys.stderr)
        return 1
    return 0


# --- reporting -------------------------------------------------------------

def mode_note(decode, n_texts, n_index):
    """The paragraph naming which decode mode produced this file, and the other's numbers.

    DESIGN RATIONALE: the two modes differ by four numbers out of eight and by
    eight documents out of 31,634, which is exactly the size of difference a
    reader skims past. Each results file therefore says which mode it is, what
    the other mode gave, and which of the two reproduces the paper.
    """
    other = "replace" if decode == "strict" else "strict"
    o = RECORDED_RUNS[other]
    if decode == "strict":
        head = (f"**This is the `--decode strict` run, and it reproduces the paper's "
                f"configuration.** Files that are not valid UTF-8 are not part of the "
                f"population behind the Section 5.2 figures, so this run vectorises "
                f"{n_texts:,} documents rather than the {n_index:,} the scan indexes; "
                f"the eight excluded files are listed under Provenance below.")
        tail = (f"A `--decode replace` run of {o['date']} over all {o['docs']:,} "
                f"documents gave {o['clusters']:,} clusters over {o['files']:,} files, "
                f"with identical precision and recall. "
                f"**The script's default mode is `replace`**, so a rerun "
                f"without `--decode strict` reproduces {o['files']:,} files in clusters, "
                f"not the paper's {PAPER['files_in_clusters']:,}.")
    else:
        head = (f"**This is the `--decode replace` run, the script's default.** It keeps "
                f"every one of the {n_texts:,} indexed files by substituting U+FFFD for "
                f"undecodable bytes, which is not the population behind the published figures.")
        tail = (f"The `--decode strict` run of {o['date']} reproduces the paper's "
                f"configuration by skipping the eight files that are not valid UTF-8, "
                f"over {o['docs']:,} documents, and gives {o['clusters']:,} clusters "
                f"over {o['files']:,} files, matching the paper exactly. "
                f"**Use `--decode strict` to reproduce Section 5.2.**")
    return [head, "", tail, ""]


def fmt_pct(v):
    return "N/A" if v is None else f"{v:.1f}%"


def comparison_rows(clusters, metadata, texts, timings, precision, recall,
                    h6_found, h6_total):
    """(label, paper value, this run's value, match) for every Section 5.2 number."""
    n = len(texts)
    memberships = sum(len(c) for c in clusters)
    distinct = len({i for c in clusters for i in c})
    p20 = precision.get(20, {})
    p10 = precision.get(10, {})

    def match(a, b):
        return "yes" if a == b else "**NO**"

    rows = [
        ("clusters", f"{PAPER['clusters']:,}", f"{len(clusters):,}",
         match(PAPER["clusters"], len(clusters))),
        ("files in clusters (memberships)", f"{PAPER['files_in_clusters']:,}",
         f"{memberships:,}", match(PAPER["files_in_clusters"], memberships)),
        ("files in clusters (distinct)", "not stated separately", f"{distinct:,}",
         "n/a"),
        ("share of files clustered", f"{PAPER['rate_pct']:.1f}%",
         f"{memberships / n * 100:.1f}%",
         match(PAPER["rate_pct"], round(memberships / n * 100, 1))),
        ("recall (hightower6eu)", f"{PAPER['recall_pct']:.1f}%",
         f"{recall:.1f}% ({h6_found}/{h6_total})",
         match(PAPER["recall_pct"], round(recall, 1))),
        ("P@>=20", f"{PAPER['p20_pct']:.1f}% ({PAPER['p20_tp']}/{PAPER['p20_n']})",
         f"{fmt_pct(p20.get('precision'))} ({p20.get('malicious')}/{p20.get('count')})",
         match((PAPER["p20_tp"], PAPER["p20_n"]),
               (p20.get("malicious"), p20.get("count")))),
        ("P@>=10", f"{PAPER['p10_pct']:.1f}% ({PAPER['p10_tp']}/{PAPER['p10_n']})",
         f"{fmt_pct(p10.get('precision'))} ({p10.get('malicious')}/{p10.get('count')})",
         match((PAPER["p10_tp"], PAPER["p10_n"]),
               (p10.get("malicious"), p10.get("count")))),
        ("runtime (wall)", f"{PAPER['runtime_s']} s", f"{timings['total']:.0f} s",
         "n/a"),
    ]
    return rows, memberships, distinct


def build_report(scan, texts, metadata, skipped, dropped, clusters, timings,
                 precision, recall, h6_found, h6_total, malicious, rule_agrees,
                 rule_bad, census, decode):
    rows, memberships, distinct = comparison_rows(
        clusters, metadata, texts, timings, precision, recall, h6_found, h6_total)
    n = len(texts)
    this_machine = machine()
    # The flag is always printed, including for the default, so a copied command
    # cannot silently reproduce the other mode's file count.
    command = (f"python paper/sources/scans/{Path(__file__).name} "
               f"--decode {decode}")

    lines = [
        "# TF-IDF cosine-similarity baseline (0.9 cosine, SKILL.md only)", "",
        "This file reports the TF-IDF baseline of Section 5.2, Comparison with Simple "
        'Baselines: "TF-IDF produced 3,170 clusters covering 9,208 files (29.1%), with '
        "comparable recall (99.7%) but substantially lower precision: P@≥20 dropped "
        "to 75.0% (15/20) and P@≥10 to 41.1% (30/73), compared to MinHash's 100% "
        '(P@≥20) and 78.9% (P@≥10). Runtime was 465 s versus 305 s for MinHash '
        '(both wall time)." It also supports the TF-IDF bars of Figure 3 ("Similarity '
        'method comparison on 31,634 SKILL.md files").', "",
        f"Generated by `{Path(__file__).name}`; rerun with `{command}` from the "
        "repository root with `LIBRARIAN_CORPUS` set. Output defaults to today's UTC "
        "date; set `SCAN_RESULTS_OUT` to a full path to write elsewhere.",
        f"Input file list: `{SCAN.name}` `file_index`. File contents: the corpus "
        "root below. Ground truth: `paper/iocs.json` `clawhub_authors`.", "",
    ] + mode_note(decode, len(texts), len(scan["file_index"])) + [
        "## Provenance", "",
    ]
    lines += provenance(scan)
    lines += [
        "| item | value |", "|---|---|",
        f"| Python | {sys.version.split()[0]} |",
        f"| scikit-learn | {sklearn.__version__} |",
        f"| machine | {this_machine} |",
        f"| March bench (paper) | {PAPER_MACHINE} |",
        f"| load average at finish (1/5/15 min) | {load_average()} |",
        f"| paper repository HEAD | {git_head(HERE.parents[2])} |",
        f"| command | `{command}` |",
        f"| run finished (UTC) | {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')} |",
        f"| vectorise | {timings['vectorise']:.1f} s |",
        f"| sparse similarity products | {timings['similarity']:.1f} s |",
        f"| threshold and greedy assignment | {timings['cluster']:.1f} s |",
        f"| **total** | **{timings['total']:.1f} s** |",
        "",
        "The paper does not record the scikit-learn version behind its TF-IDF "
        "figures, and `pyproject.toml` does not list scikit-learn as a dependency. "
        "The version above is the one this run used, so a TF-IDF difference "
        "attributable to a library change cannot be bounded from this repository.", "",
        f"Files: {len(texts)} of {len(scan['file_index'])} scan entries loaded with "
        f"`--decode {decode}`; {skipped['missing']} could not be read from the "
        f"corpus, {skipped['undecodable']} are not valid UTF-8, and "
        f"{skipped['short']} were shorter than {MIN_CHARS} characters.",
        "",
        "Decoding is the one input that changes the document set silently. Under "
        "`--decode strict`, files that are not valid UTF-8 never enter the document "
        "set, which is the population behind the Section 5.2 figures; `--decode "
        "replace` keeps them by substituting U+FFFD. Files dropped as undecodable "
        + (f"({skipped['undecodable']}):" if skipped["undecodable"] else
           "under this mode: none.")]
    if dropped["undecodable"]:
        lines += [""] + [f"- `{q}`" for q in dropped["undecodable"]]
    lines += [
        "",
        f"Ground truth: the {len(malicious)} accounts in `iocs.json` "
        "`clawhub_authors`, checked at startup against the account set the Section "
        "5.2 figures were computed with. A cluster counts as a true positive if at least "
        "one of its files sits under one of those accounts in the ClawHub archive "
        "(`skills/<account>/...`). Recall is the share of `hightower6eu` files "
        "that landed in any cluster; it is not corpus-wide recall.",
        "",
    ]
    if rule_agrees:
        lines += [
            "The attribution rule here (`get_author`) takes a ClawHub path of three "
            "or more segments; `file_level_precision.account_of` requires four. On "
            "this scan the two agree on all "
            f"{len(scan['file_index'])} entries, so the precision figures below are "
            "comparable with `file-level-precision-*.md` under its `clawhub_authors` "
            "candidate row.", ""]
    else:
        lines += [
            f"**The attribution rule here disagrees with `file_level_precision.account_of` "
            f"on {len(rule_bad)} of {len(scan['file_index'])} entries**, so the precision "
            "figures below are not directly comparable with `file-level-precision-*.md`. "
            f"First disagreements: {[e['path'] for e in rule_bad[:5]]}.", ""]

    lines += [
        "## Against the Section 5.2 numbers", "",
        'Paper source: Section 5.2 ("TF-IDF produced 3,170 clusters covering 9,208 '
        'files (29.1%)"), and the hardcoded TF-IDF bars in '
        "`paper/figures/generate_figures.py`, the `p_at_20`, `p_at_10` and `runtime` "
        "lists of `fig_method_comparison`.", "",
        "| quantity | paper | this run | match |", "|:--|--:|--:|:--|",
    ]
    lines += [f"| {label} | {paper} | {got} | {ok} |" for label, paper, got, ok in rows]
    lines += [
        "",
        "The clustering loop never adds an already-assigned file to a second "
        f"cluster, so memberships and distinct files are equal by construction "
        f"({memberships:,} either way). "
        + (f"The paper's {PAPER['files_in_clusters']:,} therefore matches both "
           "readings."
           if memberships == PAPER["files_in_clusters"] else
           f"The paper's {PAPER['files_in_clusters']:,} matches NEITHER reading "
           f"of this run, which differs by {memberships - PAPER['files_in_clusters']:+,} "
           f"({(memberships - PAPER['files_in_clusters']) / PAPER['files_in_clusters'] * 100:+.3f}%); "
           "the two readings cannot be what separates them.")
        + f" The share is that count over the {n:,} files loaded.",
        "",
        "A row above that does not match has to be read against the scikit-learn "
        "version, which the paper does not record, and against the decode mode "
        "named at the top of this file; the decode mode is reproduced by "
        "`--decode strict`, the library version is not fixed by this repository.",
        "",
        "Near-threshold census, counting DISTINCT unordered pairs among those the "
        "greedy loop actually examined (a pair reachable from both of its endpoints "
        "is counted once): "
        + "; ".join(f"{census[b]:,} pairs with cosine in [{lo}, {hi})"
                    for b, (lo, hi) in enumerate(CENSUS_BANDS))
        + ". These are the pairs whose cluster membership would flip under a small "
        "change to the feature set, so they bound how much of a difference against "
        "the paper's figures a knife-edge effect can explain.",
        "",
        "Runtime carries no match verdict. "
        + ("The CPU is the same model the paper "
           f"benched on ({PAPER_MACHINE}), but this run ran at the load average "
           "recorded above, and the paper records no load for its figure."
           if "i9-9880H" in this_machine else
           f"This run's CPU ({this_machine}) is not the model the paper benched on "
           f"({PAPER_MACHINE}), so the wall-clock figures are not comparable.")
        + " The three-way "
        "split is recorded so a rerun on an unloaded machine can compare like with "
        "like.",
        "",
        "## Full precision profile", "",
        "| minimum cluster size | clusters | with a malicious file | precision |",
        "|--:|--:|--:|--:|",
    ]
    for size in sorted(precision):
        p = precision[size]
        lines.append(f"| >= {size} | {p['count']} | {p['malicious']} | "
                     f"{fmt_pct(p['precision'])} |")

    summary = scan.get("summary", {})
    mh_clusters = summary.get("unique_clusters")
    mh_files = summary.get("files_in_clusters")
    mh_total = summary.get("total_files_scanned")
    lines += [
        "", "## Side by side with MinHash", "",
        "MinHash cluster and file counts are the archived scan's own `summary`; its "
        "recall, precision and runtime are quoted from Section 5.2.", "",
        "| method | clusters | files clustered | share | recall | P@>=20 | P@>=10 | runtime |",
        "|:--|--:|--:|--:|--:|--:|--:|--:|",
        f"| TF-IDF (0.9 cosine, this run) | {len(clusters):,} | {memberships:,} | "
        f"{memberships / n * 100:.1f}% | {recall:.1f}% | "
        f"{fmt_pct(precision.get(20, {}).get('precision'))} | "
        f"{fmt_pct(precision.get(10, {}).get('precision'))} | "
        f"{timings['total']:.0f} s |",
        f"| MinHash (0.9 Jaccard, archived scan) | {mh_clusters:,} | {mh_files:,} | "
        f"{mh_files / mh_total * 100:.1f}% | {MINHASH_RECALL_PCT:.1f}% | "
        f"{MINHASH_P20_PCT:.1f}% | {MINHASH_P10_PCT:.1f}% | {MINHASH_RUNTIME_S} s |",
        "",
    ]
    return lines


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--decode", choices=("strict", "replace"), default="replace",
        help="How to decode corpus files. 'replace' (default) substitutes U+FFFD "
             "for undecodable bytes and keeps every indexed file. 'strict' skips "
             "and lists files that are not valid UTF-8, clustering the 31,626 "
             "documents behind the Section 5.2 figures rather than 31,634.")
    return ap.parse_args(argv)


def main(args) -> int:
    scan = json.loads(SCAN.read_text())
    malicious = load_malicious_authors()
    rule_agrees, rule_bad = check_attribution_rule(scan["file_index"])
    if not rule_agrees:
        print(f"note: get_author and file_level_precision.account_of disagree on "
              f"{len(rule_bad)} entries; recorded in the results file", file=sys.stderr)

    texts, metadata, skipped, dropped = load_corpus(scan, args.decode)
    if not texts:
        print(f"no files loaded from {CORPUS}; the corpus root or the scan's "
              "file_index keys are wrong", file=sys.stderr)
        return 1
    # A path in the scan index that does not resolve means the corpus is not the
    # one the scan was built from, and every count below would then be computed
    # over a different document set while still looking well-formed. That is a
    # failed run, not a footnote, so it stops here. Undecodable files are NOT
    # covered by this ceiling: under --decode strict they are an expected,
    # enumerated part of reproducing the paper's document set.
    if skipped["missing"]:
        print(f"{skipped['missing']} indexed path(s) missing from {CORPUS}; the "
              f"corpus is not the one {SCAN.name} was built from. First few: "
              f"{dropped['missing'][:5]}", file=sys.stderr)
        return 1

    print(f"\n=== TF-IDF Cosine Similarity (threshold={THRESHOLD}) ===", flush=True)
    clusters, timings, census = cluster_tfidf_batched(texts, THRESHOLD)
    precision, recall, h6_found, h6_total = evaluate_clusters(
        clusters, metadata, malicious)

    lines = build_report(scan, texts, metadata, skipped, dropped, clusters, timings,
                         precision, recall, h6_found, h6_total, malicious,
                         rule_agrees, rule_bad, census, args.decode)
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nWrote {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    _args = parse_args()
    _rc = self_test()
    sys.exit(_rc or main(_args))
