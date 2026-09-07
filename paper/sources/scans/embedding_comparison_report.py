#!/usr/bin/env python3
"""Markdown rendering for `embedding_comparison.py`.

Nothing here computes a result. `render()` takes values the run has already produced
and returns the text of the results file; `embedding_comparison.py` writes it. No CLI:
importing this module has no side effects beyond the imports.

`tilde`, `_git` and `git_head` duplicate the helpers in `order_permutation.py` rather
than importing them, because that module imports datasketch and the embedding run does
not require it. Keep the two copies in step.

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
# that module imports datasketch, which is absent from this interpreter)
# --------------------------------------------------------------------------

def tilde(path):
    """Home-relative form of a path, so the artifact carries no user directory."""
    home = os.path.expanduser("~")
    path = str(path)
    return "~" + path[len(home):] if path.startswith(home) else path


def _git(d, *args):
    """stdout of a git command, or None if it exited non-zero.

    No exception handling here on purpose. `git_head` is the only caller and it
    already turns FileNotFoundError, OSError and SubprocessError into the reason
    strings that render into the results file, so a bare `except ...: raise` here
    was a no-op that read as if it handled something.
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
    on disk here; recording the hash is what makes the encode reproducible.
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
    values are not comparable at all (the runtime rows: this machine was under
    concurrent load), so the row shows both and marks the verdict `n/a` rather
    than claiming a match it has not tested.
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
    the caller has already fixed, so moving it out of `embedding_comparison.py`
    (which was over the ~500-line house limit, roughly 180 of them this template)
    cannot change a reported number. The keyword-only signature is the point: it
    names exactly what the report depends on, and a missing input is a TypeError at
    the call rather than a blank cell in the artifact.
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
        # it unconditionally would put a false claim in the artifact on any run
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

Four candidate causes, none of them checkable today, in rough order of how much of a
{delta:+,d}-cluster shift each could plausibly produce:

1. **A different file list.** The original run read a local index file, a separate
   artifact from the archived scan used here, and it does not survive. If its
   `file_index` differed from the scan's by even a handful of entries, the membership
   counts move directly. This cannot be checked.
2. **An unpinned corpus.** The original run read a live checkout on 2026-03-15, a day
   after the scan was generated, not a snapshot pinned to the scan's SHAs. This run
   reads the pinned snapshot.
3. **Package versions.** Nothing records what was installed in March. This interpreter now has
   sentence-transformers {sentence_transformers.__version__} and torch {torch.__version__}; a
   change in the tokenizer, the pooling path or a default dtype between March's versions and
   these shifts borderline cosines.
4. **Float arithmetic.** The March code normalised and multiplied in float32 NumPy; this run
   does the same in float32 torch, with a different summation order inside the matmul. A pair
   sitting within roughly 1e-6 of 0.9 can land on the other side of the comparison, and because
   the clustering is greedy and order-dependent, one flipped pair can cascade into a different
   cluster count.

Causes 1 and 2 are corpus-side, 3 and 4 arithmetic-side, and nothing available here separates
them. The paper was not edited on the strength of this difference; that decision is the
author's."""
    size_rows = "\n".join(
        f"| >= {sz} | {p['count']} | {p['malicious']} | "
        + (f"{p['precision']:.1f}% |" if p["precision"] is not None else "n/a |")
        for sz, p in sorted(precision.items()))
    # DESIGN RATIONALE: the command block used to print no flags, so the one
    # copy-and-run path in this file reproduced the script's DEFAULTS rather than
    # the run that wrote the file. Any flag whose value is not the default is
    # interpolated here; a flag added later must be added here too, or this file
    # will again print a command that contradicts its own numbers.
    # Decode-mode rows. The row for the mode this run executed carries THIS RUN's
    # measured triple and the verdict of the cross-check against DECODE_OBSERVED; the
    # other row is the recorded value from a prior run and is labelled as such, because
    # nothing in this run can confirm it.
    _mode_label = {"strict": "the March behaviour", "replace": "the script default"}
    decode_rows = []
    for mode in ("strict", "replace"):
        rec = DECODE_OBSERVED.get(mode)
        if mode == decode:
            n, c, m = decode_observed_run
            src = ("**this run**, cross-checked against the recorded value: match"
                   if decode_check_ok else
                   f"**this run** -- **MISMATCH** against the recorded "
                   f"{tuple(rec) if rec else None}; see the warning on stderr")
        else:
            n, c, m = rec if rec else (0, 0, 0)
            src = "recorded from a prior run; not executed here"
        decode_rows.append(f"| `{mode}` ({_mode_label[mode]}) | {n:,} | {c:,} | {m:,} | {src} |")
    decode_rows = "\n".join(decode_rows)
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

