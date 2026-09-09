#!/usr/bin/env python3
"""Per-account file counts, clustering and similarity for Table 3.

Table 3 of the paper (Section 4.3, Method Behavior on Malicious Content) prints a Files
column and a Sim. column for four campaigns plus a pooled Minor row. The printed values
are hand-recorded March figures and no released script produced them. This script
recomputes the row quantities from the archived 90% scan under stated rules, so that the
population behind each number is defined and checkable.

Rule for the Files column: a SKILL.md file in the scan's `file_index` belongs to account
`A` when its marketplace is `clawhub-archive` and its path is `skills/A/<slug>/SKILL.md`.
Clustered is how many of those files appear in the `locations` list of at least one
cluster, and Clusters is how many distinct clusters hold at least one of them.

Four statistics are reported for the Sim. column. The primary one is the mean of the
scan's recorded pairwise similarities over pairs whose two endpoints both belong to the
row's accounts, taken across every cluster that holds them, which is the mean pairwise
similarity Section 4.3 describes. Counting rule: one recorded value per pair per cluster,
so a pair the greedy assignment places in two clusters contributes twice. The second
statistic applies the other rule, one value per distinct pair however many clusters
record it, and is reported beside the first so the difference between the two is visible;
the two differ on one row only. The third is the mean of the clusters' `avg_similarity`
field weighted by how many of the account's file memberships each cluster contributes.
The fourth is the mean over pairs with exactly one endpoint in the row's accounts,
reported as its own column so the comparison the report draws between it and the
two-endpoint means can be checked against a printed number.

The script also prints two alternative populations, distinct files in clusters of size at
least 10 and at least 20, and two candidate pools for the Minor row, so that the
choices between candidate definitions stay visible rather than implicit.

The values Table 3 prints are recorded in `PRINTED` and checked against the computed rows
before anything is written: the Files column exactly, the Sim. column at the precision the
column prints, and the Minor row's pair count against the caption. A disagreement stops
the run rather than being narrated beside numbers that contradict it.

Inputs: `scan_20260314_threshold90_skillonly.json` beside this script, and `iocs.json`
two directories up, for the recorded `total_skills` per account. No corpus access, no
network, no environment variables, nothing randomized.

Output: `table3-campaigns-20260908.md` beside this script.

Options: --check verifies that file instead of rewriting it, and reports a unified diff
on a mismatch.

Self-test (before either input is read): a seven-file toy scan with two accounts, two
clusters of different sizes and different recorded similarities, one deeper clawhub path
and one same-shaped path in another marketplace. It fixes hand-computed answers for the
attribution counts, the two similarity statistics (which differ from their unweighted and
from their one-endpoint counterparts on this toy), and the attribution guard, which must
trip on the account holding the deeper path and stay silent on the other.

Run:
  python paper/sources/scans/table3_campaigns.py [--check]
"""
import argparse
import difflib
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAN = HERE / "scan_20260314_threshold90_skillonly.json"
IOCS = HERE.parent.parent / "iocs.json"
OUT = HERE / "table3-campaigns-20260908.md"
SIZE_GATES = (10, 20)

CAMPAIGN_ACCOUNTS = ("hightower6eu", "sakaen736jih", "thiagoruss0", "zaycv", "jordanprater")

# Minor pool (a): Table 6 (Appendix A) accounts with a Documented-by entry of Antiy CERT,
# Koi Security or Trend Micro that rows 1 to 4 do not name.
MINOR_A = ("moonshine-100rze", "aslaep123", "noreplyboter", "rjnpage", "lvy19811120-gif",
           "gpaitai", "danman60", "noypearl", "stveenli")
# Minor pool (b): every Table 6 account rows 1 to 4 do not name, documented or not.
MINOR_B = MINOR_A + ("anisafifi", "timclawbot", "kenblive", "mupengi-bot")

ROWS = (
    ("1", ("hightower6eu",)),
    ("2", ("sakaen736jih",)),
    ("3", ("thiagoruss0",)),
    ("4", ("zaycv", "jordanprater")),
    ("Minor", MINOR_A),
)

MINOR_POOLS = (
    ("a", "Table 6 accounts documented by Antiy CERT, Koi Security or Trend Micro that "
          "rows 1 to 4 do not name", MINOR_A),
    ("b", "every Table 6 account rows 1 to 4 do not name", MINOR_B),
)

# What Table 3 prints, for the side-by-side paragraphs and for check_printed() below.
PRINTED = {
    "1": ("hightower6eu", 352, "99.8%"),
    "2": ("sakaen736jih", 212, "99.3%"),
    "3": ("thiagoruss0", 38, "99.9%"),
    "4": ("zaycv, jordanprater", 39, "99.9%"),
    "Minor": ("nine documented accounts", 14, "100%"),
}
# Table 3's caption states that the Minor row averages two pairs.
PRINTED_MINOR_PAIRS = 2


