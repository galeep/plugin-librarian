#!/usr/bin/env python3
"""Sentence-embedding baseline for Section 5.2 and Figure 3 (all-MiniLM-L6-v2).

Section 5.2 reports "Embeddings produced 3,626 clusters covering 9,462 files" (29.9%),
99.7% recall, P@>=20 92.9% (13/14), P@>=10 62.8% (27/43), and 924 s wall time. This
script recomputes every one of those figures.

Method: 384-dimensional embeddings of the first 2,048 characters of each file, cosine
similarity at 0.9, and the same greedy first-match clustering rule as the MinHash
pipeline. Encoding stays in torch throughout and values cross to Python only via
`.tolist()`, so the run does not depend on the torch/NumPy ABI pairing.

Inputs. LIBRARIAN_CORPUS (required) names the pinned March corpus; see
paper/supplementary/repository-commits.md. The file list is the archived scan's
`file_index`, resolved as `$LIBRARIAN_CORPUS/<marketplace>/<path>`. Ground-truth accounts come
from `paper/iocs.json` (`clawhub_authors`). Set HF_HUB_OFFLINE=1 so the model bytes
are the ones already cached; the run records the cached snapshot hash.

The MinHash comparison row is recomputed from the archived scan under the same
precision and recall definitions, not quoted from a stored literal.

Output: `embedding-comparison-<UTC date>.md` beside this script, or the full path in
SCAN_RESULTS_OUT. The Markdown template lives in `embedding_comparison_report.py`,
which computes nothing. A second run on the same UTC day overwrites the day's file.

Options: --decode strict|replace (default replace) chooses how non-UTF-8 corpus files
are read; `strict` skips and lists them, `replace` substitutes U+FFFD and keeps every
indexed file. See `load_corpus`.

Requires sentence-transformers and torch, which are not dependencies of the
`librarian` package. Any interpreter with those installed and the model cached will do.

Run:
  LIBRARIAN_CORPUS=$LIBRARIAN_CORPUS HF_HUB_OFFLINE=1 python \
    paper/sources/scans/embedding_comparison.py

Self-test runs first: a near-duplicate pair must score above the threshold and an
unrelated pair below it, so a broken encode or a wrong normalisation fails the run
rather than producing a plausible cluster count.
"""

import datetime
import json
import os
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import embedding_comparison_report as report
from embedding_comparison_report import git_head, model_snapshot, tilde

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

HERE = Path(__file__).resolve().parent
SCAN = HERE / "scan_20260314_threshold90_skillonly.json"
IOCS = HERE.parents[1] / "iocs.json"

