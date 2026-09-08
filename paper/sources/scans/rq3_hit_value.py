#!/usr/bin/env python3
"""Cross-tabulations behind the RQ3 overlap paragraph of Section 4.5, Structural Clustering
vs. Pattern-Based Triage (RQ3).

Section 4.5 reads: "Of the 1,469 files matching at least one pattern, 485 (33.0%) also
appeared in similarity clusters, and within that intersection 245 (50.5%) belong to documented
accounts, against 17 of the 984 hits outside clusters (1.7%), the remaining 967 carrying no
attribution to a documented account. Clustering also holds 376 documented attackers' files
that match no pattern, 317 of them hightower6eu copies; over the 714 documented files in the
archive, clustering reaches 621 and the pattern scan 262." and, one sentence later, "The
in-cluster agreement is concentrated: sakaen736jih supplies 195 of the 245 documented
in-cluster hits, and 227 of the 245 match the base64 pattern." This script computes every
number in those sentences: it cross-tabulates the ClawHub population on pattern hit against
cluster membership, splits every cell by attribution to a documented attacker account, counts
the documented files each signal reaches, lists the accounts behind the documented cells, and
repeats the first table with the iocs.json payload indicators in place of the grep patterns.

Nothing here is re-derived: the six primary regexes and the population rule are copied verbatim
from `behavioral-scan-20260907.md`, the tracked output of `behavioral_scan.py`; `account_of`,
the study accounts and the payload marker come from `file_level_precision.py` by import. Every
run recomputes that scan's counts, union, overlap, index size and cluster total, and the three
documented totals, stopping on a disagreement, which would mean these tables describe a
different scan or a different attribution rule.

Inputs: LIBRARIAN_CORPUS, the pinned corpus snapshot, under which the ClawHub archive is
read; the scan JSON and iocs.json that `file_level_precision.py` locates beside itself; and
`behavioral-scan-20260907.md` for the patterns and the population rule.

Output: `rq3-hit-value-YYYYMMDD.md` (UTC date) beside this script, or the full path in
SCAN_RESULTS_OUT. A second run on the same UTC day overwrites the day's file.

Run, with LIBRARIAN_CORPUS set:
  python paper/sources/scans/rq3_hit_value.py
"""
import collections, datetime, json, math, os, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import file_level_precision as flp  # account_of, payload_indicators, ContentMarker

SCAN, IOCS, CLAWHUB = flp.SCAN, flp.IOCS, flp.CLAWHUB
CORPUS = Path(flp.require_corpus())    # required here; flp leaves it optional
PATTERN_SOURCE = "behavioral-scan-20260907.md"
NOW = datetime.datetime.now(datetime.timezone.utc)
OUT = Path(os.environ.get("SCAN_RESULTS_OUT")
           or HERE / f"rq3-hit-value-{NOW:%Y%m%d}.md")

# The six PRIMARY patterns of Table 7, character for character from the "Recomputed (primary)"
# rows of behavioral-scan-20260907.md with the case flag and per-row count that file records.
# These patterns belong to `behavioral-scan-20260907.md`; editing them here detaches these
# tables from the union that file publishes.
PATTERNS = [
    ("Base64 decode", re.compile(r"base64 -d|base64 -D|base64 --decode|b64decode|atob\("), 332),
    ("curl-pipe-to-shell", re.compile(r"(curl|wget)[^\n]*\|[^\n]*sh"), 443),
    ("Env secrets + HTTP calls",
     re.compile(r"(API_KEY|API_TOKEN|SECRET_KEY|ACCESS_TOKEN|PASSWORD)[^\n]{0,120}https?://",
                re.IGNORECASE), 551),
    ("Prompt injection language",
     re.compile(r"(ignore|disregard|forget)[^\n]{0,30}(previous|prior|above|earlier|all)"
                r"[^\n]{0,20}instructions", re.IGNORECASE), 101),
    ("Remote instruction fetch (C2)",
     re.compile(r"(curl|wget)[^\n]*https?://[^\n]*\.(sh|py|pl|rb|exe|bin)"), 367),
    ("Reverse shell indicators", re.compile(r"/dev/tcp|nc -e|ncat -e", re.IGNORECASE), 20),
]
# Imported rather than restated, so this script and behavioral_scan.py cannot disagree.
from behavioral_scan import (PAPER_UNION as EXPECTED_UNION,          # noqa: E402
                             PAPER_OVERLAP as EXPECTED_OVERLAP,
                             PAPER_POPULATION as EXPECTED_POPULATION)