def attribute(scan):
    """Map file_index value to account under the path rule, plus the two coverage counts.

    Returns (by_file, n_attributed, n_clawhub). The second and third differ because
    clawhub-archive also holds paths deeper than skills/<account>/<slug>/SKILL.md.
    """
    by_file = {}
    n_clawhub = 0
    for entry in scan["file_index"]:
        if entry.get("marketplace") != "clawhub-archive":
            continue
        n_clawhub += 1
        parts = entry["path"].split("/")
        if len(parts) == 4 and parts[0] == "skills" and parts[3] == "SKILL.md":
            by_file[entry["file_index"]] = parts[1]
    return by_file, len(by_file), n_clawhub


def loose_counts(scan):
    """Account counts under the weaker rule that reads the second path segment at any
    depth. Used only to check that the two rules agree on the accounts in the table."""
    counts = {}
    for entry in scan["file_index"]:
        if entry.get("marketplace") != "clawhub-archive":
            continue
        parts = entry["path"].split("/")
        if len(parts) >= 2 and parts[0] == "skills":
            counts[parts[1]] = counts.get(parts[1], 0) + 1
    return counts


def attribution_disagreements(scan, by_file, accounts):
    """Accounts where the strict path rule and the second-segment rule differ, as
    (account, strict, loose) triples. Empty means the accounts are safe to attribute."""
    loose = loose_counts(scan)
    strict = {}
    for account in by_file.values():
        strict[account] = strict.get(account, 0) + 1
    out = []
    for account in accounts:
        if strict.get(account, 0) != loose.get(account, 0):
            out.append((account, strict.get(account, 0), loose.get(account, 0)))
    return out


def mean(values):
    return sum(values) / len(values) if values else None


def row_stats(scan, by_file, accounts, gates=SIZE_GATES):
    """Every per-row quantity for one set of accounts."""
    wanted = set(accounts)
    idx = {f for f, a in by_file.items() if a in wanted}
    clustered = set()
    clusters = 0
    memberships = 0
    weighted_sim = 0.0
    gated = {g: set() for g in gates}
    both, one = [], []
    # One entry per distinct pair, against `both`'s one entry per pair per cluster.
    distinct = {}
    for cluster in scan["clusters"]:
        mine = {loc["file_index"] for loc in cluster["locations"]} & idx
        if not mine:
            continue
        clusters += 1
        clustered |= mine
        memberships += len(mine)
        weighted_sim += cluster["avg_similarity"] * len(mine)
        for gate in gates:
            if cluster["size"] >= gate:
                gated[gate] |= mine
        for pair in cluster["similarity_pairs"]:
            first = pair["file1_index"] in idx
            second = pair["file2_index"] in idx
            if first and second:
                both.append(pair["similarity"])
                key = (min(pair["file1_index"], pair["file2_index"]),
                       max(pair["file1_index"], pair["file2_index"]))
                if key in distinct and distinct[key] != pair["similarity"]:
                    sys.exit(f"pair {key} is recorded at {distinct[key]} in one cluster and "
                             f"at {pair['similarity']} in cluster {cluster['cluster_id']}; "
                             "the distinct-pair mean has no single value for it")
                distinct[key] = pair["similarity"]
            elif first or second:
                one.append(pair["similarity"])
    return {
        "files": len(idx),
        "clustered": len(clustered),
        "clusters": clusters,
        "memberships": memberships,
        "pair_sim": mean(both),
        "pair_n": len(both),
        "distinct_sim": mean(list(distinct.values())),
        "distinct_n": len(distinct),
        "cluster_sim": weighted_sim / memberships if memberships else None,
        "one_sim": mean(one),
        "one_n": len(one),
        "gated": {g: len(v) for g, v in gated.items()},
    }


def gate_sweep(scan, by_file, accounts, lo, hi):
    """Distinct clustered files per cluster-size gate over the range [lo, hi]."""
    wanted = set(accounts)
    idx = {f for f, a in by_file.items() if a in wanted}
    out = {}
    for gate in range(lo, hi + 1):
        files = set()
        for cluster in scan["clusters"]:
            if cluster["size"] >= gate:
                files |= {loc["file_index"] for loc in cluster["locations"]} & idx
        out[gate] = len(files)
    return out