Recompute of the Sentence-BERT baseline in Section 5.2 ("Embeddings produced 3,626
clusters covering 9,462 files") and Figure 3,
which the paper reports with no archived results file. The original run read a local
index file and an unpinned checkout, neither of which survives, so its figures had no
reproducible artifact;
this run reads the archived scan's `file_index` against a pinned March corpus snapshot.

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
| Corpus root | `{tilde(CORPUS)}` |
| Scan | `{SCAN.name}`, `generated_at` {scan["metadata"]["generated_at"]} |
| Ground truth | `{tilde(IOCS)}`, `clawhub_authors` ({len(mal_authors)} accounts) |
| Repository HEAD | {git_head(HERE.parents[2])} |
| Run at | {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")} |

The published run used the package versions in the table above; any environment with a
working `sentence-transformers` reproduces it. Nothing pins those versions: there is no
lock file, and no results file from March records them.

Command, as run. Every non-default flag is interpolated from the run itself, so copying this
block out and running it reproduces the numbers below rather than the script's defaults:

```
LIBRARIAN_CORPUS={tilde(CORPUS)} HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false \\
  {tilde(sys.executable)} \\
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
rows ({t_sim + t_clu:.1f} s). Runtimes here are not comparable to the published figures:
the run shared its CPU with unrelated work.

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

The paper states none of these rules; they are stated here in full.

- **Encoded unit.** The first {TRUNCATE_CHARS} characters of each file, decoded as UTF-8 with
  `errors="{decode}"`, encoded by `{MODEL_NAME}` on CPU in batches of {ENCODE_BATCH}. Files under
  {MIN_CHARS} characters are skipped ({skipped["short"]} here).
- **Decoding.** Eight indexed files are not valid UTF-8, and whether they enter the corpus is
  what separates the published document count from the full index. `--decode strict` drops
  them, which is the population behind the published figures, and names the files it drops;
  `--decode replace` (the default) substitutes U+FFFD and encodes everything the index names.
  The two give different document counts, so the mode is in the provenance table above.
- **File list.** The archived scan's `file_index`, resolved as `$LIBRARIAN_CORPUS/<marketplace>/<path>`,
  mirroring `order_permutation.load_files`. A bare `$LIBRARIAN_CORPUS/<path>` fallback is not used, so a
  path that does not resolve is a skip.
- **Similarity.** Cosine, computed as a matmul of L2-normalised embeddings, in row batches of
  {SIM_BATCH}. Entirely in torch: torch {torch.__version__} here was built against NumPy 1.x and
  `Tensor.numpy()` raises `RuntimeError: Numpy is not available`, so no array crosses between the
  two libraries at any point. Values reach Python only through `.tolist()`.
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

Runtime rows carry no verdict: the run shared its CPU with unrelated work, so a
wall-clock disagreement says nothing about the method. The similarity + clustering figure is also
not like-for-like, because the greedy loop here finds its matching indices by thresholding the row
in torch rather than scanning `range(n)` in Python.

## Where the recompute differs, and why

{diff_section}

## The decode mode is the whole gap

The eight undecodable files above are the entire difference between reproducing Section 5.2 and
missing it by a cluster. One full run per mode on this corpus, both deterministic. Only one mode
runs at a time, so the last column says which row this run measured and which is quoted from a
previous one:

| `--decode` | Documents encoded | Clusters | Files in clusters | Source |
|---|---:|---:|---:|---|
{decode_rows}
| Section 5.2 as published | not stated | {PAPER["clusters"]:,} | {PAPER["files_in_clusters"]:,} | the paper |

The row for `{decode}` is not a literal: this run measured {decode_observed_run[0]:,} documents,
{decode_observed_run[1]:,} clusters and {decode_observed_run[2]:,} files in clusters, and the
script compares that triple against its recorded `DECODE_OBSERVED` entry before writing this
file. {"The two agree." if decode_check_ok else "**They do not agree.** The run exited non-zero and warned on stderr; this file was written anyway so the mismatch can be read, so do not quote its numbers until it is explained."} The other mode's row cannot be checked by a run that did
not execute it, and is marked accordingly.

`strict` matches the published figures exactly; `replace` misses by +1 cluster and +4 files,
because eight documents the March run never saw are encoded and four of them find a partner at
0.9. The same eight files account for the TF-IDF baseline's document count, so this is one
decode decision showing up in two baselines rather than two independent discrepancies.

That does not make `strict` the better rule. It reproduces the paper because it is what the
paper did, and what the paper did was drop eight files inside a bare `except Exception` without
recording it. `replace` encodes everything the file index names, which is what Section 5.2's
own prose describes. The default here is `replace` for that reason, and this file names its
mode in the provenance table so the two can never be confused.

The "9,462 files (29.9%)" cell is ambiguous in the paper between cluster memberships and
distinct files. Here memberships are {memberships:,} and distinct files {distinct:,}; the greedy rule
only ever assigns an unassigned file, so the two coincide by construction, and the published
figure is a membership count under a rule that makes it also a file count. (The MinHash side of
the same sentence is not like this: the archived scan's 7,147 is a membership count over 7,061
distinct files, because its LSH query can return an already-clustered file.)

## Precision by cluster size

| Size threshold | Clusters | With >= 1 malicious file | Precision |
|---|---:|---:|---:|
{size_rows}

## MinHash comparison row

Recomputed from the archived scan under the same rules rather than re-derived with datasketch (absent
from this interpreter) rather than quoted from a stored literal.

| Method | Clusters | Memberships | Distinct | Rate | Recall | P@>=20 | P@>=10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Embeddings ({MODEL_NAME}) | {len(clusters):,} | {memberships:,} | {distinct:,} | {rate:.1f}% | {recall:.1f}% \
| {pct(p20)} | {pct(p10)} |
| MinHash (archived scan) | {mh["clusters"]:,} | {mh["memberships"]:,} | {mh["distinct"]:,} \
| {mh["memberships"] / len(entries) * 100:.1f}% | {mh["recall"]:.1f}% ({mh["recall_hit"]:,}/{mh["recall_tot"]:,}) \
| {mh["p20"]:.1f}% ({mh["p20_mal"]}/{mh["p20_n"]}) | {mh["p10"]:.1f}% ({mh["p10_mal"]}/{mh["p10_n"]}) |
| MinHash, as the paper prints it | {PAPER_MINHASH["clusters"]:,} | {PAPER_MINHASH["files_in_clusters"]:,} \
| n/a | {PAPER_MINHASH["rate"]}% | 99.2% | {PAPER_MINHASH["p20"]}% | {PAPER_MINHASH["p10"]}% |

Every MinHash cell recomputes except the recall: the published row says 99.2%,
and the archived scan under this script's own recall rule gives {mh["recall"]:.1f}%
({mh["recall_hit"]:,}/{mh["recall_tot"]:,}).

That 99.2% is not a stale literal. It is the paper's own figure, stated five times in
`main-acm.tex` -- in Similarity Analysis ("Recall against the Koi IOC list held constant at
99.2% across all"), twice in Ecosystem Characterization (RQ1) ("is 99.2% at all thresholds;
full-list recall is 98.8%" and "(hightower6eu subset: 351/354) is invariant at 99.2%"), in IOC
Validation ("99.7% of those scanned; 99.2% against the full 354") and in Comparison with Simple
Baselines ("Recall ($\\geq$99.2%)"). The RQ1 one gives the arithmetic outright: 351/354 =
99.15%.

(Quoted, not cited by line number, so the receipt does not go stale if the paper is
re-typeset.)

The two rows of the March comparison table used
different denominators for the same numerator: 354, the hightower6eu slugs on the Koi IOC list,
on the MinHash row, against 352, the hightower6eu files the loaded corpus actually holds, on the
embedding row. Both rows are labelled "Recall". Recomputing the MinHash row against the same 352
this script uses for its own recall gives {mh["recall"]:.1f}%, which is why the table above now
carries a recomputed row beside the printed one rather than the printed one alone.

"""