def require_corpus():
    """Corpus root from LIBRARIAN_CORPUS, or exit; there is no default.

    DESIGN RATIONALE: a fallback to a checkout on the author's machine hands a
    reproducer plausible numbers computed against the wrong tree. No default is
    right, so there is none, and a missing or wrong value stops the run.
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


CORPUS = Path(require_corpus())
# DESIGN RATIONALE: the dated default name means a rerun cannot clobber a tracked
# baseline; SCAN_RESULTS_OUT (a full path) overrides it for a run that must not
# touch either the dated default or a prior run's file.
_DEFAULT_OUT_NAME = "embedding-comparison-{}.md".format(
    datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d"))
OUT = Path(os.environ["SCAN_RESULTS_OUT"]) if os.environ.get("SCAN_RESULTS_OUT") \
    else HERE / _DEFAULT_OUT_NAME

MODEL_NAME = "all-MiniLM-L6-v2"
THRESHOLD = 0.9
TRUNCATE_CHARS = 2048        # Section 5.2: "first 2,048 characters per file"
MIN_CHARS = 100              # the March loader's skip rule, kept
ENCODE_BATCH = 64            # the March loader's encode batch, kept
SIM_BATCH = 1000             # the March clusterer's similarity batch, kept
CLAWHUB = "clawhub-archive"
# `--decode strict` reproduces the March loader's silent drop of files that are not
# valid UTF-8; `replace` decodes them with U+FFFD. See load_corpus.
DECODE_MODES = ("replace", "strict")
DEFAULT_DECODE = "replace"

# Published Section 5.2 / Figure 3 figures for the embedding baseline.
PAPER = {
    "clusters": 3626, "files_in_clusters": 9462, "rate": 29.9, "recall": 99.7,
    "p20_mal": 13, "p20_n": 14, "p20": 92.9,
    "p10_mal": 27, "p10_n": 43, "p10": 62.8,
    "runtime": 924, "encode_s": 805, "cluster_s": 119,
}
# Observed outcome of each decode mode, one full run per mode on the pinned March
# corpus, 2026-09-07: (documents encoded, clusters, files in clusters). Recorded so a
# results file can state what the mode it did not run would have given.
#
# DESIGN RATIONALE: these are literals, and a literal printed beside a live run's own
# counts is exactly the shape of a number that goes wrong quietly. So every run now
# cross-checks the row for the mode it actually executed against what it just measured
# (see main); only the OTHER mode's row is unverified, and the results file labels it as
# recorded from a prior run rather than as this run's output. Update these values only
# from a run whose cross-check you have read.
DECODE_OBSERVED = {"strict": (31626, 3626, 9462), "replace": (31634, 3627, 9466)}

# Published MinHash row Section 5.2 quotes alongside it, for the comparison block.
PAPER_MINHASH = {"clusters": 2622, "files_in_clusters": 7147, "rate": 22.6,
                 "p20": 100.0, "p10": 78.9, "runtime": 305}


# --------------------------------------------------------------------------
# ground truth and attribution
# --------------------------------------------------------------------------

def get_author(marketplace, path):
    """Account owning a ClawHub archive file, or None.

    The marketplace must be `clawhub-archive` and the path must start `skills/`,
    with at least three segments, in which case the second segment is the account. (Note this is one segment looser than
    `file_level_precision.account_of`, which requires four; the looser rule is the
    one that produced the published embedding figures, so it is kept.)
    """
    parts = path.split("/")
    if marketplace == CLAWHUB and parts[0] == "skills" and len(parts) >= 3:
        return parts[1]
    return None


def malicious_authors(iocs):
    """The confirmed-malicious ClawHub accounts, read from paper/iocs.json.

    `clawhub_authors` is the single source for this set, so no second copy can
    disagree with the IOC file.
    """
    return set(iocs["clawhub_authors"])


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------

def load_files(scan):
    """Scan entries as dicts, exactly as `order_permutation.load_files` reads them."""
    entries = scan["file_index"]
    return entries if isinstance(entries, list) else list(entries.values())


def load_corpus(entries, root, decode=DEFAULT_DECODE):
    """(texts, metadata, skipped, undecodable) for entries resolving under `root`.

    Only `$LIBRARIAN_CORPUS/<marketplace>/<path>` is a real corpus path. A bare
    `$LIBRARIAN_CORPUS/<path>` fallback can resolve a different marketplace's file (14
    `curated` entries have paths beginning `hashicorp-agent-skills/`, itself a
    top-level marketplace directory), so a miss stays a miss. The `< 100
    characters` skip is the March loader's rule, kept.

    DESIGN RATIONALE for `decode`: eight indexed files are not valid UTF-8, and
    whether they enter the corpus is what separates the published document count
    from the full index. `strict` drops them, which is the population behind the
    paper's Section 5.2 figures, and records which files it dropped;
    `replace` (the default) decodes everything with U+FFFD substitutions, which is
    what `order_permutation.signatures` does and what a reader would assume from
    "all 31,634 files". The two are not interchangeable, so the mode is recorded in
    the results file rather than left implicit.
    """
    texts, metadata, undecodable = [], [], []
    skipped = {"missing": 0, "unreadable": 0, "undecodable": 0, "short": 0}
    errors = "strict" if decode == "strict" else "replace"
    for e in entries:
        p = root / e["marketplace"] / e["path"]
        try:
            text = p.read_text(encoding="utf-8", errors=errors)
        except UnicodeDecodeError:
            skipped["undecodable"] += 1
            undecodable.append(e)
            continue
        except OSError:
            skipped["missing" if not p.exists() else "unreadable"] += 1
            continue
        if len(text) < MIN_CHARS:
            skipped["short"] += 1
            continue
        texts.append(text)
        metadata.append(e)
    return texts, metadata, skipped, undecodable


# --------------------------------------------------------------------------
# encoding and clustering
# --------------------------------------------------------------------------

def encode(texts, model):
    """L2-normalised (n, 384) float32 torch tensor for the truncated texts.

    DESIGN RATIONALE: everything here stays in torch. torch 2.2.2 in this
    interpreter was compiled against NumPy 1.x and cannot hand a tensor to NumPy
    (`Tensor.numpy()` raises `RuntimeError: Numpy is not available`), so
    `convert_to_numpy` must stay off and no array ever crosses the boundary.
    Normalising once here makes the cosine similarity a plain matmul.
    """
    import torch

    truncated = [t[:TRUNCATE_CHARS] for t in texts]
    parts = []
    for start in range(0, len(truncated), ENCODE_BATCH):
        batch = truncated[start:start + ENCODE_BATCH]
        parts.append(model.encode(batch, show_progress_bar=False,
                                  batch_size=ENCODE_BATCH, convert_to_tensor=True))
        if start % (ENCODE_BATCH * 100) == 0:
            print(f"  encoded {start}/{len(truncated)}...", flush=True)
    embeddings = torch.cat(parts).to(torch.float32)
    return embeddings / embeddings.norm(dim=1, keepdim=True)


def _greedy_reference(sim_rows, n, threshold):
    """Literal transcription of the March greedy loop, over a full (n, n) matrix.

    Kept only so the self-test can prove the batched implementation below agrees
    with it. It is O(n^2) in Python and is never run on the corpus.
    """
    assigned, clusters = set(), []
    for global_i in range(n):
        if global_i in assigned:
            continue
        row = sim_rows[global_i]
        matches = set()
        for idx in range(n):
            if idx != global_i and idx not in assigned and row[idx] >= threshold:
                matches.add(idx)
        if matches:
            cluster = frozenset({global_i} | matches)
            clusters.append(cluster)
            assigned.update(cluster)
    return clusters


def greedy_cluster(sim_rows_for, n, threshold, batch_size=SIM_BATCH, progress=False):
    """The March greedy first-match clustering, driven by batched similarity rows.

    `sim_rows_for(start, end)` returns the (end - start, n) similarity rows for
    that batch. The rule is unchanged: walk files in index order; skip one already
    assigned; take every other still-unassigned file at or above the threshold; if
    there is at least one, emit the cluster and mark all of it assigned. A file
    matching nothing is left unclustered, and a cluster is never revisited.

    DESIGN RATIONALE: the only change from the March code is how the matching
    indices are found. It scanned `for idx in range(n)` in Python for every
    unassigned row, ~7e8 scalar reads here and far slower under torch scalar
    indexing than it was under NumPy. Thresholding the row in torch and walking
    only the indices that clear it yields the identical set, because
    `torch.nonzero` returns them in ascending order and the `idx != i` /
    `idx not in assigned` filters are applied unchanged. `_greedy_reference`
    pins that equivalence in the self-test rather than leaving it to inspection.
    The loop lives here once, so the self-test exercises the same code the corpus
    run does, with only the row source swapped.

    Returns (clusters, similarity_seconds, cluster_seconds).
    """
    import torch

    assigned, clusters = set(), []
    t_sim = t_clu = 0.0
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        if progress and start % (batch_size * 5) == 0:
            print(f"  batch {start}-{end} of {n} ({len(clusters)} clusters)...", flush=True)
        t = time.time()
        hits = sim_rows_for(start, end) >= threshold
        t_sim += time.time() - t

        t = time.time()
        for local_i in range(end - start):
            global_i = start + local_i
            if global_i in assigned:
                continue
            candidates = torch.nonzero(hits[local_i], as_tuple=False).flatten().tolist()
            matches = {idx for idx in candidates if idx != global_i and idx not in assigned}
            if matches:
                cluster = frozenset({global_i} | matches)
                clusters.append(cluster)
                assigned.update(cluster)
        t_clu += time.time() - t
    return clusters, t_sim, t_clu


def cluster_embeddings(embeddings, threshold, batch_size=SIM_BATCH):
    """Cluster L2-normalised embeddings: cosine similarity is then a plain matmul."""
    n = embeddings.shape[0]
    return greedy_cluster(lambda s, e: embeddings[s:e] @ embeddings.T,
                          n, threshold, batch_size, progress=True)


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------

def evaluate_clusters(clusters, metadata, mal_authors):
    """Cluster-level precision by size threshold, and recall over hightower6eu.

    Precision at size s: of the clusters holding at least s files, the share
    holding at least one file attributed to a confirmed-malicious account.
    Recall: of the hightower6eu files present in the loaded corpus, the share
    landing in any cluster.
    """
    results = {}
    for min_size in (5, 10, 15, 20):
        large = [c for c in clusters if len(c) >= min_size]
        if not large:
            results[min_size] = {"precision": None, "count": 0, "malicious": 0}
            continue
        mal = sum(1 for c in large
                  if any(get_author(metadata[i]["marketplace"], metadata[i]["path"])
                         in mal_authors for i in c))
        results[min_size] = {"precision": mal / len(large) * 100,
                             "count": len(large), "malicious": mal}

    clustered = set()
    for c in clusters:
        clustered.update(c)
    h6_total = h6_in = 0
    for i, fi in enumerate(metadata):
        if get_author(fi["marketplace"], fi["path"]) == "hightower6eu":
            h6_total += 1
            if i in clustered:
                h6_in += 1
    recall = h6_in / h6_total * 100 if h6_total else 0.0
    return results, recall, h6_in, h6_total


def minhash_from_scan(scan, mal_authors):
    """The MinHash comparison row, recomputed from the archived scan.

    Everything except the 305 s runtime, which the scan does not carry, is
    recomputed here under the same precision and recall rules used for the
    embedding row, so the comparison is between two measured columns.
    """
    clusters = scan["clusters"]
    memberships = sum(len(c["locations"]) for c in clusters)
    distinct = len({(l["marketplace"], l["path"]) for c in clusters for l in c["locations"]})
    out = {"clusters": len(clusters), "memberships": memberships, "distinct": distinct}
    for sz in (10, 20):
        big = [c for c in clusters if len(c["locations"]) >= sz]
        mal = sum(1 for c in big
                  if any(get_author(l["marketplace"], l["path"]) in mal_authors
                         for l in c["locations"]))
        out[f"p{sz}"] = 100 * mal / len(big) if big else float("nan")
        out[f"p{sz}_mal"], out[f"p{sz}_n"] = mal, len(big)
    clustered = {(l["marketplace"], l["path"]) for c in clusters for l in c["locations"]}
    tot = hit = 0
    for e in scan["file_index"]:
        if get_author(e["marketplace"], e["path"]) == "hightower6eu":
            tot += 1
            if (e["marketplace"], e["path"]) in clustered:
                hit += 1
    out["recall"] = 100 * hit / tot if tot else float("nan")
    out["recall_hit"], out["recall_tot"] = hit, tot
    return out


# --------------------------------------------------------------------------
# self-test
# --------------------------------------------------------------------------

# Two near-duplicates and one unrelated sentence. The pair differs only in
# function words, so it must clear the 0.9 threshold; the third shares no topic.
SELFTEST_TEXTS = [
    "Install the package with pip and then run the command line tool to start the server.",
    "Install the package using pip, then run the command-line tool to start the server.",
    "Arctic terns migrate from pole to pole every year, the longest migration of any bird.",
]


def self_test(model) -> int:
    """Check the encoder's cosine ordering and the greedy loop before the real run.

    DESIGN RATIONALE: two things here fail silently rather than loudly. A model
    that loaded but resolved to different weights, or a normalisation that was
    skipped, still produces a plausible-looking similarity matrix; and the batched
    greedy loop could quietly disagree with the March one at a batch boundary, or
    at the threshold itself, and still emit a believable cluster count. So the
    encoder is pinned by a known cosine ordering on three short sentences run
    through `encode` itself, and the loop by equality with a literal transcription
    of the original over a matrix carrying both a cross-batch match and a pair at
    exactly the threshold.

    Both arms are mutation-tested. Changing `greedy_cluster`'s `>=` to `>` passed an
    earlier version of this test, because the matrix then had no value at 0.9; it now
    fails. Normalising on the wrong axis in `encode` fails the first arm.

    One mutation cannot be caught, and the reason is worth recording rather than
    papering over: DELETING the `/ norm` line from `encode` changes nothing at all.
    `all-MiniLM-L6-v2` ships a `Normalize` module (`modules.json`: Transformer,
    Pooling, Normalize), so `model.encode` already returns unit vectors and the
    division is a no-op for this model. It is kept as a guard for a model that does
    not normalise, and the check below tests the property that actually matters --
    that whatever reaches the matmul is unit-norm -- rather than the line.
    """
    import torch

    # DESIGN RATIONALE: this MUST go through encode(), not a local copy of what
    # encode does. An earlier version normalised inline here, so deleting the
    # normalisation from encode() left the self-test passing while the corpus run
    # went on to cluster unnormalised dot products. Routing the three sentences
    # through the real function is what makes the self-similarity check below an
    # actual test of the code that runs on the corpus.
    e = encode(SELFTEST_TEXTS, model)
    sim = (e @ e.T).tolist()
    dup, far_a, far_b = sim[0][1], sim[0][2], sim[1][2]
    for i in range(3):
        if abs(sim[i][i] - 1.0) > 1e-4:
            print(f"self-test FAILED: self-similarity {sim[i][i]} is not 1 "
                  f"(embeddings are not normalised)", file=sys.stderr)
            return 1
    if not dup >= THRESHOLD:
        print(f"self-test FAILED: near-duplicate pair scored {dup:.4f}, "
              f"below the {THRESHOLD} threshold", file=sys.stderr)
        return 1
    if not (far_a < 0.5 and far_b < 0.5):
        print(f"self-test FAILED: unrelated sentence scored {far_a:.4f}/{far_b:.4f}, "
              f"expected well below 0.5", file=sys.stderr)
        return 1
    if not (dup > far_a and dup > far_b):
        print(f"self-test FAILED: cosine ordering wrong ({dup:.4f} vs "
              f"{far_a:.4f}, {far_b:.4f})", file=sys.stderr)
        return 1

    # Greedy loop. Seven items; 0 matches 1 and 4 (4 is in the next batch under
    # batch_size=2, so this also exercises a batch boundary), 2 matches 3, and 5
    # matches 6 at EXACTLY the threshold. Expected by hand: [{0,1,4}, {2,3}, {5,6}];
    # item 1 is already assigned when reached, and no cluster is revisited.
    #
    # DESIGN RATIONALE for the 0.9 cell: the rule is `>= threshold`, and inclusivity
    # at exactly the threshold is the one place it can change silently and move a
    # cluster count. Without a boundary value in this matrix, flipping `>=` to `>`
    # in greedy_cluster passed the whole self-test. float32(0.9) >= 0.9 is True in
    # torch (the Python scalar is cast to the tensor's dtype) and > 0.9 is False, so
    # the {5,6} cluster disappears under that mutation and the check fires.
    m = [[1.0, 0.95, 0.10, 0.10, 0.92, 0.10, 0.10],
         [0.95, 1.0, 0.10, 0.10, 0.20, 0.10, 0.10],
         [0.10, 0.10, 1.0, 0.99, 0.10, 0.10, 0.10],
         [0.10, 0.10, 0.99, 1.0, 0.10, 0.10, 0.10],
         [0.92, 0.20, 0.10, 0.10, 1.0, 0.10, 0.10],
         [0.10, 0.10, 0.10, 0.10, 0.10, 1.0, 0.90],
         [0.10, 0.10, 0.10, 0.10, 0.10, 0.90, 1.0]]
    t = torch.tensor(m, dtype=torch.float32)
    want = [frozenset({0, 1, 4}), frozenset({2, 3}), frozenset({5, 6})]
    if not (t[5][6] >= THRESHOLD) or (t[5][6] > THRESHOLD):
        print(f"self-test FAILED: the boundary cell is {t[5][6].item()!r}, which does "
              f"not sit exactly on the {THRESHOLD} threshold", file=sys.stderr)
        return 1
    ref = _greedy_reference(m, 7, THRESHOLD)
    if ref != want:
        print(f"self-test FAILED: reference greedy loop gave {ref}, expected {want}",
              file=sys.stderr)
        return 1
    # The production loop, driven from the same matrix. Batch sizes 2 and 3 split
    # the {0,1,4} cluster across a boundary, 2 and 3 also split {5,6}, and 7 runs
    # the whole matrix in one batch.
    for bs in (2, 3, 5, 7):
        got, _, _ = greedy_cluster(lambda s, e: t[s:e], 7, THRESHOLD, bs)
        if got != want:
            print(f"self-test FAILED: batched greedy loop at batch_size={bs} gave "
                  f"{got}, expected {want}", file=sys.stderr)
            return 1
    return 0


def parse_args(argv=None):
    """Just `--decode strict|replace`. argparse would be four lines longer here.

    DESIGN RATIONALE: the mode changes which documents are encoded, so a typo must
    stop the run rather than fall through to the default and produce a results file
    that names the wrong mode.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    decode = DEFAULT_DECODE
    while argv:
        a = argv.pop(0)
        if a == "--decode":
            if not argv:
                sys.exit("--decode needs a value: " + " | ".join(DECODE_MODES))
            decode = argv.pop(0)
        elif a.startswith("--decode="):
            decode = a.split("=", 1)[1]
        else:
            sys.exit(f"unknown argument {a!r}; only --decode {'|'.join(DECODE_MODES)}")
        if decode not in DECODE_MODES:
            sys.exit(f"--decode must be one of {' | '.join(DECODE_MODES)}, got {decode!r}")
    return decode