def toy_scan():
    """Two accounts. alpha holds files 0, 1, 2, 6 under the strict rule and file 4 as
    well under the second-segment rule; file 5 shares alpha's path shape in another
    marketplace. Cluster 0 has 2 alpha files at 0.90; cluster 1 has 3 alpha files and one
    beta file, and its six pairs average 0.95."""
    return {
        "file_index": [
            {"file_index": 0, "marketplace": "clawhub-archive", "path": "skills/alpha/s1/SKILL.md"},
            {"file_index": 1, "marketplace": "clawhub-archive", "path": "skills/alpha/s2/SKILL.md"},
            {"file_index": 2, "marketplace": "clawhub-archive", "path": "skills/alpha/s3/SKILL.md"},
            {"file_index": 3, "marketplace": "clawhub-archive", "path": "skills/beta/s1/SKILL.md"},
            {"file_index": 4, "marketplace": "clawhub-archive", "path": "skills/alpha/nested/s4/SKILL.md"},
            {"file_index": 5, "marketplace": "other-marketplace", "path": "skills/alpha/s5/SKILL.md"},
            {"file_index": 6, "marketplace": "clawhub-archive", "path": "skills/alpha/s6/SKILL.md"},
            {"file_index": 7, "marketplace": "clawhub-archive", "path": "skills/gamma/s1/SKILL.md"},
        ],
        "clusters": [
            {"cluster_id": 0, "size": 2, "avg_similarity": 0.90,
             "locations": [{"file_index": 0}, {"file_index": 1}],
             "similarity_pairs": [{"file1_index": 0, "file2_index": 1, "similarity": 0.90}]},
            {"cluster_id": 1, "size": 4, "avg_similarity": 0.95,
             "locations": [{"file_index": 1}, {"file_index": 2}, {"file_index": 3}, {"file_index": 6}],
             "similarity_pairs": [
                 {"file1_index": 1, "file2_index": 2, "similarity": 1.00},
                 {"file1_index": 1, "file2_index": 6, "similarity": 1.00},
                 {"file1_index": 2, "file2_index": 6, "similarity": 1.00},
                 {"file1_index": 1, "file2_index": 3, "similarity": 0.80},
                 {"file1_index": 2, "file2_index": 3, "similarity": 0.90},
                 {"file1_index": 3, "file2_index": 6, "similarity": 1.00},
             ]},
            {"cluster_id": 2, "size": 2, "avg_similarity": 0.50,
             "locations": [{"file_index": 3}, {"file_index": 7}],
             "similarity_pairs": [{"file1_index": 3, "file2_index": 7, "similarity": 0.50}]},
        ],
    }


def fail(message):
    print(f"self-test FAILED: {message}", file=sys.stderr)
    sys.exit(1)


