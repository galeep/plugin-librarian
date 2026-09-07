"""Shingle size ablation: 2-gram, 3-gram and 4-gram word shingles.

Runs MinHash/LSH clustering at the 90% Jaccard threshold with each shingle size and
scores precision and recall against the IOC account list. It reproduces Table 5
(`tab:shingle-ablation`, "Shingle size ablation at 90% Jaccard threshold.") and
supports the sentence in Section 5.2 that introduces it: "We repeated the MinHash
analysis with 2-gram and 4-gram word shingles (Table 5)." Shingling, MinHash
parameters, LSH threshold, greedy clustering and the precision and recall
definitions are those Section 3.3 describes.

Inputs. LIBRARIAN_CORPUS (required) names the corpus snapshot recorded in
paper/supplementary/repository-commits.md. The file list is the `file_index` of
`scan_20260314_threshold90_skillonly.json`, beside this script, resolved through
`order_permutation.load_files`. Account ground truth is read from `paper/iocs.json`
and asserted at startup to equal MARCH_MALICIOUS_AUTHORS, the eleven accounts
Table 5 was computed with, so an edit to iocs.json cannot silently redefine the
published precision.

Output: `shingle-ablation-<UTC date>.md` beside this script, or the full path in
SCAN_RESULTS_OUT. A second run on the same UTC day overwrites the day's file. The
report compares every cell against Table 5 as printed.

Run, with LIBRARIAN_CORPUS set:
  python paper/sources/scans/shingle_ablation.py
"""

import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
# The scans directory is sys.path[0] when this file is run as a script, but not
# when it is imported, so name it explicitly before importing a sibling.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from datasketch import MinHash, MinHashLSH
from librarian.core import NUM_PERM, tokenize
from order_permutation import CORPUS as OP_CORPUS
from order_permutation import git_head, load_files, provenance, require_corpus, tilde

THRESHOLD = 0.9
SHINGLE_SIZES = [2, 3, 4]
CORPUS = Path(require_corpus())
REPO = Path(__file__).resolve().parents[3]
SCAN = Path(__file__).with_name("scan_20260314_threshold90_skillonly.json")
IOCS = REPO / "paper" / "iocs.json"
# DESIGN RATIONALE (shared with order_permutation.py): the default output name
# carries today's UTC date, so a rerun cannot overwrite a tracked results file from
# another day. A same-day rerun overwrites the day's file unless SCAN_RESULTS_OUT
# (a full path) is set.
_DEFAULT_OUT_NAME = "shingle-ablation-{}.md".format(
    datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d"))
OUT = Path(os.environ["SCAN_RESULTS_OUT"]) if os.environ.get("SCAN_RESULTS_OUT") \
    else Path(__file__).with_name(_DEFAULT_OUT_NAME)

# The eleven ClawHub accounts that the precision columns of Table 5 count as
# malicious. `clawhub_authors` in iocs.json is asserted equal to this set at
# startup, so an edit to iocs.json cannot silently redefine the published precision.
MARCH_MALICIOUS_AUTHORS = frozenset({
    "hightower6eu", "sakaen736jih", "thiagoruss0", "zaycv",
    "jordanprater", "stveenli", "anisafifi", "timclawbot",
    "kenblive", "mupengi-bot", "moonshine-100rze",
})
RECALL_AUTHOR = "hightower6eu"

# Table 5 of the paper as printed, for the comparison table:
# size -> (clusters, memberships, recall_found, recall_total, p20_tp, p20_n,
#          p10_tp, p10_n).
PAPER_TABLE5 = {
    2: (2693, 7344, 351, 352, 14, 14, 28, 37),
    3: (2622, 7147, 351, 352, 11, 11, 30, 38),
    4: (2539, 6939, 351, 352, 14, 15, 27, 33),
}


def tokenize_with_size(text, shingle_size):
    """Tokenize text using word-level n-grams of given size."""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'[^a-z0-9\s\-]', '', text)
    words = [w for w in text.split() if w]

    if len(words) < shingle_size:
        if words:
            return set(words)
        elif len(text) >= shingle_size:
            return set(text[i:i+shingle_size] for i in range(len(text) - shingle_size + 1))
        else:
            return {text} if text else set()

    shingles = set()
    for i in range(len(words) - shingle_size + 1):
        shingle = ' '.join(words[i:i + shingle_size])
        shingles.add(shingle)
    return shingles