def main(argv=None) -> int:
    decode = parse_args(argv)
    import torch
    import numpy
    import sklearn
    import sentence_transformers
    from sentence_transformers import SentenceTransformer

    print(f"Loading {MODEL_NAME} (HF_HUB_OFFLINE="
          f"{os.environ.get('HF_HUB_OFFLINE', 'unset')})...", flush=True)
    t0 = time.time()
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    t_load = time.time() - t0
    print(f"Model loaded in {t_load:.1f}s", flush=True)

    if self_test(model):
        return 1
    print("self-test passed", flush=True)

    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    iocs = json.loads(IOCS.read_text(encoding="utf-8"))
    mal_authors = malicious_authors(iocs)
    entries = load_files(scan)

    t = time.time()
    texts, metadata, skipped, undecodable = load_corpus(entries, CORPUS, decode)
    t_read = time.time() - t
    print(f"Loaded {len(texts)} files of {len(entries)} in {t_read:.1f}s "
          f"(--decode {decode}; skipped {skipped})", flush=True)
    if not texts:
        print(f"no files resolved under {CORPUS}", file=sys.stderr)
        return 1

    print("Encoding...", flush=True)
    t = time.time()
    embeddings = encode(texts, model)
    t_encode = time.time() - t
    print(f"Encoded {len(texts)} documents in {t_encode:.1f}s "
          f"(dim {embeddings.shape[1]})", flush=True)

    print("Clustering...", flush=True)
    clusters, t_sim, t_clu = cluster_embeddings(embeddings, THRESHOLD)
    total = t_load + t_read + t_encode + t_sim + t_clu

    memberships = sum(len(c) for c in clusters)
    distinct = len(set().union(*clusters)) if clusters else 0
    rate = memberships / len(texts) * 100
    precision, recall, h6_in, h6_total = evaluate_clusters(clusters, metadata, mal_authors)
    mh = minhash_from_scan(scan, mal_authors)

    # Cross-check this run against the recorded outcome for the mode it executed.
    # DESIGN RATIONALE: the results file prints DECODE_OBSERVED beside cmp_rows, which
    # is built from this run's real clusters. Without this comparison the two could
    # disagree on screen with nothing saying so. The verdict is rendered into the
    # results table AND warned to stderr, and the run exits non-zero -- but the file is
    # written first, so a failing run leaves its output on disk to be read. That is the
    # same order exact_hash_baseline.py and file_level_precision.py use, and it is the
    # reason this does not raise: raising would destroy the artifact needed to diagnose
    # the mismatch. Trust the exit status, not the presence of the file.
    observed = (len(texts), len(clusters), memberships)
    recorded = DECODE_OBSERVED.get(decode)
    decode_ok = recorded is not None and tuple(recorded) == observed

    OUT.write_text(report.render(
        PAPER=PAPER, PAPER_MINHASH=PAPER_MINHASH, MODEL_NAME=MODEL_NAME,
        DECODE_OBSERVED=DECODE_OBSERVED, DEFAULT_DECODE=DEFAULT_DECODE,
        decode_observed_run=observed, decode_check_ok=decode_ok,
        THRESHOLD=THRESHOLD, TRUNCATE_CHARS=TRUNCATE_CHARS, MIN_CHARS=MIN_CHARS,
        ENCODE_BATCH=ENCODE_BATCH, SIM_BATCH=SIM_BATCH,
        CORPUS=CORPUS, SCAN=SCAN, IOCS=IOCS, HERE=HERE,
        SCRIPT_NAME=Path(__file__).name,
        decode=decode,
        scan=scan, entries=entries, texts=texts, mal_authors=mal_authors,
        skipped=skipped, undecodable=undecodable, embeddings_dim=embeddings.shape[1],
        clusters=clusters, memberships=memberships, distinct=distinct, rate=rate,
        precision=precision, recall=recall, h6_in=h6_in, h6_total=h6_total, mh=mh,
        t_load=t_load, t_read=t_read, t_encode=t_encode, t_sim=t_sim, t_clu=t_clu,
        total=total), encoding="utf-8")

    def pct(p):
        """`92.9% (13/14)`, or `n/a (0/0)` for a size threshold no cluster reaches."""
        if p["precision"] is None:
            return f"n/a ({p['malicious']}/{p['count']})"
        return f"{p['precision']:.1f}% ({p['malicious']}/{p['count']})"

    p20, p10 = precision[20], precision[10]


    print(f"\nwrote {tilde(OUT)}", flush=True)
    print(f"  clusters {len(clusters)}, memberships {memberships}, distinct {distinct} "
          f"({rate:.1f}%)", flush=True)
    print(f"  recall {recall:.1f}% ({h6_in}/{h6_total}), "
          f"P@20 {pct(p20)}, P@10 {pct(p10)}", flush=True)
    print(f"  runtime {total:.1f}s = load {t_load:.1f} + read {t_read:.1f} + "
          f"encode {t_encode:.1f} + sim {t_sim:.1f} + cluster {t_clu:.1f}", flush=True)
    if not decode_ok:
        print(f"MISMATCH: --decode {decode} measured {observed} "
              f"(documents, clusters, files in clusters), but DECODE_OBSERVED records "
              f"{tuple(recorded) if recorded else None}. The results file is on disk and "
              f"marks the row MISMATCH; do not quote its numbers until this is explained.",
              file=sys.stderr)
        return 1
    print(f"  decode cross-check: {observed} matches DECODE_OBSERVED[{decode!r}]", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