def self_test():
    toy = toy_scan()
    by_file, n_attributed, n_clawhub = attribute(toy)
    if (n_attributed, n_clawhub) != (6, 7):
        fail(f"attributed {n_attributed} of {n_clawhub} clawhub files, want 6 of 7")

    # The deeper path skills/alpha/nested/s4/SKILL.md is alpha's under the second-segment
    # rule and nobody's under the strict rule, so the guard must trip on alpha (4 against
    # 5) and stay silent on beta.
    tripped = attribution_disagreements(toy, by_file, ("alpha",))
    if tripped != [("alpha", 4, 5)]:
        fail(f"attribution guard gave {tripped}, want [('alpha', 4, 5)]")
    if attribution_disagreements(toy, by_file, ("beta",)):
        fail("attribution guard tripped on beta, which has no deeper path")

    # alpha holds 4 files. Cluster 0 contributes 2 memberships at 0.90, cluster 1
    # contributes 3 at 0.95, so the membership-weighted cluster mean is 4.65 / 5 = 0.930,
    # which the unweighted cluster mean (1.85 / 2 = 0.925) does not equal. alpha's
    # both-endpoint pairs are 0.90, 1.00, 1.00, 1.00, giving 3.90 / 4 = 0.975; its
    # one-endpoint pairs are 0.80, 0.90, 1.00, giving 2.70 / 3 = 0.900.
    alpha = row_stats(toy, by_file, ("alpha",), gates=(2, 3))
    want = {"files": 4, "clustered": 4, "clusters": 2, "memberships": 5,
            "pair_sim": 0.975, "pair_n": 4, "distinct_sim": 0.975, "distinct_n": 4,
            "cluster_sim": 0.930, "one_sim": 0.900, "one_n": 3, "gated": {2: 4, 3: 3}}
    got = dict(alpha)
    for key in ("pair_sim", "cluster_sim", "one_sim", "distinct_sim"):
        got[key] = None if got[key] is None else round(got[key], 6)
    if got != want:
        fail(f"alpha gave {got}, want {want}")

    # Pooling alpha and beta takes every pair inside clusters 0 and 1: 6.60 / 7 = 0.942857.
    # Cluster 2's beta-gamma pair has one endpoint in that pool, so it is the one-endpoint
    # figure at 0.500.
    pooled = row_stats(toy, by_file, ("alpha", "beta"), gates=(2, 3))
    if (pooled["files"], pooled["clustered"], pooled["memberships"], pooled["pair_n"],
            round(pooled["pair_sim"], 6), pooled["one_n"], pooled["one_sim"]) != \
            (5, 5, 7, 7, 0.942857, 1, 0.50):
        fail(f"pooled gave {pooled}, want 5 files, 5 clustered, 7 memberships, 7 pairs at "
             "0.942857 and one one-endpoint pair at 0.500")

    # A pooled row is a function of its pool. Adding gamma pulls the beta-gamma pair
    # inside the pool, so the file count rises by one and the pairwise mean drops from
    # 6.60 / 7 = 0.942857 to 7.10 / 8 = 0.887500. If these matched, the row would be
    # insensitive to which accounts the pool names, and the choice of pool would be
    # unfalsifiable from the output.
    wider = row_stats(toy, by_file, ("alpha", "beta", "gamma"), gates=(2, 3))
    if (wider["files"], wider["clustered"], wider["memberships"], wider["pair_n"],
            round(wider["pair_sim"], 6), wider["one_n"]) != (6, 6, 8, 8, 0.8875, 0):
        fail(f"wider pool gave {wider}, want 6 files, 6 clustered, 8 memberships, 8 pairs "
             "at 0.887500 and no one-endpoint pair")
    if wider["pair_sim"] == pooled["pair_sim"] or wider["files"] == pooled["files"]:
        fail("changing the pool left the pooled row unchanged, so the row does not depend "
             "on its pool")

    # The two counting rules for the Sim. column differ only where one pair sits in two
    # clusters. The toy above has no such pair, so a second toy carries one: files 0 and 1
    # are recorded at 1.00 in both clusters, giving 2 recorded values and 1 distinct pair.
    dup = {"file_index": [
               {"file_index": 0, "marketplace": "clawhub-archive", "path": "skills/alpha/s1/SKILL.md"},
               {"file_index": 1, "marketplace": "clawhub-archive", "path": "skills/alpha/s2/SKILL.md"},
               {"file_index": 2, "marketplace": "clawhub-archive", "path": "skills/alpha/s3/SKILL.md"}],
           "clusters": [
               {"cluster_id": 0, "size": 2, "avg_similarity": 1.00,
                "locations": [{"file_index": 0}, {"file_index": 1}],
                "similarity_pairs": [{"file1_index": 0, "file2_index": 1, "similarity": 1.00}]},
               {"cluster_id": 1, "size": 3, "avg_similarity": 0.80,
                "locations": [{"file_index": 0}, {"file_index": 1}, {"file_index": 2}],
                "similarity_pairs": [
                    {"file1_index": 1, "file2_index": 0, "similarity": 1.00},
                    {"file1_index": 0, "file2_index": 2, "similarity": 0.70},
                    {"file1_index": 1, "file2_index": 2, "similarity": 0.70}]}]}
    dup_by_file, _n, _c = attribute(dup)
    dup_stats = row_stats(dup, dup_by_file, ("alpha",), gates=(2, 3))
    # Recorded values: 1.00, 1.00, 0.70, 0.70 -> 3.40 / 4 = 0.850.
    # Distinct pairs: (0,1) 1.00, (0,2) 0.70, (1,2) 0.70 -> 2.40 / 3 = 0.800.
    if (dup_stats["pair_n"], round(dup_stats["pair_sim"], 6), dup_stats["distinct_n"],
            round(dup_stats["distinct_sim"], 6)) != (4, 0.85, 3, 0.80):
        fail(f"duplicate-pair toy gave {dup_stats['pair_n']} recorded values at "
             f"{dup_stats['pair_sim']} and {dup_stats['distinct_n']} distinct pairs at "
             f"{dup_stats['distinct_sim']}, want 4 at 0.850 and 3 at 0.800")

    for n, want_w in ((0, "zero"), (2, "two"), (10, "ten"), (11, "11"), (1500, "1,500")):
        if number_word(n) != want_w:
            fail(f"number_word({n}) gave {number_word(n)}, want {want_w}")

    # check_printed compares a printed percentage at its own precision, so 99.8%, 99.9%
    # and 100% are each read to the number of places they print.
    probe = [("1", ("x",), {"files": 352, "pair_sim": 0.998049, "pair_n": 9}),
             ("2", ("x",), {"files": 212, "pair_sim": 0.992662, "pair_n": 9}),
             ("3", ("x",), {"files": 38, "pair_sim": 0.999080, "pair_n": 9}),
             ("4", ("x",), {"files": 39, "pair_sim": 0.998857, "pair_n": 9}),
             ("Minor", ("x",), {"files": 14, "pair_sim": 1.0, "pair_n": 2})]
    if check_printed(probe):
        fail(f"check_printed rejected values that match Table 3: {check_printed(probe)}")
    bent = [(n, a, dict(st)) for n, a, st in probe]
    bent[1][2]["pair_sim"] = 0.9925          # rounds to 99.2%, not the printed 99.3%
    bent[3][2]["files"] = 40
    bent[4][2]["pair_n"] = 3
    if len(check_printed(bent)) != 3:
        fail(f"check_printed missed a disagreement: {check_printed(bent)}")

    print("self-test PASS: 6 of 7 clawhub files attributed (nested path and foreign "
          "marketplace excluded); attribution guard trips on alpha at 4 against 5 and is "
          "silent on beta; alpha 4 files, 4 clustered, 2 clusters, pairwise mean 0.975, "
          "membership-weighted cluster mean 0.930 against an unweighted 0.925, "
          "one-endpoint mean 0.900; alpha+beta pooled 5 files and 7 pairs at 0.942857, "
          "and adding gamma moves that pool to 6 files and 8 pairs at 0.887500; a pair in "
          "two clusters counts twice at 0.850 and once at 0.800; check_printed accepts "
          "Table 3's five rows and catches a bent Sim., a bent Files and a bent pair count")


NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
                "nine", "ten")


def number_word(n):
    """Small counts as words, larger ones as digits, so counted prose stays computed."""
    return NUMBER_WORDS[n] if 0 <= n < len(NUMBER_WORDS) else f"{n:,}"


def fmt_sim(value, places=2):
    return "n/a" if value is None else f"{100 * value:.{places}f}%"


def printed_places(text):
    """Decimal places in a printed percentage such as `99.8%` or `100%`."""
    body = text.rstrip("%")
    return len(body.split(".")[1]) if "." in body else 0


def check_printed(rows):
    """Disagreements between PRINTED and the computed rows, as message strings.

    DESIGN RATIONALE: the report asserts in prose that the printed Files column is the
    computed column and that each printed Sim. value is the computed one at the
    precision the column prints. An assertion in prose beside numbers that contradict
    it is worse than no assertion, so the comparison is made here and a disagreement
    stops the run on both the write path and the --check path.
    """
    by_name = {name: stats for name, _accounts, stats in rows}
    out = []
    for name, (_label, files, sim) in PRINTED.items():
        stats = by_name.get(name)
        if stats is None:
            out.append(f"row {name} is printed in Table 3 but not computed here")
            continue
        if stats["files"] != files:
            out.append(f"row {name}: Table 3 prints {files:,} files, the rule gives "
                       f"{stats['files']:,}")
        got = fmt_sim(stats["pair_sim"], printed_places(sim))
        if got != sim:
            out.append(f"row {name}: Table 3 prints Sim. {sim}, the pairwise mean at that "
                       f"precision is {got}")
    minor = by_name.get("Minor")
    if minor is not None and minor["pair_n"] != PRINTED_MINOR_PAIRS:
        out.append(f"the Minor row: Table 3's caption states {PRINTED_MINOR_PAIRS} pairs, "
                   f"the rule gives {minor['pair_n']}")
    return out


def ioc_total(iocs, accounts):
    """Recorded total_skills summed over the row's accounts, and the accounts with no
    entry in iocs.json."""
    present = [a for a in accounts if a in iocs]
    missing = [a for a in accounts if a not in iocs]
    total = sum(iocs[a]["total_skills"] for a in present)
    return total, present, missing