def get_author(path):
    """Extract author from clawhub-archive path."""
    parts = path.split("/")
    if parts[0] == "skills" and len(parts) >= 3:
        return parts[1]
    return None


def load_iocs_authors():
    """Malicious account list for precision, read from paper/iocs.json.

    The rule is the keys of `clawhub_authors`, the accounts this study confirmed
    by payload inspection. It is not the rule file_level_precision.py uses, so
    nothing is imported from that script: its `strict` set is Antiy CERT's 12
    documented accounts, its `study` set is the union of those with
    `clawhub_authors` (18 accounts), and its `account_of` additionally requires
    marketplace == "clawhub-archive" and a four-segment path. Substituting either
    would change the Table 5 numbers, so this script applies its own rule.
    """
    iocs = json.loads(IOCS.read_text())
    authors = frozenset(iocs["clawhub_authors"])
    if authors != MARCH_MALICIOUS_AUTHORS:
        raise ValueError(
            f"iocs.json clawhub_authors does not match the account list Table 5 was computed with; "
            f"only in iocs.json: {sorted(authors - MARCH_MALICIOUS_AUTHORS)}, "
            f"only in MARCH_MALICIOUS_AUTHORS: {sorted(MARCH_MALICIOUS_AUTHORS - authors)}")
    return authors


def run_with_shingle_size(file_index, shingle_size):
    """Run full clustering pipeline with a specific shingle size."""
    t0 = time.time()
    lsh = MinHashLSH(threshold=THRESHOLD, num_perm=NUM_PERM)

    minhashes = {}
    metadata = {}
    skipped = {"missing": 0, "short": 0, "empty": 0}

    for i, (market, rel) in enumerate(file_index):
        # Only <marketplace>/<relative> is a real corpus path; see
        # order_permutation.signatures for why there is no bare-CORPUS fallback.
        p = CORPUS / market / rel
        if not p.exists():
            skipped["missing"] += 1
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if len(text) < 100:
            skipped["short"] += 1
            continue

        shingles = tokenize_with_size(text, shingle_size)
        if not shingles:
            skipped["empty"] += 1
            continue

        m = MinHash(num_perm=NUM_PERM)
        for s in shingles:
            m.update(s.encode('utf-8'))
        minhashes[i] = m
        metadata[i] = {"marketplace": market, "path": rel}
        lsh.insert(str(i), m)

    # Build clusters (greedy first-match, same as production)
    assigned = set()
    clusters = []

    for i in sorted(minhashes.keys()):
        if i in assigned:
            continue
        result = lsh.query(minhashes[i])
        similar = set(int(r) for r in result)
        if len(similar) > 1:
            clusters.append(similar)
            assigned.update(similar)

    t1 = time.time()
    return clusters, metadata, t1 - t0, len(minhashes), skipped


def evaluate(clusters, metadata, malicious_authors):
    """Compute precision at size thresholds and recall."""
    # Precision at size thresholds
    size_thresholds = [5, 10, 15, 20]
    precision = {}

    for min_size in size_thresholds:
        large = [c for c in clusters if len(c) >= min_size]
        if not large:
            precision[min_size] = (None, 0, 0)
            continue
        mal = 0
        for cluster in large:
            for idx in cluster:
                fi = metadata.get(idx)
                if fi:
                    author = get_author(fi["path"])
                    if author and author in malicious_authors:
                        mal += 1
                        break
        precision[min_size] = (mal / len(large) * 100, mal, len(large))

    # Recall: hightower6eu files in clusters
    clustered = set()
    for c in clusters:
        clustered.update(c)

    h6_total = 0
    h6_found = 0
    for i, fi in metadata.items():
        author = get_author(fi["path"])
        if author == RECALL_AUTHOR:
            h6_total += 1
            if i in clustered:
                h6_found += 1

    recall = h6_found / h6_total * 100 if h6_total else 0
    return precision, recall, h6_found, h6_total