EXPECTED_INDEXED, EXPECTED_CLUSTERED = 23654, 4250   # clawhub rows in file_index, in_cluster
# Documented files in the population, of them clustered and pattern-hit: the 714, 621 and 262
# that Section 4.5 quotes. A run that disagrees with any expected value stops (`ok` in main).
EXPECTED_DOCUMENTED, EXPECTED_DOC_CLUSTERED, EXPECTED_DOC_HIT = 714, 621, 262
HEADER = ["| flag | side | files | documented account | not documented | documented share |",
          "|---|---|---:|---:|---:|---:|"]


def two_by_two(records):
    """Cells of the cluster x attribution table, keyed by (in_cluster, documented)."""
    counts = collections.Counter((bool(c), bool(d)) for c, d in records)
    return {(c, d): counts[(c, d)] for c in (True, False) for d in (True, False)}


def table_rows(cells, label):
    """Markdown rows for one 2x2, each with the documented share of its row."""
    out = []
    for in_cluster, side in ((True, "in a cluster"), (False, "not in a cluster")):
        doc, undoc = cells[(in_cluster, True)], cells[(in_cluster, False)]
        out.append(f"| {label} | {side} | {doc + undoc} | {doc} | {undoc}"
                   f" | {share(doc, doc + undoc)} |")
    return out


def share(num, den):
    return f"{100 * num / den:.1f}%" if den else "n/a"


def clustered_no_hit(rows):
    """(documented, account) for clustered files carrying no pattern hit."""
    return [(d, a) for hit, _, c, d, a in rows if c and not hit]


def selftest():
    """Four (hit, indicator, in_cluster, documented, account) files, one per corner."""
    toy = [(True, True, True, True, "a"), (True, False, False, False, None),
           (False, True, True, True, "a"), (False, False, False, False, None)]
    cells = two_by_two((c, d) for h, _, c, d, _ in toy if h)
    assert cells == {(True, True): 1, (True, False): 0, (False, True): 0, (False, False): 1}
    unhit = clustered_no_hit(toy)          # the function main uses, not a second copy of it
    assert [len(unhit), sum(1 for d, _ in unhit if d)] == [1, 1], unhit
    assert collections.Counter(a for d, a in unhit if d) == {"a": 1}
    assert table_rows(cells, "x")[0] == "| x | in a cluster | 1 | 1 | 0 | 100.0% |"
    assert flp.account_of({"marketplace": CLAWHUB, "path": "skills/a/s/SKILL.md"}) == "a"
    assert flp.account_of({"marketplace": "other", "path": "skills/a/s/SKILL.md"}) is None


PUBLIC_REPO = "plugin-librarian"
PRIVATE_HISTORY = "<private-history>"