def build_report(scan, by_file, iocs, rows, digest, ioc_digest,
                 n_attributed, n_clawhub, n_index, n_clusters, n_pairs, pools, sweep):
    by_name = {name: stats for name, _accounts, stats in rows}
    order = [name for name, _accounts, _stats in rows]

    def where(name):
        return "for the Minor row" if name == "Minor" else f"for row {name}"

    zaycv = row_stats(scan, by_file, ("zaycv",))["files"]
    jordan = by_name["4"]["files"] - zaycv
    sweep_lo, sweep_hi = min(sweep), max(sweep)
    ioc_lines = []
    ioc_missing = []
    for account in CAMPAIGN_ACCOUNTS + MINOR_B:
        if account in iocs:
            ioc_lines.append(f"`{account}` {iocs[account]['total_skills']:,}")
        else:
            ioc_missing.append(f"`{account}`")

    lines = [
        "# Table 3: campaign file counts, clustering and similarity per account",
        "",
        "Supports Table 3 (Section 4.3, Method Behavior on Malicious Content).",
        "",
        "Generated by `paper/sources/scans/table3_campaigns.py` on 2026-09-08 from the archived scan "
        f"`{SCAN.name}` (sha256 `{digest}`), which indexes {n_index:,} files in {n_clusters:,} clusters "
        f"and records {n_pairs:,} within-cluster similarity pairs, and from `paper/iocs.json` "
        f"(sha256 `{ioc_digest}`).",
        "",
        "## Settings and rules",
        "",
        "*Attribution.* A file in the scan's `file_index` belongs to account `A` when its marketplace is "
        "`clawhub-archive` and its path is `skills/A/<slug>/SKILL.md`. That rule attributes "
        f"{n_attributed:,} of the {n_clawhub:,} clawhub-archive files in the index; the remainder sit at "
        "deeper paths. For every account named below the rule agrees file for file with the weaker rule "
        "that reads the second path segment at any depth, and the script stops if the two disagree on any "
        "of them, so no account here loses files to a deeper path.",
        "",
        "*Files.* Files attributed to the row's account or accounts. This is the population the "
        "printed table uses: every row of its Files column equals the computed column below.",
        "",
        "*Clustered.* How many of those files appear in the `locations` list of at least one cluster. "
        "*Clusters* is how many distinct clusters hold at least one of them, and *Memb.* is the sum over "
        "those clusters of how many of the account's files each holds. The greedy assignment loop can "
        "place one file in more than one cluster, which is why *Memb.* can exceed *Clustered*.",
        "",
        "*Sim. (pairwise).* The mean of the scan's recorded `similarity_pairs` values over pairs whose two "
        "endpoints both belong to the row's accounts, across every cluster holding them. Section 4.3 "
        "describes the quantity as a mean pairwise similarity, and the scan's pair records are complete "
        "for within-cluster pairs, so this is the statistic that answers the printed column. The counting "
        "rule is one recorded value per pair per cluster: the greedy assignment can place a pair in more "
        "than one cluster, and each cluster's record of it counts. *Pair values* is how many recorded "
        "values the mean averages, which is not the same as how many pairs there are.",
        "",
        "*Sim. (distinct pairs).* The same mean under the other counting rule, one value per distinct "
        "pair however many clusters record it. *Distinct pairs* is that count. Both are reported because "
        "the two rules give different means wherever a pair sits in two clusters, and the choice between "
        "them is not visible in a single printed figure. A pair recorded in two clusters carries the same "
        "similarity in both, and the script stops if it ever does not.",
        "",
        "*Sim. (one endpoint).* The mean over pairs with exactly one endpoint in the row's accounts, that "
        "is over the row's files paired with files belonging to nobody in the row. It is reported so the "
        "comparison the closing section draws between the within-row means and this one can be read off a "
        "column rather than taken on trust.",
        "",
        "*Sim. (cluster).* The alternative reading: the mean of the clusters' `avg_similarity` field over "
        "the clusters the account's files sit in, weighted by the memberships each cluster contributes. It "
        "is reported so the two candidate definitions can be compared, but it mixes in the similarity of "
        "files belonging to other accounts in the same cluster.",
        "",
        f"*Recorded skills.* The `total_skills` value `paper/iocs.json` records for the row's accounts, "
        "summed. This is a third population, counted from the filesystem archive rather than the scan's "
        "index, and it is shown so the reader can see the file index, `iocs.json` and the printed table "
        "side by side. Per account: " + ", ".join(ioc_lines) + ". No entry exists for "
        + ", ".join(ioc_missing) + ", so those contribute nothing to the column.",
        "",
        "## Computed rows",
        "",
        "| Row | Account(s) | Files | Clustered | Clusters | Memb. | Sim. (pairwise) | Pair values | "
        "Sim. (distinct pairs) | Distinct pairs | Sim. (one endpoint) | Sim. (cluster) | "
        "Recorded skills |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, accounts, stats in rows:
        label = "see pool (a) below" if name == "Minor" else ", ".join(f"`{a}`" for a in accounts)
        total, _present, _missing = ioc_total(iocs, accounts)
        lines.append(f"| {name} | {label} | {stats['files']:,} | {stats['clustered']:,} | "
                     f"{stats['clusters']:,} | {stats['memberships']:,} | {fmt_sim(stats['pair_sim'])} | "
                     f"{stats['pair_n']:,} | {fmt_sim(stats['distinct_sim'])} | "
                     f"{stats['distinct_n']:,} | {fmt_sim(stats['one_sim'])} | "
                     f"{fmt_sim(stats['cluster_sim'])} | {total:,} |")
    lines += [
        "",
        "## Alternative populations",
        "",
        "Distinct files of the row's account or accounts that sit in a cluster of at least the given size. "
        "These are the other candidate definitions of a Files column, printed so the choice between them "
        "stays visible.",
        "",
        "| Row | Account(s) | Files | Clustered | In clusters >= 10 | In clusters >= 20 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for name, accounts, stats in rows:
        label = "see pool (a) below" if name == "Minor" else ", ".join(f"`{a}`" for a in accounts)
        lines.append(f"| {name} | {label} | {stats['files']:,} | {stats['clustered']:,} | "
                     f"{stats['gated'][10]:,} | {stats['gated'][20]:,} |")
    lines += [
        "",
        f"Row 1's >= 10 column is flat across the neighbouring gates: every gate from {sweep_lo} to "
        f"{sweep_hi} gives the same {by_name['1']['gated'][10]:,} files, so that column identifies a "
        "band rather than a single cluster size. The script stops if a rescan makes the sweep "
        "non-flat, because this sentence would then be wrong.",
    ]

    lines += [
        "",
        "## Candidate pools for the Minor row",
        "",
        f"The paper does not name the accounts the Minor row pools, so {number_word(len(pools))} "
        "candidate pools are computed. The Minor row of the computed table above is pool (a), marked "
        "*used* below.",
        "",
        "| Pool | Accounts | Files | Clustered | Clusters | Memb. | Sim. (pairwise) | Pair values | "
        "Sim. (cluster) | Recorded skills |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, description, accounts, stats in pools:
        used = " *used*" if key == "a" else ""
        total, _present, _missing = ioc_total(iocs, accounts)
        lines.append(f"| ({key}){used} | {description}: " + ", ".join(f"`{a}`" for a in accounts)
                     + f" | {stats['files']:,} | {stats['clustered']:,} | {stats['clusters']:,} | "
                     f"{stats['memberships']:,} | {fmt_sim(stats['pair_sim'])} | {stats['pair_n']:,} | "
                     f"{fmt_sim(stats['cluster_sim'])} | {total:,} |")
    pool_files = {key: stats["files"] for key, _d, _a, stats in pools}
    mupengi = row_stats(scan, by_file, ("mupengi-bot",))["files"]
    lines += [
        "",
        "Pool (a) is the one used, because it is the definition the surrounding text implies: the minor "
        "actors documented by the citing sources, which is Table 6 restricted to accounts with a "
        "Documented-by entry and stripped of the five that rows 1 to 4 already name. Pool (b) is the "
        "unrestricted remainder of Table 6, which pulls in the four accounts no source documents, one of "
        f"them (`mupengi-bot`) large enough to dominate the row at {mupengi} files. The printed table "
        f"names pool (a) in its caption and prints that pool's {pool_files['a']:,} files, where pool (b) "
        f"gives {pool_files['b']:,}. Both stay in the table above so the reader can see what the choice "
        "costs.",
        "",
        "Three accounts in the chosen pool have no file in the scan's index: `aslaep123`, `gpaitai` and "
        "`danman60`. Table 6 records `gpaitai` and `danman60` as absent from the archive; it records "
        "`aslaep123` as reached by payload grep rather than by clustering, so its absence from the file "
        "index is a separate matter from the other two.",
        "",
        "## What the rules reproduce",
        "",
        "The printed Files column is the computed column. Under the rule the Files column reads "
        + ", ".join(f"{by_name[n]['files']:,} {where(n)}" for n in order) + ", and the printed "
        "table prints " + ", ".join(f"{PRINTED[n][1]:,} {where(n)}" for n in order) + ".",
        "",
        f"Row 4 pools two accounts: `zaycv` contributes {zaycv} files and `jordanprater` a further "
        f"{jordan}, {by_name['4']['files']} together, which is what that row prints. The Minor row is "
        "pool (a), the nine documented Table 6 accounts rows 1 to 4 do not name, which the printed "
        f"caption names and which gives {by_name['Minor']['files']} attributed files, "
        f"{by_name['Minor']['clustered']} of them clustered.",
        "",
        "The pairwise statistic reproduces the Sim. column for every row. Printed against computed "
        f"pairwise: row 1 {PRINTED['1'][2]} against {fmt_sim(by_name['1']['pair_sim'])}, row 2 "
        f"{PRINTED['2'][2]} against {fmt_sim(by_name['2']['pair_sim'])}, row 3 {PRINTED['3'][2]} "
        f"against {fmt_sim(by_name['3']['pair_sim'])}, row 4 {PRINTED['4'][2]} against "
        f"{fmt_sim(by_name['4']['pair_sim'])}, Minor {PRINTED['Minor'][2]} against "
        f"{fmt_sim(by_name['Minor']['pair_sim'])}. Each printed value is the computed one at the "
        "precision the column prints, and the script stops rather than writing this file if that "
        "stops being true. Under the other counting rule, one value per distinct pair, row 2 falls "
        f"from {by_name['2']['pair_n']:,} recorded values to {by_name['2']['distinct_n']:,} distinct "
        f"pairs and its mean from {fmt_sim(by_name['2']['pair_sim'])} to "
        f"{fmt_sim(by_name['2']['distinct_sim'])}, which prints as "
        f"{fmt_sim(by_name['2']['distinct_sim'], 1)} where the column gives {PRINTED['2'][2]}; no "
        "other row has a pair in two clusters, so the two rules agree on the rest. The printed digit "
        "reproduces under the recorded-value rule and not under the distinct-pair rule, and both are "
        "in the table above so the difference is visible rather than a choice made silently. The "
        "membership-weighted cluster statistic is the alternative "
        f"reading and runs lower ({fmt_sim(by_name['3']['cluster_sim'])} for row 3 and "
        f"{fmt_sim(by_name['4']['cluster_sim'])} for row 4), so it is not the statistic the column "
        "uses. The one-endpoint means in the table above are lower again, for the same reason.",
        "",
        "The Clusters column has no counterpart in the printed table. It is reported because Section 4.3 "
        "states a cluster count for row 3 in its prose, and the computed value for that row is "
        f"{by_name['3']['clusters']}.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Recompute the Table 3 campaign rows from the archived scan.")
    parser.add_argument("--check", action="store_true",
                        help="verify the existing results file instead of rewriting it")
    args = parser.parse_args()
    self_test()

    raw = SCAN.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    scan = json.loads(raw.decode("utf-8"))
    ioc_raw = IOCS.read_bytes()
    ioc_digest = hashlib.sha256(ioc_raw).hexdigest()
    iocs = json.loads(ioc_raw.decode("utf-8"))["clawhub_authors"]

    by_file, n_attributed, n_clawhub = attribute(scan)
    checked = set(CAMPAIGN_ACCOUNTS) | set(MINOR_B)
    disagreements = attribution_disagreements(scan, by_file, sorted(checked))
    if disagreements:
        for account, strict, loose in disagreements:
            print(f"{account}: path rule gives {strict} files but the second-segment rule gives {loose}; "
                  "the two disagree, so the attribution rule is not safe for this account", file=sys.stderr)
        sys.exit(1)

    n_pairs = sum(len(c["similarity_pairs"]) for c in scan["clusters"])

    rows = []
    for name, accounts in ROWS:
        stats = row_stats(scan, by_file, accounts)
        rows.append((name, accounts, stats))
        print(f"row {name:<5} files {stats['files']:>4}  clustered {stats['clustered']:>4}  "
              f"clusters {stats['clusters']:>3}  memb {stats['memberships']:>4}  "
              f"pairwise {fmt_sim(stats['pair_sim']):>8} over {stats['pair_n']:>5} pairs  "
              f"cluster {fmt_sim(stats['cluster_sim']):>8}  one-endpoint {fmt_sim(stats['one_sim']):>8} "
              f"over {stats['one_n']:>4} pairs  >=10 {stats['gated'][10]:>4}  >=20 {stats['gated'][20]:>4}")

    pools = []
    for key, description, accounts in MINOR_POOLS:
        stats = row_stats(scan, by_file, accounts)
        pools.append((key, description, accounts, stats))
        print(f"minor pool ({key})  accounts {len(accounts):>2}  files {stats['files']:>3}  "
              f"clustered {stats['clustered']:>3}")

    sweep = gate_sweep(scan, by_file, ("hightower6eu",), 8, 13)
    print("hightower6eu gate sweep: " + ", ".join(f">={g} {n}" for g, n in sorted(sweep.items())))
    if len(set(sweep.values())) != 1:
        print("gate sweep 8 to 13 is no longer flat; the report's flat-band sentence under "
              "Alternative populations needs rewriting", file=sys.stderr)
        sys.exit(1)

    # Both paths: a report that asserts the printed values are the computed ones must not
    # be written, or pass a check, while they disagree.
    problems = check_printed(rows)
    if problems:
        for line in problems:
            print(line, file=sys.stderr)
        print("Table 3 as printed and the recomputed rows disagree; refusing to write or "
              "verify a report that says they agree", file=sys.stderr)
        sys.exit(1)

    report = build_report(scan, by_file, iocs, rows, digest, ioc_digest, n_attributed, n_clawhub,
                          len(scan["file_index"]), len(scan["clusters"]), n_pairs, pools, sweep)

    if args.check:
        existing = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if report == existing:
            print(f"{OUT.name} matches recomputation")
            sys.exit(0)
        diff = difflib.unified_diff(existing.splitlines(keepends=True), report.splitlines(keepends=True),
                                    fromfile=str(OUT.name), tofile="recomputed")
        sys.stdout.writelines(diff)
        sys.exit(1)

    OUT.write_text(report, encoding="utf-8")
    print(f"wrote {OUT.name}")


if __name__ == "__main__":
    main()