def self_test() -> int:
    """Pin the shingle function to exact expected sets before any run.

    DESIGN RATIONALE: every number in Table 5 is a function of this one routine,
    and a silent change to the normalization (the punctuation class, the
    short-document fallback) would move all three rows at once while still
    producing a plausible-looking table. The expected sets are written out by
    hand rather than derived from the code. The last check pins the 3-gram case
    to librarian.core.tokenize, the production tokenizer that built the archived
    scan, since the 3-gram row is required to reproduce that scan exactly.
    """
    text = "The Quick, brown fox!  jumps"          # normalizes to "the quick brown fox jumps"
    expected = {
        2: {"the quick", "quick brown", "brown fox", "fox jumps"},
        3: {"the quick brown", "quick brown fox", "brown fox jumps"},
        4: {"the quick brown fox", "quick brown fox jumps"},
    }
    for size, want in expected.items():
        got = tokenize_with_size(text, size)
        if got != want:
            print(f"self-test FAILED: {size}-gram shingles of {text!r} were {sorted(got)}, "
                  f"expected {sorted(want)}", file=sys.stderr)
            return 1
    # Short-document fallback: fewer words than the shingle size returns the
    # words themselves, not an empty set.
    if tokenize_with_size("alpha beta", 4) != {"alpha", "beta"}:
        print("self-test FAILED: short-document fallback did not return the bare words",
              file=sys.stderr)
        return 1
    if tokenize_with_size(text, 3) != tokenize(text):
        print("self-test FAILED: the 3-gram case does not agree with librarian.core.tokenize, "
              "so the 3-gram row cannot be the archived scan's configuration", file=sys.stderr)
        return 1
    return 0


def datasketch_version():
    try:
        from importlib.metadata import version
        return version("datasketch")
    except Exception as exc:                     # noqa: BLE001 - reported, never swallowed
        return f"unknown ({exc.__class__.__name__})"


def rerun_command():
    """The run line as printed in the report. LIBRARIAN_CORPUS is named once, in
    the sentence that introduces it, not repeated on the command."""
    return f"python paper/sources/scans/{Path(__file__).name}"


def environment_table(results):
    lines = ["| item | value |", "|---|---|",
             f"| corpus root | `{tilde(CORPUS)}`"
             + ("" if os.environ.get("LIBRARIAN_CORPUS") else " (LIBRARIAN_CORPUS unset; default)")
             + " |",
             f"| repository HEAD | {git_head(REPO)} |",
             f"| input scan | `{SCAN.name}` |",
             f"| ground truth | `{tilde(IOCS)}` |",
             f"| python | {sys.version.split()[0]} ({tilde(sys.executable)}) |",
             f"| datasketch | {datasketch_version()} |",
             f"| num_perm | {NUM_PERM} (default datasketch seed) |",
             f"| LSH threshold | {THRESHOLD} |",
             f"| command | `{rerun_command()}` |"]
    for size in SHINGLE_SIZES:
        lines.append(f"| runtime, {size}-gram | {results[size]['runtime']:.1f} s |")
    return lines


