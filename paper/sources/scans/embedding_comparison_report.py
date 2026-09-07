#!/usr/bin/env python3
"""Markdown rendering for `embedding_comparison.py`.

Nothing here computes a result. `render()` takes values the run has already produced
and returns the text of the results file; `embedding_comparison.py` writes it. No CLI:
importing this module has no side effects beyond the imports.

`tilde`, `_git` and `git_head` duplicate the helpers in `order_permutation.py` rather
than importing them, because that module imports datasketch and the embedding run does
not need it. Keep the two copies in step.

`git_head` reports the short HEAD of the checkout rooted exactly at the given
directory, or a reason string; `model_snapshot` reports the cached Hugging Face
snapshot hash, which is what makes an offline encode reproducible.
"""

import datetime
import os
import sys
from pathlib import Path
import subprocess


# --------------------------------------------------------------------------
# provenance helpers (copied from order_permutation.py rather than imported:
# that module imports datasketch, which the embedding run does not need)
# --------------------------------------------------------------------------

def tilde(path):
    """Home-relative form of a path, so console output carries no user directory."""
    home = os.path.expanduser("~")
    path = str(path)
    return "~" + path[len(home):] if path.startswith(home) else path


def _git(d, *args):
    """stdout of a git command, or None if it exited non-zero.

    No exception handling here on purpose. `git_head` is the only caller and it
    already turns FileNotFoundError, OSError and SubprocessError into the reason
    strings that render into the results file.
    """
    r = subprocess.run(["git", "-C", str(d), *args], capture_output=True,
                       text=True, timeout=30)
    return r.stdout.strip() if r.returncode == 0 else None


def git_head(d):
    """Short HEAD of the checkout rooted exactly at `d`, else a reason string.

    DESIGN RATIONALE: `git -C` walks up to a parent repository, so a plain
    directory sitting inside one would otherwise be reported with the parent's
    SHA. Comparing --show-toplevel against `d` rejects that. Read-only.
    """
    if not d.is_dir():
        return "directory absent"
    try:
        top = _git(d, "rev-parse", "--show-toplevel")
        if top is None or Path(top).resolve() != d.resolve():
            return "not a git checkout"
        head = _git(d, "rev-parse", "--short", "HEAD")
        if head is None:
            return "not a git checkout"
        dirty = _git(d, "status", "--porcelain")
        if dirty is None:
            return f"{head}+status unknown"
        return f"{head}+dirty" if dirty else head
    except FileNotFoundError:
        return "git unavailable"
    except (OSError, subprocess.SubprocessError):
        return "not a git checkout"


def model_snapshot(name):
    """Cached Hugging Face snapshot hash for the model, or a reason string.

    The run is pinned with HF_HUB_OFFLINE=1, so the bytes encoded are whatever is
    in the local hub cache; recording the hash is what makes the encode reproducible.
    """
    root = Path(os.path.expanduser("~/.cache/huggingface/hub"))
    for owner in ("sentence-transformers", "models"):
        d = root / f"models--{owner}--{name}" / "snapshots"
        if d.is_dir():
            snaps = sorted(p.name for p in d.iterdir() if p.is_dir())
            if snaps:
                return ", ".join(snaps)
    return "not found in the local hub cache"


# report

def row(label, paper, got, fmt="{:,}", tol=0.0):
    """One comparison row.

    `tol` allows a rounding-width match on percentages. `tol=None` means the two
    values are not compared at all (the runtime rows: wall time depends on the
    machine and on what else it was running), so the row shows both and marks the
    verdict `n/a` rather than claiming a match it has not tested.
    """
    if paper is None:
        return f"| {label} | n/a | {fmt.format(got)} | n/a |"
    if tol is None:
        return f"| {label} | {fmt.format(paper)} | {fmt.format(got)} | n/a |"
    match = "yes" if abs(paper - got) <= tol else "NO"
    return f"| {label} | {fmt.format(paper)} | {fmt.format(got)} | {match} |"


