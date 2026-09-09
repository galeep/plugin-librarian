#!/usr/bin/env python3
"""File-order permutation sensitivity of the greedy first-match clusterer.

Supports the ordering-sensitivity result of Section 3.3 (Similarity Analysis),
which reports a range of adjusted Rand index scores over ten shuffles of the
assignment order with the signatures held fixed, and Section 6 (Limitations),
which repeats that range. Both endpoints are the minimum and maximum of the
adjusted Rand column this script writes.

Method. MinHash signatures are computed once with the default datasketch seed.
The greedy assignment loop is then run in sorted file-index order (the baseline)
and in K = 10 shuffled orders. For each shuffle the script reports the cluster
count, the Rand index and adjusted Rand index against the baseline, and the
share of baseline clusters reproduced as the identical set of files.

Inputs. LIBRARIAN_CORPUS (required) names the root of the pinned corpus
snapshot; paper/supplementary/repository-commits.md lists its SHAs. The file
list is the `file_index` of `scan_20260314_threshold90_skillonly.json`, beside
this script. Parameters: 0.9 LSH threshold, 128 permutations, 3-word shingles,
100-character minimum, K = 10 shuffles seeded 1000 + k.

Output. `order-permutation-<UTC date>.md` beside this script, or the full path
in SCAN_RESULTS_OUT. A second run on the same UTC day overwrites the day's
file. The shipped result is `order-permutation-20260907.md`.

`load_files`, `signatures`, `greedy`, `git_head`, `provenance`, `require_corpus`
and `tilde` are imported by `backup_slug_check.py`, `shingle_ablation.py`,
`tfidf_comparison.py` and `exact_hash_baseline.py`, and `cluster_gap_recompute.py`
imports the module whole, so those runs resolve the same file list from the same
snapshot. Changing them changes those results too. The published-commit rule is
not here: `repo_provenance.py` holds it, and each script imports it from there.

Run, with LIBRARIAN_CORPUS set:
  python paper/sources/scans/order_permutation.py
"""
import datetime, json, math, os, random, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from datasketch import MinHash, MinHashLSH
from librarian.core import tokenize, NUM_PERM

THRESHOLD = 0.9
K = 10

def require_corpus():
    """Corpus root from LIBRARIAN_CORPUS, or exit; there is no default.

    DESIGN RATIONALE: a fallback to a fixed local checkout hands a reproducer
    plausible numbers computed against the wrong tree. No default is right, so
    there is none, and a missing or wrong value stops the run.
    """
    value = os.environ.get("LIBRARIAN_CORPUS")
    if not value:
        sys.exit("LIBRARIAN_CORPUS is unset; set it to the pinned corpus snapshot "
                 "(see paper/supplementary/repository-commits.md) and rerun.")
    root = os.path.expanduser(value)
    if not os.path.isdir(root):
        sys.exit(f"LIBRARIAN_CORPUS={value} is not a directory; set it to the pinned corpus "
                 "snapshot (see paper/supplementary/repository-commits.md) and rerun.")
    return root