def comparison_rows(results):
    """Rows comparing this run against Table 5, plus the count of mismatches."""
    rows, mismatches = [], 0
    for size in SHINGLE_SIZES:
        r = results[size]
        p20, p10 = r["precision"][20], r["precision"][10]
        paper = PAPER_TABLE5[size]
        mine = (r["clusters"], r["files_in_clusters"], r["h6_found"], r["h6_total"],
                p20["mal"], p20["total"], p10["mal"], p10["total"])
        cells = [
            ("clusters", f"{paper[0]:,}", f"{mine[0]:,}"),
            ("memberships", f"{paper[1]:,}", f"{mine[1]:,} ({r['cluster_rate']:.1f}%)"),
            ("recall", f"{paper[2]}/{paper[3]}", f"{mine[2]}/{mine[3]} ({r['recall']:.1f}%)"),
            ("P@>=20", f"{paper[4]}/{paper[5]}", f"{mine[4]}/{mine[5]}"
             + (f" ({p20['value']:.1f}%)" if p20["value"] is not None else " (n/a)")),
            ("P@>=10", f"{paper[6]}/{paper[7]}", f"{mine[6]}/{mine[7]}"
             + (f" ({p10['value']:.1f}%)" if p10["value"] is not None else " (n/a)")),
        ]
        # Match on the integers, not on the rounded percentages: two different
        # counts can print the same one-decimal rate.
        agree = [paper[0] == mine[0], paper[1] == mine[1],
                 (paper[2], paper[3]) == (mine[2], mine[3]),
                 (paper[4], paper[5]) == (mine[4], mine[5]),
                 (paper[6], paper[7]) == (mine[6], mine[7])]
        for (label, pv, mv), ok in zip(cells, agree):
            rows.append((f"{size}-gram", label, pv, mv, "yes" if ok else "**NO**"))
            mismatches += 0 if ok else 1
    return rows, mismatches


def archived_check(scan, results):
    """The 3-gram row is the archived scan's own configuration; hold it to that.

    DESIGN RATIONALE: 3-gram shingles with num_perm 128 at threshold 0.9 are
    exactly what produced scan_20260314_threshold90_skillonly.json, so any
    difference in the 3-gram row means the corpus or the pipeline moved, and
    every other row in the table is then unanchored. Returned as a breach so it
    reaches the exit status, not only the markdown.
    """
    ref = scan.get("summary", {})
    ref_clusters, ref_files = ref.get("unique_clusters"), ref.get("files_in_clusters")
    if ref_clusters is None or ref_files is None:
        raise ValueError(
            f"{SCAN.name} carries no cluster counts in its `summary`; the 3-gram row "
            "cannot be checked against the archived scan.")
    got = results[3]
    ok = got["clusters"] == ref_clusters and got["files_in_clusters"] == ref_files
    lines = [f"Archived {scan['metadata']['generated_at'][:10]} scan (3-gram, the production "
             f"configuration): {ref_clusters:,} clusters, {ref_files:,} memberships. "
             f"This run's 3-gram row: {got['clusters']:,} clusters, "
             f"{got['files_in_clusters']:,} memberships. "
             + ("Exact reproduction." if ok else "**These differ.**")]
    if not ok:
        lines += ["", "**The 3-gram row does not reproduce the archived scan, so the corpus in "
                  f"use is not the one that scan was built from.** Corpus: `{tilde(CORPUS)}`; "
                  "compare the snapshot table above against paper/supplementary/"
                  "repository-commits.md. The 2-gram and 4-gram rows are internally comparable "
                  "to this 3-gram baseline but none of them are the paper's numbers."]
    return lines + [""], not ok