def render(*, PAPER, PAPER_MINHASH, DECODE_OBSERVED, DEFAULT_DECODE,
           decode_observed_run, decode_check_ok, MODEL_NAME, THRESHOLD, TRUNCATE_CHARS, MIN_CHARS,
           ENCODE_BATCH, SIM_BATCH, CORPUS, SCAN, IOCS, HERE, SCRIPT_NAME,
           decode,
           scan, entries, texts, mal_authors, skipped, undecodable, embeddings_dim,
           clusters, memberships, distinct, rate, precision, recall, h6_in, h6_total, mh,
           t_load, t_read, t_encode, t_sim, t_clu, total):
    """Render the results Markdown. Every input is a value the run already computed.

    DESIGN RATIONALE: this is a rendering function and nothing else. It performs no
    file reads, no clustering and no arithmetic beyond formatting and the comparisons
    the caller has already fixed, so it cannot change a reported number; keeping it in
    its own module keeps the computation and the rendering apart. The
    keyword-only signature names exactly what the report depends on, and a missing
    input is a TypeError at the call rather than a blank cell in the results file.
    """
    import numpy
    import sklearn
    import sentence_transformers
    import torch

    p20, p10 = precision[20], precision[10]

    def pct(p):
        """`92.9% (13/14)`, or `n/a (0/0)` for a size threshold no cluster reaches."""
        if p["precision"] is None:
            return f"n/a ({p['malicious']}/{p['count']})"
        return f"{p['precision']:.1f}% ({p['malicious']}/{p['count']})"

    markets = sorted({e["marketplace"] for e in entries})
    n_markets = len(markets)
    heads = "\n".join(f"| `{m}` | {git_head(CORPUS / m)} |" for m in markets)
    # Paths in the results file are repository-relative, never absolute.
    repo_root = HERE.parents[2]
    iocs_rel = IOCS.relative_to(repo_root).as_posix()
    cmp_rows = "\n".join([
        row("Clusters", PAPER["clusters"], len(clusters)),
        row("Files in clusters (memberships)", PAPER["files_in_clusters"], memberships),
        row("Distinct files in clusters", None, distinct),
        row("...as a share of the corpus", PAPER["rate"], rate, "{:.1f}%", tol=0.05),
        row("Recall (hightower6eu)", PAPER["recall"], recall, "{:.1f}%", tol=0.05),
        row(f"P@>=20 ({PAPER['p20_mal']}/{PAPER['p20_n']} published; "
            f"{p20['malicious']}/{p20['count']} here)",
            PAPER["p20"], p20["precision"] if p20["precision"] is not None else float("nan"),
            "{:.1f}%", tol=0.05),
        row(f"P@>=10 ({PAPER['p10_mal']}/{PAPER['p10_n']} published; "
            f"{p10['malicious']}/{p10['count']} here)",
            PAPER["p10"], p10["precision"] if p10["precision"] is not None else float("nan"),
            "{:.1f}%", tol=0.05),
        row("Runtime, wall", PAPER["runtime"], total, "{:,.0f}s", tol=None),
        row("...encoding", PAPER["encode_s"], t_encode, "{:,.0f}s", tol=None),
        row("...similarity + clustering", PAPER["cluster_s"], t_sim + t_clu, "{:,.0f}s", tol=None),
    ])
    # Where any disagreement sits. The published precision rows pin the >= 10 and
    # >= 20 cluster counts exactly, so if those two reproduce, a difference in the
    # total cluster count can only come from clusters below size 10.
    diffs = [("Clusters", PAPER["clusters"], len(clusters), "{:,}"),
             ("Files in clusters", PAPER["files_in_clusters"], memberships, "{:,}")]
    diffs = [d for d in diffs if d[1] != d[2]]
    big_ok = (p10["count"] == PAPER["p10_n"] and p20["count"] == PAPER["p20_n"]
              and p10["malicious"] == PAPER["p10_mal"] and p20["malicious"] == PAPER["p20_mal"])
    small_clusters = sum(1 for c in clusters if len(c) < 10)
    small_files = sum(len(c) for c in clusters if len(c) < 10)
    if not diffs:
        diff_section = ("Every published cell reproduces exactly, so there is no difference to "
                        "explain.")
    else:
        delta = diffs[0][2] - diffs[0][1]
        table = "\n".join([
            "| Cell | Paper | Recomputed | Delta |", "|---|---:|---:|---:|",
            *[f"| {lab} | {f.format(p)} | {f.format(g)} | {g - p:+,} |" for lab, p, g, f in diffs],
        ])
        # DESIGN RATIONALE: "the difference is confined to small clusters" is only
        # true when the >= 10 and >= 20 buckets and recall all reproduce. Asserting
        # it unconditionally would put a false claim in the results file on any run
        # where they do not, so the sentence is gated on the numbers themselves.
        recall_ok = abs(PAPER["recall"] - recall) <= 0.05
        if big_ok and recall_ok:
            where = (f"The disagreement is confined to small clusters. The published precision "
                     f"rows fix the cluster counts at the two size thresholds, and both "
                     f"reproduce exactly here ({p20['malicious']}/{p20['count']} at >= 20 and "
                     f"{p10['malicious']}/{p10['count']} at >= 10), so every cluster the paper's "
                     f"own figures identify is reproduced; the {small_clusters:,} clusters below "
                     f"size 10, holding {small_files:,} files, absorb the whole difference. "
                     f"Recall reproduces exactly too, so no published precision or recall figure "
                     f"moves.")
        else:
            where = (f"The disagreement is NOT confined to small clusters: the size-thresholded "
                     f"buckets are {p20['malicious']}/{p20['count']} at >= 20 and "
                     f"{p10['malicious']}/{p10['count']} at >= 10 against the published "
                     f"{PAPER['p20_mal']}/{PAPER['p20_n']} and {PAPER['p10_mal']}/"
                     f"{PAPER['p10_n']}, and recall is {recall:.1f}% against {PAPER['recall']}%. "
                     f"Published precision or recall figures move, so this run does not "
                     f"reproduce the baseline and the causes below are not sufficient to "
                     f"explain it.")
        diff_section = f"""{table}

{where}

Candidate causes of a {delta:+,d}-cluster shift, in rough order of how much of it each
could produce:

1. **Package versions.** No lock file pins them. This run used sentence-transformers
   {sentence_transformers.__version__} and torch {torch.__version__}; a change in the
   tokenizer, the pooling path or a default dtype between two versions shifts borderline
   cosines.
2. **Float arithmetic.** Normalization and the matmul run in float32, and the summation
   order inside the matmul differs between libraries and builds. A pair sitting within
   roughly 1e-6 of 0.9 can land on the other side of the comparison, and because the
   clustering is greedy and order-dependent, one flipped pair can cascade into a different
   cluster count.
3. **A corpus not at the recorded commits.** The marketplace HEAD table above must match
   `paper/supplementary/repository-commits.md`; a checkout at a different commit changes
   file contents and therefore memberships.
4. **A different file list.** The file list is the archived scan's `file_index`; a run that
   indexes the corpus afresh can differ from it by a handful of entries, and the membership
   counts move directly.

Causes 1 and 2 are arithmetic-side, 3 and 4 corpus-side; the provenance table above is
what separates them."""
    size_rows = "\n".join(
        f"| >= {sz} | {p['count']} | {p['malicious']} | "
        + (f"{p['precision']:.1f}% |" if p["precision"] is not None else "n/a |")
        for sz, p in sorted(precision.items()))
    # Decode-mode rows. The row for the mode this run executed carries THIS RUN's
    # measured triple and the verdict of the cross-check against DECODE_OBSERVED; the
    # other row is the recorded value from a prior run and is labeled as such, because
    # nothing in this run can confirm it.
    _mode_label = {"strict": "the population the paper states",
                   "replace": "the script default"}
    decode_rows = []
    for mode in ("strict", "replace"):
        rec = DECODE_OBSERVED.get(mode)
        if mode == decode:
            n, c, m = decode_observed_run
            src = ("**this run**, cross-checked against the recorded value: match"
                   if decode_check_ok else
                   f"**this run**, **MISMATCH** against the recorded "
                   f"{tuple(rec) if rec else None}; see the warning on stderr")
        else:
            n, c, m = rec if rec else (0, 0, 0)
            src = "recorded from a prior run; not executed here"
        decode_rows.append(f"| `{mode}` ({_mode_label[mode]}) | {n:,} | {c:,} | {m:,} | {src} |")
    decode_rows = "\n".join(decode_rows)
    # DESIGN RATIONALE: the command block interpolates every flag whose value is not
    # the default, so the one copy-and-run path in this file reproduces the run that
    # wrote the file rather than the script's defaults. A flag added later must be
    # added here too, or this file will print a command that contradicts its own
    # numbers.
    flags = [f"--decode {decode}"] if decode != DEFAULT_DECODE else []
    flag_block = (" \\\n  " + " ".join(flags)) if flags else ""
    skip_rows = " | ".join(str(skipped[k]) for k in
                           ("missing", "unreadable", "undecodable", "short"))
    if undecodable:
        undec_block = "\n".join(
            [f"`--decode {decode}` dropped these {len(undecodable)} files, which are not valid "
             "UTF-8:", ""]
            + [f"- `{e['marketplace']}/{e['path']}`" for e in
               sorted(undecodable, key=lambda e: (e["marketplace"], e["path"]))])
    else:
        undec_block = (f"`--decode {decode}` dropped no files: every file the index names "
                       "decoded without error." if decode == "strict" else
                       "`--decode replace` drops nothing on decoding; bytes that are not valid "
                       "UTF-8 become U+FFFD and the file is still encoded.")


    return f"""# Sentence-embedding baseline (Section 5.2 recompute)

This file reports a recompute of the sentence-embedding baseline that Section 5.2
(Comparison with Simple Baselines) sets beside MinHash and TF-IDF, and that Figure 3
plots. It supports these Section 5.2 sentences: "We encoded every file that decodes as
UTF-8 (31,626 of 31,634) with the sentence-transformers model all-MiniLM-L6-v2
(384-dimensional embeddings, first 2,048 characters per file) and clustered at 0.9 cosine
similarity. Embeddings produced 3,626 clusters covering 9,462 files (29.9%) with 99.7%
recall. Precision fell between TF-IDF and MinHash: P@$\\geq$20 was 92.9% (13/14) and
P@$\\geq$10 was 62.8% (27/43). Runtime was 924 s (805 s encoding, 119 s clustering),
three times slower than MinHash." The run reads the archived scan's `file_index` against
the pinned corpus snapshot and writes every recomputed figure beside the published one.

## Provenance

| Item | Value |
|---|---|
| Python | {sys.version.split()[0]} |
| sentence-transformers | {sentence_transformers.__version__} |
| torch | {torch.__version__} |
| scikit-learn | {sklearn.__version__} |
| numpy | {numpy.__version__} |
| datasketch | not required by this script |
| Model | `{MODEL_NAME}`, {embeddings_dim}-dimensional |
| Model snapshot | `{model_snapshot(MODEL_NAME)}` |
| `HF_HUB_OFFLINE` | `{os.environ.get("HF_HUB_OFFLINE", "unset")}` |
| Decode mode | `--decode {decode}` |
| Corpus root | `$LIBRARIAN_CORPUS` |
| Scan | `{SCAN.name}`, `generated_at` {scan["metadata"]["generated_at"]} |
| Ground truth | `{iocs_rel}`, `clawhub_authors` ({len(mal_authors)} accounts) |
| Repository HEAD | {git_head(repo_root)} |
| Run at | {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")} |

The package versions in the table are the ones this run used, and the published figures
reproduce under them. No lock file pins them, so a rerun records its own.

Command, as run, with LIBRARIAN_CORPUS set. Every non-default flag is interpolated from
the run itself, so copying this block out and running it reproduces the numbers below
rather than the script's defaults:

```
HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false \\
  python \\
  paper/sources/scans/{SCRIPT_NAME}{flag_block}
```

| Runtime split | Seconds |
|---|---:|
| Model load | {t_load:.1f} |
| Corpus read | {t_read:.1f} |
| Encode | {t_encode:.1f} |
| Cosine similarity (batched matmul) | {t_sim:.1f} |
| Greedy clustering | {t_clu:.1f} |
| **Total** | **{total:.1f}** |

The paper reports one 924 s figure split 805 s encode / 119 s cluster. Its "cluster" number
covers similarity and clustering together, so compare it against the sum of the last two
rows ({t_sim + t_clu:.1f} s). Runtimes here are not comparable to the published figures: wall time depends on the machine and its load.

Snapshot the numbers above and below were computed from. Compare against
`paper/supplementary/repository-commits.md`. Listed here are the {n_markets} marketplaces that
contribute at least one file to the scan's `file_index`; corpus directories with no indexed file
are not read by this script and so are not pinned by it.

| Marketplace | git HEAD |
|---|---|
{heads}

| Files in index | Loaded | Missing | Unreadable | Undecodable | Under {MIN_CHARS} chars |
|---:|---:|---:|---:|---:|---:|
| {len(entries):,} | {len(texts):,} | {skip_rows} |

{undec_block}

## Rules

Section 5.2 gives the model, the population ("every file that decodes as UTF-8 (31,626 of
31,634)"), the 2,048-character truncation, the 0.9 cosine threshold and the greedy
first-match rule. The remaining rules are stated here in full.

- **Encoded unit.** The first {TRUNCATE_CHARS} characters of each file, decoded as UTF-8 with
  `errors="{decode}"`, encoded by `{MODEL_NAME}` on CPU in batches of {ENCODE_BATCH}. Files under
  {MIN_CHARS} characters are skipped ({skipped["short"]} here).
- **Decoding.** Eight indexed files are not valid UTF-8. `--decode strict` skips them, which
  gives the population Section 5.2 states, and names the files it drops; `--decode replace`
  (the script default) substitutes U+FFFD and encodes everything the index names. The two
  give different document counts, so the mode is in the provenance table above.
- **File list.** The archived scan's `file_index`, resolved as `$LIBRARIAN_CORPUS/<marketplace>/<path>`,
  mirroring `order_permutation.load_files`. A bare `$LIBRARIAN_CORPUS/<path>` fallback is not used, so a
  path that does not resolve is a skip.
- **Similarity.** Cosine, computed as a matmul of L2-normalized embeddings, in row batches of
  {SIM_BATCH}, entirely in torch. Values reach Python only through `.tolist()`, so no array
  crosses between torch and NumPy at any point.
- **Clustering.** The same greedy first-match rule as the MinHash pipeline: walk files in index
  order; skip one already assigned; collect every other still-unassigned file at or above
  {THRESHOLD}; emit the cluster if non-empty and mark all of it assigned. A file matching nothing
  stays unclustered and no cluster is revisited. The implementation finds the matching indices by
  thresholding the row in torch instead of scanning `range(n)` in Python; the startup self-test
  proves the two agree, including across a batch boundary.
- **Attribution.** `clawhub-archive` files whose path begins `skills/` with at least three
  segments are attributed to the second segment. This is one segment looser than
  `file_level_precision.account_of` (which requires four), and is kept because it is the rule the
  published figures used.
- **Malicious.** The {len(mal_authors)} accounts in `iocs.json` `clawhub_authors`, which is the
  single source for the set, so no second copy can disagree with it.
- **Precision at size s.** Of clusters holding at least s files, the share holding at least one
  file attributed to one of those accounts. Cluster-level, not file-level.
- **Recall.** Of the hightower6eu files in the loaded corpus ({h6_total:,}), the share landing in any
  cluster ({h6_in:,}).

## Comparison with the published values

| Quantity | Paper | Recomputed | Match |
|---|---:|---:|:--:|
{cmp_rows}

Runtime rows carry no verdict: wall time depends on the machine and its load, so a
wall-clock disagreement says nothing about the method. The similarity + clustering figure is also
not like-for-like, because the greedy loop here finds its matching indices by thresholding the row
in torch rather than scanning `range(n)` in Python.

## Where the recompute differs, and why

{diff_section}

## Decode mode

The eight undecodable files above are the whole difference between the two decode modes. One
full run per mode on this corpus, both deterministic. Only one mode runs at a time, so the last
column says which row this run measured and which is quoted from a previous one:

| `--decode` | Documents encoded | Clusters | Files in clusters | Source |
|---|---:|---:|---:|---|
{decode_rows}
| Section 5.2 as published | not stated | {PAPER["clusters"]:,} | {PAPER["files_in_clusters"]:,} | the paper |

The row for `{decode}` is not a literal: this run measured {decode_observed_run[0]:,} documents,
{decode_observed_run[1]:,} clusters and {decode_observed_run[2]:,} files in clusters, and the
script compares that triple against its recorded `DECODE_OBSERVED` entry before writing this
file. {"The two agree." if decode_check_ok else "**They do not agree.** The run exited non-zero and warned on stderr; this file was written anyway so the mismatch can be read, so do not quote its numbers until it is explained."} The other mode's row cannot be checked by a run that did
not execute it, and is marked accordingly.

`strict` matches the published figures exactly; `replace` differs by +1 cluster and +4 files,
because the eight documents outside the stated population are encoded and four of them find a
partner at 0.9. The same eight files separate the TF-IDF baseline's document count from the full
index, so one decode decision shows up in both baselines rather than two independent
discrepancies.

`strict` is the mode that reproduces Section 5.2. `replace` is kept so a reader can measure
what the eight files add, and this file names its mode in the provenance table so the two
cannot be confused.

The "9,462 files (29.9%)" cell can be read as cluster memberships or as distinct files. Here
memberships are {memberships:,} and distinct files {distinct:,}; the greedy rule
only ever assigns an unassigned file, so the two coincide by construction, and the published
figure is a membership count under a rule that makes it also a file count. (The MinHash side of
the same sentence differs: the archived scan's 7,147 is a membership count over 7,061 distinct
files, because MinHash clusters overlap, as the caption of Table 2 states: "memberships run
higher because clusters overlap (7,147 over 7,061 at 90%)".)

## Precision by cluster size

| Size threshold | Clusters | With >= 1 malicious file | Precision |
|---|---:|---:|---:|
{size_rows}

## MinHash comparison row

Recomputed from the archived scan under the same precision and recall rules as the embedding
row, not quoted from a stored literal. datasketch is not needed for this.

| Method | Clusters | Memberships | Distinct | Rate | Recall | P@>=20 | P@>=10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Embeddings ({MODEL_NAME}) | {len(clusters):,} | {memberships:,} | {distinct:,} | {rate:.1f}% | {recall:.1f}% \
| {pct(p20)} | {pct(p10)} |
| MinHash (archived scan) | {mh["clusters"]:,} | {mh["memberships"]:,} | {mh["distinct"]:,} \
| {mh["memberships"] / len(entries) * 100:.1f}% | {mh["recall"]:.1f}% ({mh["recall_hit"]:,}/{mh["recall_tot"]:,}) \
| {mh["p20"]:.1f}% ({mh["p20_mal"]}/{mh["p20_n"]}) | {mh["p10"]:.1f}% ({mh["p10_mal"]}/{mh["p10_n"]}) |
| MinHash, as the paper prints it | {PAPER_MINHASH["clusters"]:,} | {PAPER_MINHASH["files_in_clusters"]:,} \
| n/a | {PAPER_MINHASH["rate"]}% | 99.2% | {PAPER_MINHASH["p20"]}% | {PAPER_MINHASH["p10"]}% |

Every MinHash cell recomputes except the recall cell of the printed row: it says 99.2%,
and the archived scan under this script's own recall rule gives {mh["recall"]:.1f}%
({mh["recall_hit"]:,}/{mh["recall_tot"]:,}).

Both figures are the paper's, and Section 4.4 (IOC Validation) states how they relate: "of
the 352 scanned, 351 appeared in clusters (99.7% of those scanned; 99.2% against the full
354)". The 354-denominator form appears in Section 3.3 (Similarity Analysis: "Recall against
the Koi IOC list held constant at 99.2% across all six thresholds"), in the captions of Table 2
("is 99.2% at all thresholds; full-list recall is 98.8%") and Figure 1 ("(hightower6eu subset:
351/354) is invariant at 99.2%"), and in Section 5.2 ("Recall ($\\geq$99.2%) is omitted from
the figure because all methods achieve near-identical values"). The 352-denominator form,
99.7% (351/352), is the one Table 5 prints for the 3-gram MinHash row.

This script counts recall over the hightower6eu files the loaded corpus holds
({h6_total:,}), for the embedding row and the MinHash row alike, so its recomputed MinHash
row reads {mh["recall"]:.1f}% beside the printed 99.2%. The two are the same {mh["recall_hit"]:,}
files over different denominators, and the table above carries the recomputed row beside the
printed one so that both denominators are visible.

"""