CORPUS = Path(require_corpus())
SCAN = Path(__file__).with_name("scan_20260314_threshold90_skillonly.json")
# The default output name carries today's UTC date, so a run on another day cannot overwrite
# a tracked file; SCAN_RESULTS_OUT (a full path) overrides it.
_DEFAULT_OUT_NAME = "order-permutation-{}.md".format(
    datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d"))
OUT = Path(os.environ["SCAN_RESULTS_OUT"]) if os.environ.get("SCAN_RESULTS_OUT") \
    else Path(__file__).with_name(_DEFAULT_OUT_NAME)

def tilde(path):
    """Home-relative form of a path, so a results file carries no user directory."""
    home = os.path.expanduser("~")
    path = str(path)
    return "~" + path[len(home):] if path.startswith(home) else path

def load_files(scan):
    """(marketplace, path) pairs from the scan's `file_index`, in index order.

    The two keys together form the corpus-relative path `<marketplace>/<path>`.
    """
    entries = scan["file_index"]
    items = entries if isinstance(entries, list) else list(entries.values())
    files = []
    for e in items:
        files.append((e["marketplace"], e["path"]))
    return files

def signatures(files):
    """MinHash signature per file-index position, plus counts of skipped files by reason."""
    sigs = {}
    skipped = {"missing": 0, "short": 0, "empty": 0}
    for i, (market, rel) in enumerate(files):
        # Only <marketplace>/<relative> is a real corpus path. A bare CORPUS/rel
        # fallback can resolve a different marketplace's file (14 `curated`
        # entries have paths starting `hashicorp-agent-skills/`, which is also a
        # top-level marketplace directory), so a miss stays a miss.
        p = CORPUS / market / rel
        if not p.exists():
            skipped["missing"] += 1; continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if len(text) < 100:
            skipped["short"] += 1; continue
        sh = tokenize(text)
        if not sh:
            skipped["empty"] += 1; continue
        m = MinHash(num_perm=NUM_PERM)
        for s in sh:
            m.update(s.encode("utf-8"))
        sigs[i] = m
    return sigs, skipped

def greedy(lsh, sigs, order):
    """Greedy first-match clustering in the given order (Section 3.3, cluster formation).

    Each unassigned file seeds one cluster from its LSH candidates; every member
    is then marked assigned. Minimum cluster size is 2.
    """
    assigned, clusters = set(), []
    for i in order:
        if i in assigned:
            continue
        similar = frozenset(int(r) for r in lsh.query(sigs[i]))
        if len(similar) > 1:
            clusters.append(similar); assigned.update(similar)
    return clusters

def rand_indices(a_clusters, b_clusters):
    """Rand index and Hubert-Arabie adjusted Rand index over the common files.

    Clusters may overlap (a file can be returned by more than one seed's LSH
    query), so each clustering is first flattened to a hard partition by
    last-cluster-wins. Both indices are therefore computed on that flattened
    assignment, not on the overlapping cluster lists themselves.

    Pair counts: a = together in both, b = apart in both, c = together in A
    only, d = together in B only. So a + c is the number of within-cluster
    pairs in A, and a + d that in B.
    """
    ma = {x: k for k, c in enumerate(a_clusters) for x in c}
    mb = {x: k for k, c in enumerate(b_clusters) for x in c}
    common = sorted(set(ma) & set(mb))
    a = b = c = d = 0
    for idx, i in enumerate(common):
        for j in common[idx + 1:]:
            sa, sb = ma[i] == ma[j], mb[i] == mb[j]
            if sa and sb: a += 1
            elif not sa and not sb: b += 1
            elif sa: c += 1
            else: d += 1
    n = a + b + c + d
    if n == 0:
        # Fewer than two shared files: agreement is undefined, not chance-level.
        return float("nan"), float("nan")
    ri = (a + b) / n
    # Hubert-Arabie: the expected value of `a` alone, E[a] = (a+c)(a+d)/n, to
    # match the numerator. Using E[a+b] here (the expected count of ALL
    # agreements) inflates the statistic until it saturates at 1.0.
    expected = (a + c) * (a + d) / n
    max_val = ((a + c) + (a + d)) / 2
    if max_val == expected:
        # Degenerate: both clusterings put every common pair the same way, so
        # the index has no range to normalize over. Undefined, not zero:
        # returning 0.0 would read as chance-level on a perfect match.
        return ri, float("nan")
    return ri, (a - expected) / (max_val - expected)

def self_test() -> int:
    """Check rand_indices against hand-computed pair counts before the run.

    DESIGN RATIONALE: the Hubert-Arabie form needs E[a], not E[a+b]. With
    E[a+b] the statistic saturates at 1.0000 for this corpus shape and the
    error is invisible in the output, so the formula is pinned by a test that
    fails the script rather than by inspection. The expected values are derived
    by hand and written out below, so the test needs no scikit-learn.
    """
    a3 = [{0, 1, 2}, {3, 4, 5}, {6, 7, 8}]
    # Identical clusterings: a=9, b=27, c=0, d=0, n=36.
    # RI = 36/36 = 1. E[a] = 9*9/36 = 2.25, max = 9, ARI = (9-2.25)/(9-2.25) = 1.
    ri, ari = rand_indices(a3, [set(c) for c in a3])
    if not (math.isclose(ri, 1.0) and math.isclose(ari, 1.0)):
        print(f"self-test FAILED: identical clusterings gave RI={ri}, ARI={ari}", file=sys.stderr)
        return 1
    # A = [{0,1,2},{3,4,5},{6,7,8}] vs B = [{0,1},{2,3,4},{5,6,7,8}] over 36 pairs:
    # within-cluster pairs A = 9, B = 1+3+6 = 10; together in both a = 5;
    # so c = 9-5 = 4, d = 10-5 = 5, b = 36-5-4-5 = 22.
    # RI = (5+22)/36 = 0.75. E[a] = 9*10/36 = 2.5, max = (9+10)/2 = 9.5,
    # ARI = (5-2.5)/(9.5-2.5) = 2.5/7 = 0.35714285714285715.
    ri, ari = rand_indices(a3, [{0, 1}, {2, 3, 4}, {5, 6, 7, 8}])
    if not (math.isclose(ri, 0.75) and math.isclose(ari, 2.5 / 7)):
        print(f"self-test FAILED: expected RI=0.75, ARI={2.5/7!r}; got RI={ri}, ARI={ari}",
              file=sys.stderr)
        return 1
    # Degenerate: every common pair is together in both, so ARI has no range.
    ri, ari = rand_indices([{0, 1}, {0, 1, 2}], [{0, 1, 2}])
    if not (math.isclose(ri, 1.0) and math.isnan(ari)):
        print(f"self-test FAILED: degenerate case gave RI={ri}, ARI={ari}", file=sys.stderr)
        return 1
    return 0

# Largest percentage difference between this run's baseline and the archived scan
# (clusters or files clustered) before the run is reported as computed over the
# wrong corpus.
TOLERANCE_PCT = 1.0

def scan_date(scan):
    """Date of the archived scan, from its metadata, else from the filename."""
    stamp = scan.get("metadata", {}).get("generated_at")
    if isinstance(stamp, str) and len(stamp) >= 10:
        return stamp[:10]
    m = re.search(r"(\d{4})(\d{2})(\d{2})", SCAN.name)
    return "-".join(m.groups()) if m else "(undated)"

def _git(d, *args):
    """Run a read-only git command in `d`. None on non-zero exit.

    GIT_OPTIONAL_LOCKS=0 stops `status` refreshing (and so rewriting) the index,
    which keeps this strictly read-only against a corpus another job may be
    reading at the same time. FileNotFoundError propagates: a missing git binary
    is a different fact from a directory that is not a checkout.
    """
    r = subprocess.run(["git", "-C", str(d), *args], capture_output=True, text=True,
                       timeout=30, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    # rstrip only: `status --porcelain` encodes the state in the first two
    # columns, so stripping leading whitespace would corrupt the first line.
    return None if r.returncode != 0 else r.stdout.rstrip("\n")

def git_head(d):
    """Short HEAD of the checkout rooted exactly at `d`, else a reason string.

    DESIGN RATIONALE: `git -C` walks up to a parent repository, so a plain
    directory sitting inside one would otherwise be reported with the parent's
    SHA. Comparing --show-toplevel against `d` rejects that. Read-only: this
    never writes to the corpus.
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
        # A dirty worktree means the SHA alone does not identify the bytes read.
        dirty = _git(d, "status", "--porcelain")
        if dirty is None:
            return f"{head}+status unknown"
        return f"{head}+dirty" if dirty else head
    except FileNotFoundError:
        # No git binary at all; without this every row would read "not a git
        # checkout", which would look like a corpus problem rather than a tooling one.
        return "git unavailable"
    except (OSError, subprocess.SubprocessError):
        return "not a git checkout"

# The repository's own HEAD is decided in `repo_provenance.py`, the one place
# that rule lives. `git_head` below stays here for the corpus and marketplace
# rows: those are the pinned upstream repositories the scan read, and their
# commits are the point of the row.

def dirty_note(label, d, indexed):
    """Explain a `+dirty` row, with counts computed from the checkout itself.

    DESIGN RATIONALE: on a case-insensitive filesystem (macOS), a commit holding
    two paths that differ only by letter case checks out to a single file, the
    second write overwriting the first, and the loser then reports as modified.
    That is a property of the commit plus the filesystem, reproduced identically
    by any checkout, not an edit to the snapshot. The counts and the index-impact
    claim are computed rather than asserted so this cannot go stale: if a dirty
    file ever does belong to the scan's file set, the sentence says so.
    """
    tree = _git(d, "ls-tree", "-r", "--name-only", "HEAD")
    status = _git(d, "status", "--porcelain", "--untracked-files=no")
    if tree is None or status is None:
        return f"`+dirty` on {label}: worktree differs from HEAD; could not enumerate the cause."
    seen, collide = set(), set()
    for p in tree.splitlines():
        low = p.lower()
        collide.add(low) if low in seen else seen.add(low)
    # "XY path"; split once so a path containing spaces survives intact.
    paths = [part[1] for part in (line.strip().split(maxsplit=1) for line in status.splitlines())
             if len(part) == 2]
    hit = sum(1 for p in paths if p in indexed)
    unexplained = sum(1 for p in paths if p.lower() not in collide)
    note = (f"`+dirty` on {label}: the commit contains {len(collide)} path pairs differing only by "
            f"letter case; on the case-insensitive macOS filesystem the second checkout overwrites "
            f"the first, so {len(paths)} tracked files show as modified under a case-insensitive "
            f"filesystem. The archived scan was produced under the same condition, and it affects "
            + ("no file in the scan index." if hit == 0 else f"{hit} file(s) in the scan index."))
    if unexplained:
        note += (f" **{unexplained} of the modified files are not explained by a case collision, "
                 f"so for those files the checkout differs from its recorded commit.**")
    return note

def provenance(scan):
    """Markdown table of the corpus snapshot every number below was computed from.

    The corpus root is written as the literal `$LIBRARIAN_CORPUS`, never as the
    resolved directory, so a results file carries no local path.
    """
    names = sorted({e["marketplace"] for e in scan["file_index"]})
    rows = [(n, git_head(CORPUS / n)) for n in names]
    # `curated` holds sub-clones rather than being one checkout itself.
    curated = CORPUS / "curated"
    dirs = {n: CORPUS / n for n in names}
    if curated.is_dir():
        for sub in sorted(p for p in curated.iterdir() if p.is_dir() and p.name != ".git"):
            rows.append((f"curated/{sub.name}", git_head(sub)))
            dirs[f"curated/{sub.name}"] = sub
    lines = ["Corpus root: `$LIBRARIAN_CORPUS`",
             "",
             "Snapshot the numbers below were computed from. Compare against "
             "`paper/supplementary/repository-commits.md`.", "",
             "| corpus directory | HEAD |", "|---|---|"]
    lines += [f"| `{n}` | {h} |" for n, h in rows]
    # Explain every dirty row, so a reader is not left to guess whether the
    # snapshot was edited.
    indexed = {}
    for e in scan["file_index"]:
        indexed.setdefault(e["marketplace"], set()).add(e["path"])
    for n, h in rows:
        if "+dirty" not in h:
            continue
        if n.startswith("curated/"):
            sub = n.split("/", 1)[1] + "/"
            paths = {p[len(sub):] for p in indexed.get("curated", ()) if p.startswith(sub)}
        else:
            paths = indexed.get(n, set())
        lines += ["", dirty_note(n, dirs[n], paths)]
    return lines + [""]

def baseline_comparison(scan, base):
    """Header lines comparing this run's baseline to the archived scan.

    DESIGN RATIONALE: the baseline is evidence only if it reproduces the
    archived scan's file set. A silent shortfall would let a run over the wrong
    corpus be read as the paper's clustering, so the comparison and any breach
    of TOLERANCE_PCT are written into the results file itself rather than left
    to whoever happens to read the console. Both the cluster delta and the file
    delta are gated, and the breach is returned so that it can reach the exit
    status rather than only the markdown.

    Returns (lines, breach).
    """
    ref = scan.get("summary", {})
    ref_clusters, ref_files = ref.get("unique_clusters"), ref.get("files_in_clusters")
    if ref_clusters is None or ref_files is None:
        # A committed scan without these keys is a broken input, not an optional
        # check: every number in this file is compared with that scan.
        raise ValueError(
            f"{SCAN.name} carries no cluster counts in its `summary`; "
            "the baseline cannot be cross-checked against the archived scan.")
    got_clusters, got_files = len(base), sum(len(c) for c in base)
    dc = 100.0 * (got_clusters - ref_clusters) / ref_clusters
    df = 100.0 * (got_files - ref_files) / ref_files
    out = [f"Archived {scan_date(scan)} scan, for comparison: {ref_clusters} clusters, "
           f"{ref_files} files clustered (also a sum of cluster sizes). "
           f"This run differs by {dc:+.2f}% clusters, {df:+.2f}% files."]
    breach = abs(dc) > TOLERANCE_PCT or abs(df) > TOLERANCE_PCT
    if breach:
        out += ["",
                f"**Baseline differs from the archived scan by more than {TOLERANCE_PCT:.0f}%, so the "
                f"file set is not the one the archived scan was built from.** Compare the snapshot "
                f"table above against the SHAs recorded in paper/supplementary/repository-commits.md "
                "to see where the directory named by `LIBRARIAN_CORPUS` diverges. Files whose paths "
                "do not resolve are counted in the skipped total above, and files that do resolve may "
                "still have changed content. The order comparison below is internally valid either way, "
                "because every shuffle is measured against this same signature set, but the absolute "
                "cluster counts here are not the paper's."]
    return out + [""], breach

def render(scan, files, sigs, skipped, base, rows):
    """All lines of the results file, header to table, from the computed values.

    Returns (lines, baseline_breach). Kept apart from main() so the prose can be
    checked against the shipped file without recomputing signatures.
    """
    name = Path(__file__).name
    base_slots = sum(len(c) for c in base)
    base_distinct = len({x for c in base for x in c})
    lines = ["# File-order permutation sensitivity (90% threshold, SKILL.md only)", "",
             "This file reports how much the greedy first-match clustering changes when the file "
             "order is shuffled with the MinHash signatures held fixed. It supports the "
             "ordering-sensitivity result of Section 3.3 (Similarity Analysis), which reports a range "
             "of adjusted Rand index scores over ten shuffles of the assignment order with the "
             "signatures held fixed, and Section 6 (Limitations), which repeats that range. Both "
             "endpoints are the minimum and maximum of the adjusted Rand column in the table at the "
             "end of this file.",
             "",
             f"Generated by `{name}`; rerun with `python paper/sources/scans/{name}` from the "
             "repository root, with `LIBRARIAN_CORPUS` set to the root of the pinned corpus snapshot "
             "(SHAs in `paper/supplementary/repository-commits.md`). The variable has no default; a "
             "run without it stops before computing anything.",
             f"Input scan: `{SCAN.name}`, beside the script; its `file_index` is the file list.", "",
             f"Files with signatures: {len(sigs)} of {len(files)}. Skipped {skipped['missing']} whose "
             f"path does not resolve under the corpus root, {skipped['short']} shorter than 100 "
             f"characters, and {skipped['empty']} that produced no shingles.",
             f"Baseline (sorted file-index order): {len(base)} clusters, {base_slots} files clustered "
             f"as a sum of cluster sizes, {base_distinct} distinct files. The two differ because clusters "
             f"may overlap: {base_slots - base_distinct} files are returned by more than one seed's query. "
             f"The archived scan's 'files in clusters' is the same sum-of-sizes count, so the two compare "
             f"like with like.",
             f"K = {K} shuffles, seeds 1000..{1000 + K - 1}, signatures fixed (datasketch default seed).", "",
             f"Output defaults to `order-permutation-<UTC date>.md`; set `SCAN_RESULTS_OUT` to a "
             f"full path to write elsewhere instead of overwriting a previously dated results file.",
             ""]
    lines += provenance(scan)
    baseline_lines, baseline_breach = baseline_comparison(scan, base)
    lines += baseline_lines
    lines += ["Columns. *clusters*: number of clusters the shuffled order produced. "
              "*Rand index*: share of file pairs assigned the same way (together, or apart) in both "
              "clusterings. *adjusted Rand*: the Hubert-Arabie chance-corrected form of it, 1.0 for "
              "identical, 0.0 for chance-level; `nan` where it is undefined. *baseline clusters "
              "reproduced exactly*: share of the baseline's clusters that appear in the shuffled run as "
              "the identical set of files.",
              "",
              "Both Rand indices are computed over a hard partition obtained by flattening each "
              "clustering with last-cluster-wins, so a file in more than one cluster is counted only in "
              "the last one. They therefore measure agreement on that flattened assignment, not on the "
              "overlapping cluster lists.",
              "",
              "| shuffle | clusters | Rand index | adjusted Rand | baseline clusters reproduced exactly |",
              "|---:|---:|---:|---:|---:|"]
    for k, n, ri, ari, exact in rows:
        lines.append(f"| {k} | {n} | {ri:.4f} | {ari:.4f} | {exact:.3f} |")
    return lines, baseline_breach

def main() -> int:
    scan = json.loads(SCAN.read_text())
    files = load_files(scan)
    sigs, skipped = signatures(files)
    if not sigs:
        print("no signatures computed; corpus path or file_index keys are wrong", file=sys.stderr)
        return 1
    lsh = MinHashLSH(threshold=THRESHOLD, num_perm=NUM_PERM)
    for i, m in sigs.items():
        lsh.insert(str(i), m)
    keys = sorted(sigs)
    base = greedy(lsh, sigs, keys)
    base_set = set(base)
    rows = []
    for k in range(K):
        rng = random.Random(1000 + k)
        order = keys[:]; rng.shuffle(order)
        cl = greedy(lsh, sigs, order)
        ri, ari = rand_indices(base, cl)
        # No baseline clusters means the share has no denominator. nan, not 0.0,
        # which would read as a measured "nothing was reproduced".
        exact = sum(1 for c in cl if c in base_set) / len(base) if base else float("nan")
        rows.append((k, len(cl), ri, ari, exact))
    lines, baseline_breach = render(scan, files, sigs, skipped, base, rows)
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    if baseline_breach:
        print(f"baseline differs from the archived scan by more than {TOLERANCE_PCT:.0f}%; "
              "the corpus is not the one the archived scan was built from", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    rc = self_test()
    sys.exit(rc or main())