def main() -> int:
    malicious_authors = load_iocs_authors()
    scan = json.loads(SCAN.read_text())
    file_index = load_files(scan)
    if OP_CORPUS != CORPUS:
        print(f"corpus mismatch: this script resolved {CORPUS}, the imported provenance "
              f"helpers resolved {OP_CORPUS}", file=sys.stderr)
        return 1
    print(f"Files in the archived scan index: {len(file_index)}")

    results = {}
    for size in SHINGLE_SIZES:
        print(f"\n{'='*60}")
        print(f"Running with shingle_size={size} (word-level {size}-grams)")
        print(f"{'='*60}")

        clusters, metadata, runtime, n_files, skipped = run_with_shingle_size(
            file_index, size)
        if not n_files:
            print("no signatures computed; corpus path or file_index keys are wrong",
                  file=sys.stderr)
            return 1
        files_in_clusters = sum(len(c) for c in clusters)

        print(f"  Files processed: {n_files} (skipped {skipped['missing']} missing, "
              f"{skipped['short']} short, {skipped['empty']} empty)")
        print(f"  Clusters: {len(clusters)}")
        print(f"  Memberships: {files_in_clusters} ({files_in_clusters/n_files*100:.1f}%)")
        print(f"  Runtime: {runtime:.1f}s")

        precision, recall, h6_found, h6_total = evaluate(clusters, metadata, malicious_authors)

        print(f"  Recall ({RECALL_AUTHOR}): {h6_found}/{h6_total} ({recall:.1f}%)")
        print("  Precision by cluster size:")
        for sz in sorted(precision.keys()):
            p, mal, total = precision[sz]
            if p is not None:
                print(f"    >= {sz}: {p:.1f}% ({mal}/{total})")
            else:
                print(f"    >= {sz}: N/A (0 clusters)")

        results[size] = {
            "clusters": len(clusters),
            "files_in_clusters": files_in_clusters,
            "cluster_rate": files_in_clusters / n_files * 100,
            "runtime": runtime,
            "recall": recall,
            "h6_found": h6_found,
            "h6_total": h6_total,
            "n_files": n_files,
            "skipped": skipped,
            "precision": {sz: {"value": p, "mal": m, "total": t}
                          for sz, (p, m, t) in precision.items()},
        }

    any3 = results[3]
    lines = ["# Shingle size ablation (90% Jaccard threshold, SKILL.md only)", "",
             f"This file reports MinHash/LSH clustering of the SKILL.md corpus at the 90% "
             f"Jaccard threshold with 2-gram, 3-gram and 4-gram word shingles, with precision "
             f"and recall for each size. It reproduces Table 5 of the paper "
             f"(`tab:shingle-ablation`, \"Shingle size ablation at 90% Jaccard threshold.\") "
             f"and supports the sentence in Section 5.2 that introduces the table: \"We "
             f"repeated the MinHash analysis with 2-gram and 4-gram word shingles (Table 5).\" "
             f"The paragraph continues: \"All three sizes found the same 351 hightower6eu "
             f"files in clusters (99.7% of 352 in the corpus). Precision varies: 2-grams "
             f"produce more topical false positives (P@>=10: 75.7% vs. 78.9%), while 4-grams "
             f"fragment one campaign, dropping P@>=20 to 93.3%. The 3-gram default maximizes "
             f"precision.\"", "",
             f"Generated by `{Path(__file__).name}`. Run, with `LIBRARIAN_CORPUS` set, from the "
             f"repository root: `{rerun_command()}`. `LIBRARIAN_CORPUS` names the corpus "
             f"snapshot and has no default; a run without it stops before computing anything. "
             f"Output defaults to `shingle-ablation-<UTC date>.md` beside the script; set "
             f"`SCAN_RESULTS_OUT` to a full path to write elsewhere.", "",
             f"The file list is the `file_index` of the committed scan `{SCAN.name}`, and paths "
             f"resolve under `LIBRARIAN_CORPUS`. The shingling, MinHash parameters, LSH "
             f"threshold, greedy clustering, and the precision and recall definitions are those "
             f"Section 3.3 describes; only the shingle size varies between rows.", "",
             f"Files with signatures: {any3['n_files']} of {len(file_index)}. Skipped "
             f"{any3['skipped']['missing']} not present in the corpus, {any3['skipped']['short']} "
             f"shorter than 100 characters, {any3['skipped']['empty']} that produced no shingles "
             f"(3-gram run; the other sizes are reported in the results table).", "",
             "## Provenance", ""]
    lines += environment_table(results)
    lines += [""]
    lines += provenance(scan)

    lines += ["## Ground truth rules", "",
              f"**Recall.** Denominator: every file with a signature whose ClawHub archive path "
              f"is `skills/{RECALL_AUTHOR}/...`, read off the path (second segment of a path "
              f"whose first segment is `skills`). Numerator: those of them in any cluster. "
              f"This is a corpus-file count, not the 354 IOC slugs of Table 2, as the caption "
              f"of Table 5 states.",
              "",
              f"**Precision.** A cluster of at least the stated size counts as a true positive "
              f"if at least one of its files has a path-derived account in the "
              f"{len(malicious_authors)} accounts of `clawhub_authors` in `paper/iocs.json` "
              f"({', '.join(sorted(malicious_authors))}). The list is read from iocs.json and "
              f"asserted equal to the eleven accounts built into the script, which exits before "
              f"running if the two disagree.",
              "",
              "**Not file_level_precision.py's rule.** That script scores `strict` (Antiy CERT's "
              "12 documented accounts) and `study` (the union of those with `clawhub_authors`, "
              "18 accounts), and its `account_of` also requires the marketplace to be "
              "`clawhub-archive` and the path to have four segments. Neither set nor the gate "
              "is the rule Table 5 was computed with, so nothing is imported from it and this "
              "script applies its own rule.", "",
              "## Results", "",
              "| Shingle | Clusters | Memberships | Recall | P@>=20 | P@>=15 | P@>=10 | P@>=5 | "
              "Files with signatures | Runtime |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for size in SHINGLE_SIZES:
        r = results[size]

        def cell(sz, r=r):
            p = r["precision"][sz]
            return "n/a" if p["value"] is None else f"{p['value']:.1f}% ({p['mal']}/{p['total']})"

        lines.append(
            f"| {size}-gram | {r['clusters']:,} | {r['files_in_clusters']:,} "
            f"({r['cluster_rate']:.1f}%) | {r['recall']:.1f}% ({r['h6_found']}/{r['h6_total']}) | "
            f"{cell(20)} | {cell(15)} | {cell(10)} | {cell(5)} | {r['n_files']:,} | "
            f"{r['runtime']:.1f} s |")

    rows, mismatches = comparison_rows(results)
    lines += ["", "## Comparison against Table 5 as published", "",
              "Percentages are shown for reading; the match column compares the underlying "
              "integer counts, since two different counts can print the same one-decimal rate.", "",
              "| Shingle | Cell | Paper Table 5 | This rerun | Match |",
              "|---|---|---:|---:|---|"]
    for size_label, label, pv, mv, ok in rows:
        lines.append(f"| {size_label} | {label} | {pv} | {mv} | {ok} |")
    lines += ["", f"{len(rows) - mismatches} of {len(rows)} cells match."
              + ("" if mismatches == 0 else
                 f" **{mismatches} differ; the rows above marked NO are not reproduced.**"), "",
              "## 3-gram reproduction check", ""]

    check_lines, breach = archived_check(scan, results)
    lines += check_lines

    OUT.write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))
    # DESIGN RATIONALE: the archived-scan check anchors the 3-gram row only, so a run
    # in which just the 2-gram or 4-gram row moved would write a results file full of
    # **NO** rows and still exit 0. Any disagreement with PAPER_TABLE5 is therefore a
    # failure in its own right, and the two causes are reported separately so the exit
    # status says which one fired.
    if breach:
        print("the 3-gram row does not reproduce the archived scan; the corpus is not the one "
              "that scan was built from", file=sys.stderr)
    if mismatches:
        print(f"{mismatches} of {len(rows)} cells disagree with Table 5 as published; see the "
              f"comparison table in {OUT.name}", file=sys.stderr)
    return 1 if (breach or mismatches) else 0


if __name__ == "__main__":
    rc = self_test()
    sys.exit(rc or main())