def is_public_repo(d) -> bool:
    """True when `d` is inside a checkout whose `origin` is the public repository.

    Duplicates `order_permutation.is_public_repo`; keep the copies in step.
    DESIGN RATIONALE: the results files are published, so a rerun inside a
    private working repository must not write that repository's commit into
    one. The test is on `origin`, so it travels with a clone, and it compares
    the whole final path segment, so a repository whose name merely begins
    with the public one does not pass it.
    """
    try:
        r = subprocess.run(["git", "-C", str(d), "config", "--get", "remote.origin.url"],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    if r.returncode != 0 or not r.stdout.strip():
        return False
    name = r.stdout.strip().rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name == PUBLIC_REPO


def public_repo_head(d) -> str:
    """`git_head(d)` when `d` is the public repository, else the redaction token."""
    return git_head(d) if is_public_repo(d) else PRIVATE_HISTORY


def git_head(path) -> str:
    """Short HEAD of the repository at `path`, with a +dirty marker."""
    def git(*args):
        return subprocess.run(["git", "-C", str(path), *args], capture_output=True,
                              text=True, check=True).stdout.strip()
    try:
        return git("rev-parse", "--short", "HEAD") + (
            "+dirty" if git("status", "--porcelain") else "")
    except (OSError, subprocess.SubprocessError) as exc:
        return f"unavailable ({exc.__class__.__name__})"


def study_accounts(iocs: dict) -> frozenset:
    """The `study` ground truth of file_level_precision.py, with that script's own checks."""
    refs = [r for r in iocs["metadata"]["references"] if r.get("source") == "Antiy CERT"]
    if len(refs) != 1:
        raise SystemExit(f"expected 1 Antiy CERT reference in iocs.json, found {len(refs)}")
    antiy = set(refs[0]["authors_documented"])
    if len(antiy) != 12:
        raise SystemExit(f"expected 12 Antiy accounts in iocs.json, found {len(antiy)}")
    return frozenset(set(iocs["clawhub_authors"]) | antiy)


def main() -> int:
    selftest()
    started = time.monotonic()
    root = CORPUS / CLAWHUB
    if not root.is_dir():
        print(f"clawhub archive not found at {root}; set LIBRARIAN_CORPUS to the pinned"
              " snapshot", file=sys.stderr)
        return 1

    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    index = {e["path"]: e for e in scan["file_index"] if e["marketplace"] == CLAWHUB}
    iocs = json.loads(IOCS.read_text(encoding="utf-8"))
    study = study_accounts(iocs)
    indicators = flp.payload_indicators(iocs)
    marker = flp.ContentMarker(indicators)

    # The population rule of PATTERN_SOURCE: every file named SKILL.md under the archive.
    # DESIGN RATIONALE for os.walk over rglob("SKILL.md"): on a case-insensitive filesystem pathlib
    # resolves a literal final component by an existence check rather than by listing the
    # directory, so rglob("SKILL.md") there returns 24,368 entries: the 23,806 exact-name files, 561 case
    # variants (530 skill.md, 18 Skill.md, 13 with a .MD extension) reported under the requested
    # name, where a p.name test cannot tell them apart, and one DIRECTORY,
    # skills/jamipuchi/openclaw-leaderboard/src/app/SKILL.md. os.walk sees the on-disk names on
    # every filesystem.
    files = sorted(Path(dirpath, name) for dirpath, _, names in os.walk(root)
                   for name in names if name == "SKILL.md")
    rows, unindexed_hits, per_pattern = [], 0, [[] for _ in PATTERNS]
    for path in files:
        rel = path.relative_to(root).as_posix()
        loc = {"marketplace": CLAWHUB, "path": rel}
        entry = index.get(rel)
        in_cluster = bool(entry and entry.get("in_cluster"))  # absent from index => unclustered
        account = flp.account_of(loc)
        documented = account in study
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = [bool(rx.search(text)) for _, rx, _ in PATTERNS]
        for bucket, hit in zip(per_pattern, hits):
            if hit:
                bucket.append((in_cluster, documented))
        unindexed_hits += any(hits) and entry is None
        rows.append((any(hits), marker(loc), in_cluster, documented, account))

    union = two_by_two((c, d) for hit, _, c, d, _ in rows if hit)
    ind = two_by_two((c, d) for _, m, c, d, _ in rows if m)
    union_total = sum(union.values())
    overlap = union[(True, True)] + union[(True, False)]      # pattern hits inside clusters
    outside, in_doc, out_doc = union_total - overlap, union[(True, True)], union[(False, True)]
    unhit = clustered_no_hit(rows)
    no_hit, no_hit_doc = len(unhit), sum(1 for d, _ in unhit if d)
    by_account = (collections.Counter(a for hit, _, c, d, a in rows if hit and c and d),
                  collections.Counter(a for d, a in unhit if d))
    top_hit, top_nohit = (c.most_common(1)[0] for c in by_account)
    top_pattern = max(((n, sum(1 for c, d in b if c and d))
                       for (n, _, _), b in zip(PATTERNS, per_pattern)), key=lambda t: t[1])
    # Reach of each signal over the documented files themselves, the complement of the tables
    # above: those ask what a hit is worth, this asks what share of the known-bad files each
    # signal touches. `reach` is (label, count) so the gate and the table read the same numbers.
    doc = [(h, m, c) for h, m, c, d, _ in rows if d]
    doc_clustered = sum(1 for _, _, c in doc if c)
    doc_hit = sum(1 for h, _, _ in doc if h)
    reach = [("in a similarity cluster", doc_clustered),
             ("hit by any of the six patterns", doc_hit),
             ("hit by any payload indicator", sum(1 for _, m, _ in doc if m)),
             ("hit by a pattern and an indicator", sum(1 for h, m, _ in doc if h and m)),
             ("hit by neither pattern nor indicator", sum(1 for h, m, _ in doc if not h and not m)),
             ("reached by no signal at all", sum(1 for h, m, c in doc if not (h or m or c)))]
    runtime = time.monotonic() - started
    ok = (len(files) == EXPECTED_POPULATION and union_total == EXPECTED_UNION
          and overlap == EXPECTED_OVERLAP and len(index) == EXPECTED_INDEXED
          and no_hit + overlap == EXPECTED_CLUSTERED and len(doc) == EXPECTED_DOCUMENTED
          and doc_clustered == EXPECTED_DOC_CLUSTERED and doc_hit == EXPECTED_DOC_HIT
          and all(len(b) == pub for b, (_, _, pub) in zip(per_pattern, PATTERNS)))
    # Guarded rather than written inline: a run with no attributed hit outside a cluster
    # would divide by zero in the ratio the sentence quotes.
    # Wald interval on log(risk ratio). Quoted as an order of magnitude, not to one decimal:
    # the outside numerator is 17 files, so the third significant figure is noise.
    if overlap and outside and out_doc:
        rr = (in_doc / overlap) / (out_doc / outside)
        half = 1.96 * math.sqrt(1 / in_doc - 1 / overlap + 1 / out_doc - 1 / outside)
        ratio = ("a hit inside a cluster is roughly {:.0f}x as likely to be an attacker's file"
                 " (risk ratio {:.1f}, approximate 95% interval [{:.0f}, {:.0f}], wide because"
                 " the outside numerator is {} files)").format(
                     round(rr, -1), rr, rr * math.exp(-half), rr * math.exp(half), out_doc)
    else:
        ratio = "one side is empty, so no ratio is quotable"

    lines = ["# What a behavioral hit is worth on each side of the overlap (RQ3)", "",
        f"Generated by `{Path(__file__).name}` on {NOW:%Y-%m-%d %H:%M} UTC.", "",
        "This file reports the cross-tabulations behind the overlap paragraph of Section"
        " 4.5, Structural Clustering vs. Pattern-Based Triage (RQ3). That paragraph gives the"
        " share of pattern-matching files that also sit in a similarity cluster, the share of"
        " that intersection attributed to documented accounts against the much smaller share"
        " among pattern hits outside clusters, the count of documented attackers' files that"
        " clustering holds although no pattern matches them, the reach of each method over"
        " the documented files in the archive, and the concentration of the in-cluster"
        " agreement in one account and one pattern. Table 1 below carries the in-cluster and"
        " outside-cluster shares, tables 2 and 4 the documented files that match no pattern,"
        " table 3 the reach of each signal, and table 4 with the per-pattern rows of table 1"
        " the concentration of the agreement. Section 6 below restates each figure beside the"
        " table it comes from.", "",
        "Every table splits the pattern-hit or the clustered population by attribution to a"
        f" documented attacker account under the `study` rule of `file_level_precision.py`: Antiy CERT's 12"
        f" accounts and the {len(study) - 12} further `clawhub_authors` accounts this study"
        " confirmed by payload inspection, attributed by the account segment of the ClawHub"
        " archive path, so a community-repository file carries no account. The documented-share"
        " columns are per-file account attributions under that rule, not the file-level precision"
        " figures of `file_level_precision.py`, whose denominator is every file in a"
        " size-thresholded cluster and which scores clusters, not pattern hits.", "",
        "## Provenance", "", "| item | value |", "|---|---|",
        "| corpus root | `$LIBRARIAN_CORPUS` |", f"| `{CLAWHUB}` HEAD | {git_head(root)} |",
        f"| repository HEAD | {public_repo_head(HERE)} |", f"| input scan | `{SCAN.name}` |",
        f"| ground truth | `{IOCS.name}`: {len(study)} accounts, {len(indicators)} indicators |",
        f"| patterns, population rule | `{PATTERN_SOURCE}` (copied verbatim, not re-derived) |",
        "| command | `python paper/sources/scans/rq3_hit_value.py` |",
        f"| runtime | {runtime:.1f} s |", "", "## Population and patterns", "",
        f"- files scanned: {len(files)} `SKILL.md` under `{CLAWHUB}/` in the pinned snapshot,"
        f" the unfiltered archive population `{PATTERN_SOURCE}` uses",
        f"- in the scan's `file_index`: {len(index)}; absent, under the clusterer's 100-character"
        f" minimum: {len(files) - len(index)}. Flagged `in_cluster`: {no_hit + overlap}",
        f"- pattern-hit files absent from the `file_index`: {unindexed_hits}, counted as"
        " unclustered throughout, since a file outside the index cannot be clustered. Files the"
        f" payload-indicator marker could not read: {len(marker.unresolved)}", "",
        "| pattern (primary) | regex | case | files | published |", "|---|---|---|---:|---:|",
    ]
    for (name, rx, pub), bucket in zip(PATTERNS, per_pattern):
        case = "insensitive" if rx.flags & re.IGNORECASE else "sensitive"
        lines.append(f"| {name} | `{rx.pattern}` | {case} | {len(bucket)} | {pub} |")
    lines += [
        f"| **union of the six** | | | **{union_total}** | **{EXPECTED_UNION}** |",
        f"| **union ∩ `in_cluster`** | | | **{overlap}** | **{EXPECTED_OVERLAP}** |", "",
        f"Reproduces `{PATTERN_SOURCE}`: {'yes' if ok else 'NO'}."
        + ("" if ok else " These tables describe a different run; treat as failed."), "",
        "## 1. Pattern hits, by cluster membership and attribution", "",
        f"All {union_total} files matching at least one of the six primaries.", "",
    ] + HEADER + table_rows(union, "any of the six") + [
        "", "The same table per pattern; a file matching two patterns appears in both rows.", "",
    ] + HEADER
    for (name, _, _), bucket in zip(PATTERNS, per_pattern):
        lines += table_rows(two_by_two(bucket), name)
    lines += [
        "", "## 2. Clustered files carrying no pattern hit", "",
        f"- clustered files with no hit on any of the six primaries: {no_hit}, of which"
        f" {no_hit_doc} ({share(no_hit_doc, no_hit)}) are attributed to a documented account", "",
        "These are the files the structural method reaches and the patterns do not; Section 4.5"
        " quotes the documented count among them, and table 4 lists the accounts behind it.", "",
        "## 3. Documented files: reach of each signal", "",
        f"Documented throughout this file means attributed to the {len(study)}-account study set"
        " by `account_of` from `file_level_precision.py`: the account segment of the ClawHub"
        " archive path, gated on the `clawhub-archive` marketplace, so a file in another"
        " marketplace, or a ClawHub file whose path is not `skills/<account>/<slug>/...`, carries"
        f" no account. The population holds {len(doc)} such files. The tables above ask what a"
        " hit is worth; this one asks what share of the known-bad files each signal reaches.", "",
        f"| signal | documented files reached | share of {len(doc)} |", "|---|---:|---:|",
    ] + [f"| {label} | {n} | {share(n, len(doc))} |" for label, n in reach] + [
        "", "## 4. Which accounts the two documented cells come from", "",
        f"Both documented cells are concentrated. `{top_hit[0]}` holds {top_hit[1]} of the"
        f" {in_doc} documented in-cluster hits, and {top_pattern[1]} of those {in_doc} are hits on"
        f" the {top_pattern[0].lower()} pattern alone; `{top_nohit[0]}` holds {top_nohit[1]} of the"
        f" {no_hit_doc} documented clustered files with no hit. Neither cell is that many"
        " independent observations: both are a few campaigns whose files were copied many times,"
        " so read the shares in tables 1 and 2 as counts of files, not of incidents.", "",
        "| account | documented hits in clusters | documented clustered files, no hit |",
        "|---|---:|---:|",
    ] + [f"| `{a}` | {by_account[0].get(a, 0)} | {by_account[1].get(a, 0)} |"
         for a in sorted(set(by_account[0]) | set(by_account[1]),
                         key=lambda a: (-by_account[0].get(a, 0), -by_account[1].get(a, 0), a))] + [
        f"| **total** | **{in_doc}** | **{no_hit_doc}** |", "",
        "## 5. Payload-indicator variant", "",
        f"Table 1 recomputed over the {len(indicators)} `iocs.json` payload indicators (the"
        " `content` marker of `file_level_precision.py`, imported unchanged) in place of the six"
        " grep primaries, so known-infrastructure hits can be compared against generic behavioral"
        " ones. A content hit is a case-folded substring match, so a document about the attack"
        " matches as a delivery vehicle does, and `clawdhub.com` is its weakest driver. The paper"
        " does not quote this table.", "",
    ] + HEADER + table_rows(ind, "payload indicator") + [
        "", "## 6. What these tables support", "",
        f"1. Of the {overlap} pattern-hit files that also sit in a similarity cluster, {in_doc}"
        f" ({share(in_doc, overlap)}) are attributed to a documented attacker account, against"
        f" {out_doc} of the {outside} pattern-hit files outside any cluster"
        f" ({share(out_doc, outside)}): {ratio}. The paper quotes the counts and shares, not the"
        f" ratio. [table 1; population and patterns from `{PATTERN_SOURCE}`, attribution from"
        " `file_level_precision.py`]",
        f"2. Clustering reaches {no_hit} files matching none of the six patterns, {no_hit_doc} of"
        f" them ({share(no_hit_doc, no_hit)}) attributed to documented attacker accounts;"
        f" {top_nohit[1]} of those {no_hit_doc} are `{top_nohit[0]}` files. [tables 2 and 4]",
        f"3. Over the {len(doc)} documented files in the archive, clustering reaches"
        f" {doc_clustered} and the pattern scan {doc_hit}. [table 3]",
        f"4. `{top_hit[0]}` supplies {top_hit[1]} of the {in_doc} documented in-cluster hits, and"
        f" {top_pattern[1]} of the {in_doc} match the {top_pattern[0].lower()} pattern. [table 4;"
        " per-pattern rows of table 1]", "",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    if not ok:
        print(f"STOP: recomputed pattern counts, union or overlap disagree with {PATTERN_SOURCE};"
              " these tables do not describe the scan Section 4.5 and Table 7 report",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
