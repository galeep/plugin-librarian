#!/usr/bin/env python3
"""File-level precision within the size-thresholded clusters of the 2026-03-14 scan.

Cluster-level precision in the paper counts a cluster as a true positive if it
holds at least one file confirmed malicious. This script computes the finer
figure: within the clusters of >= 20, >= 10 and >= 5 files, what share of files
is malicious, and how many true-positive clusters are pure versus mixed.

It supports one sentence of Section 4.4 (IOC Validation): "File-level
precision, promised in Section 3.4, is 305 of 307 files (0.993) at ≥ 20; at
≥ 10 the corresponding figure is membership-level, 557 of 682 memberships
over 643 distinct files, 0.817 (per-cluster results are among the files
released with the code, Appendix C)." The study rows of the output are those
figures with their per-cluster breakdown. The cross-check section of the
output is the computation behind the Table 4 caption in the same section:
"Only the ≥ 20 and ≥ 10 rows reproduce from the released ground truth."

Three ground truths are reported side by side:
  strict  : the 12 accounts Antiy CERT documented, read out of iocs.json by
            looking up the reference whose "source" is "Antiy CERT"
  study   : the union of those 12 with the accounts in iocs.json clawhub_authors
            (the accounts this study confirmed by payload inspection), 18 in all
  content : EXPLORATORY. study, plus any file whose text on disk contains a
            payload indicator from iocs.json payload_infrastructure or the
            literals "openclawcli" / "clawcli". It tests
            whether a file-level marker explains the rows of Table 4 that the
            account rules do not reproduce.

strict and study are account rules: they attribute a file by the account segment
of its ClawHub archive path, so files in community repositories carry no account
and are unattributed under both. Section 3.4 of the paper states a wider rule
than either ("Antiy CERT's 12 authors, Koi IOC slugs, or files confirmed through
payload inspection"), which is why the reproduction of Table 4 is partial;
the cross-check section of the output states exactly which rows reproduce.

The denominator for file-level precision is ALL files in the thresholded set,
including files inside false-positive clusters. It is the share an operator
auto-quarantining at that cluster size would sweep up, not a rate within true
positive clusters. Files are counted as cluster memberships, one per location
record in the scan, so a file that sits in more than one cluster counts once per
cluster; the paper reports the >= 10 figure as membership-level for that reason.

Every run cross-checks its own cluster-level counts against Table 4 and exits
non-zero if the >= 20 or >= 10 rows disagree under the study definition, since a
disagreement there would mean this attribution rule is not the one behind
Table 4. The results file is written before that check, so a failing run
still leaves its output on disk for inspection; trust the exit status, not the
presence of the file.

Inputs: `scan_20260314_threshold90_skillonly.json` beside this script and
`paper/iocs.json`, both read for every column. LIBRARIAN_CORPUS must name the
corpus snapshot recorded in `paper/supplementary/repository-commits.md`; it is
read only by the exploratory `content` rule, which looks up each file's text at
`$LIBRARIAN_CORPUS/<marketplace>/<path>`. The precision figures never touch the
filesystem. main() refuses to run without a corpus directory, because with none
every file would be counted as unreadable and the content column would be a column
of quiet zeros; importing the module needs no corpus.

Output: `file-level-precision-YYYYMMDD.md` (today's UTC date) beside this script, or the
full path in SCAN_RESULTS_OUT. A second run on the same UTC day overwrites the day's file.

`account_of`, `slug_of`, `payload_indicators`, `ContentMarker`, `WEAK_INDICATOR`,
`SCAFFOLD_TYPE`, `TABLE4` and `CLAWHUB` are imported by `table4_triage_record.py`,
`rq3_hit_value.py`, `exact_hash_baseline.py`, `backup_slug_check.py` and
`supplementary_data_tables.py`, so the attribution rule is shared by all of them.

Run, with LIBRARIAN_CORPUS set:
  python paper/sources/scans/file_level_precision.py
"""
import datetime, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAN = HERE / "scan_20260314_threshold90_skillonly.json"
IOCS = HERE.parents[1] / "iocs.json"
# The default output name carries today's UTC date, so a run on another day cannot overwrite
# the file shipped in the repository; SCAN_RESULTS_OUT (a full path) overrides it.
_DEFAULT_OUT_NAME = "file-level-precision-{}.md".format(
    datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d"))
OUT = Path(os.environ["SCAN_RESULTS_OUT"]) if os.environ.get("SCAN_RESULTS_OUT") \
    else HERE / _DEFAULT_OUT_NAME
def require_corpus():
    """Corpus root from LIBRARIAN_CORPUS, or exit; there is no default.

    DESIGN RATIONALE: a fallback to a default checkout path hands a reproducer
    plausible numbers computed against the wrong tree. No default is right, so
    there is none, and a missing or wrong value stops the run.
    """
    value = os.environ.get("LIBRARIAN_CORPUS")
    if not value:
        sys.exit("LIBRARIAN_CORPUS is unset; set it to the corpus snapshot recorded in "
                 "paper/supplementary/repository-commits.md and rerun.")
    root = os.path.expanduser(value)
    if not os.path.isdir(root):
        sys.exit(f"LIBRARIAN_CORPUS={value} is not a directory; set it to the corpus "
                 "snapshot recorded in paper/supplementary/repository-commits.md and rerun.")
    return root


# Corpus root for the exploratory content marker only. The precision figures read
# the archived scan and iocs.json and never touch the filesystem, so importing this
# module must not require a corpus: MARKETPLACE_ROOT is None when LIBRARIAN_CORPUS
# is unset, every file is then counted as unreadable, and main() refuses to run. There
# is no path default, because a fallback to a live checkout computes the content
# column against a tree other than the recorded snapshot.
_corpus_env = os.environ.get("LIBRARIAN_CORPUS")
MARKETPLACE_ROOT = Path(os.path.expanduser(_corpus_env)) if _corpus_env else None
THRESHOLDS = (20, 10, 5)
CLAWHUB = "clawhub-archive"

# Cluster-level true positives as published in Table 4 of the paper (Section 4.4,
# \label{tab:precision-recall}): threshold -> (TP, clusters). None keys the
# table's "All clusters" row. Reproduced here so the cross-check is recomputed on
# every run rather than done by eye once.
TABLE4 = {20: (11, 11), 15: (23, 23), 10: (30, 38), 5: (60, 163), None: (104, 2622)}

# Rows Table 4 carries that THRESHOLDS does not, reported for context in the
# cross-check so a reader does not conclude only the >= 5 row fails to reproduce.
CONTEXT_ROWS = (15, None)

# The "known malware authors" list carried by the March working notes, which are
# not part of this artifact. Included as a candidate ground truth because those
# notes reach 60/163 at >= 5 with it, which this script does not reproduce.
MARCH_ACCOUNTS = frozenset({
    "hightower6eu", "sakaen736jih", "thiagoruss0", "zaycv", "jordanprater",
    "stveenli", "anisafifi", "timclawbot", "kenblive", "mupengi-bot",
})

# Two payload-name literals that iocs.json does not carry as indicators. They come
# from the March working notes, which are not part of this artifact. Everything
# else in the content marker comes from iocs.json.
EXTRA_LITERALS = ("openclawcli", "clawcli")

# Indicators shorter than this are dropped: they are substrings common enough to
# match unrelated prose and would silently inflate the content counts.
MIN_INDICATOR_LEN = 5

# The five payload_infrastructure categories the content marker draws on, and the
# three it does not. ip_addresses and file_hashes are excluded as verified inert:
# adding them changes no figure this script reports. social_engineering_patterns
# is excluded because it is NOT inert and must not be included: its ZIP-password
# literal "openclaw" is 8 characters, so it survives MIN_INDICATOR_LEN and matches
# most of the corpus, taking the all-clusters content count to 634 (that figure is
# recorded, not recomputed here, because reproducing it means building an indicator
# set this script deliberately does not use).
SOCIAL_ENGINEERING_ALL_CLUSTERS = 634
INDICATOR_CATEGORIES = ("domains", "paste_site_delivery", "c2_endpoints",
                        "github_accounts", "zip_delivery")
EXCLUDED_CATEGORIES = ("ip_addresses", "file_hashes", "social_engineering_patterns")

# The scan tags a cluster 'scaffold' when it is internal to one marketplace with
# >= 5 files and average similarity >= 0.98 (librarian/cli.py:1582-1585). The
# published Table 4 carries a Scaffold row reading "44/44" (Section 4.4) and the
# scan holds exactly 44 such clusters, so the triage behind Table 4 credited every
# scaffold cluster and the tag is a candidate for the marker the account rules do
# not reproduce. DESIGN RATIONALE for reporting it separately rather than folding
# it into a ground truth: the tag is assigned by the same clustering pipeline whose
# output is being evaluated, so any rule that ORs it in measures how closely that
# triage tracked the tool's own structural tag. Rows built on it are
# reconstructions, not precision figures.
SCAFFOLD_TYPE = "scaffold"

# Weakest of the indicators: iocs.json records clawdhub.com as a typosquat with
# status "unknown", not as a confirmed payload host, and a file naming it is as
# likely to be documenting the legitimate clawdhub CLI as delivering anything. Counted
# separately at every threshold so a reader can subtract it.
WEAK_INDICATOR = "clawdhub.com"


def account_of(loc: dict):
    """Account owning a ClawHub archive file, or None if the file has no account.

    DESIGN RATIONALE: the marketplace gate is deliberate. 1,425 of the 2,836
    non-ClawHub locations in this scan also have paths beginning with "skills/",
    and 78 of those have enough segments for a path-only rule to read a second
    segment as an "account" (48 of them land in the >= 5 thresholded set). On
    this scan none of those second segments matches any ground-truth set, so the
    gate changes no number reported here; without it the attribution rule is one
    upstream directory rename away from silently crediting a community
    repository's file to an attacker account. The audit that establishes the
    zero-difference claim is recomputed on every run in attribution_audit().
    """
    if loc["marketplace"] != CLAWHUB:
        return None
    parts = loc["path"].split("/")
    return parts[1] if len(parts) >= 4 and parts[0] == "skills" else None


def slug_of(loc: dict):
    """Skill slug of a file: the directory holding it, lowercased, or None."""
    parts = loc["path"].split("/")
    return parts[-2].lower() if len(parts) >= 2 else None


def payload_indicators(iocs: dict) -> frozenset:
    """Literal strings from iocs.json payload_infrastructure, lowercased.

    Covers these categories: domains, paste-site delivery URLs,
    C2 endpoints (address, path, and the two joined), the GitHub accounts and
    repositories hosting payloads with their payload filenames, and the ZIP
    delivery filenames and accounts.
    """
    pi = iocs["payload_infrastructure"]
    out = set(EXTRA_LITERALS)
    out.update(d["domain"] for d in pi["domains"])
    for entry in pi["paste_site_delivery"]:
        out.update(entry.get("urls") or [])
    for entry in pi["c2_endpoints"]:
        out.add(entry["ip"])
        if entry.get("path"):
            out.add(entry["path"])
            out.add(entry["ip"] + entry["path"])
    for entry in pi["github_accounts"]:
        out.update(v for v in (entry.get("account"), entry.get("repo"),
                               entry.get("payload")) if v)
    for entry in pi["zip_delivery"]:
        out.update(entry.get("filenames") or [])
        out.update(entry.get("github_accounts") or [])
    return frozenset(s.lower() for s in out if s and len(s) >= MIN_INDICATOR_LEN)


class ContentMarker:
    """EXPLORATORY file-level marker: does this file's text carry a payload indicator?

    A file that cannot be read (absent from the local marketplace checkout, or
    not decodable) is treated as carrying no indicator and recorded in
    `unresolved`, so the count of files this marker could not examine is
    reported rather than absorbed into the negative class.
    """

    def __init__(self, indicators):
        self.indicators = indicators
        self.unresolved = set()
        self._cache = {}

    def hits(self, loc: dict) -> frozenset:
        """Indicators found in this file's text; empty if none, unreadable, or absent."""
        key = (loc["marketplace"], loc["path"])
        if key not in self._cache:
            try:
                if MARKETPLACE_ROOT is None:
                    raise OSError("LIBRARIAN_CORPUS is unset")
                text = (MARKETPLACE_ROOT / key[0] / key[1]).read_text(
                    encoding="utf-8", errors="replace").lower()
            except (OSError, ValueError):
                self.unresolved.add(key)
                self._cache[key] = frozenset()
            else:
                self._cache[key] = frozenset(i for i in self.indicators if i in text)
        return self._cache[key]

    def __call__(self, loc: dict) -> bool:
        return bool(self.hits(loc))


def unresolved_in(clusters, marker) -> int:
    """Locations in `clusters` whose file the content marker could not read."""
    return sum(1 for c in clusters for l in c["locations"]
               if (l["marketplace"], l["path"]) in marker.unresolved)


def cluster_tp(clusters, is_tp) -> int:
    """Clusters satisfying a cluster-level predicate."""
    return sum(1 for c in clusters if is_tp(c))


def lift(is_malicious):
    """A file-level rule as the cluster-level rule of Section 3.4: any file malicious."""
    return lambda c: any(is_malicious(l) for l in c["locations"])


def weak_driver_counts(clusters, marker, is_study):
    """Files flagged by content alone, and how many owe that flag only to WEAK_INDICATOR.

    Content-only means: not attributed by account under study, but carrying at
    least one indicator. Reported because a content flag is a substring hit, so
    the reader needs to see how much of it rests on the weakest string.
    """
    only = [l for c in clusters for l in c["locations"]
            if not is_study(l) and marker.hits(l)]
    weak = sum(1 for l in only if set(marker.hits(l)) == {WEAK_INDICATOR})
    return len(only), weak


def candidate_table(clusters, candidates, rows):
    """Cluster-level TP for each candidate ground truth against Table 4's rows."""
    lines = ["## Candidate ground truths against Table 4", "",
             "Every rule reachable from this repository, evaluated on Table 4's own rows."
             " `all` is Table 4's \"All clusters\" row.", "",
             "**The scaffold rows are not precision figures.** `scaffold` is a tag the"
             " clustering pipeline assigns to its own output (an internal, single-marketplace"
             " cluster of >= 5 files with average similarity >= 0.98,"
             " `librarian/cli.py:1582-1585`), so a rule that ORs it in is measured partly"
             " against the tool being evaluated. Those rows measure how closely the triage"
             " behind Table 4 tracked the tool's structural tag; they are reconstructions of"
             " the ground truth, not measurements of precision.", "",
             "| candidate ground truth | " + " | ".join(
                 f">= {t}" if t is not None else "all" for t in rows) + " |",
             "|:--|" + "---:|" * len(rows)]
    for name, is_malicious in candidates:
        cells = []
        for t in rows:
            subset = clusters if t is None else [c for c in clusters if c["size"] >= t]
            cells.append(f"{cluster_tp(subset, is_malicious)}/{len(subset)}")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines.append("| **Table 4 as published** | " + " | ".join(
        f"**{TABLE4[t][0]}/{TABLE4[t][1]}**" for t in rows) + " |")
    lines.append("")
    return lines


def cross_check(measured, context, marker_reproduces, columns):
    """Compare measured cluster-level TP against Table 4; return lines and mismatches.

    Returns the lines and the mismatches among `measured` only: `context` rows are
    reported so the reader sees the full extent of the non-reproduction, but they
    are outside the thresholds this script computes detail for and outside the
    STOP rule the caller applies.
    """
    rows = sorted(list(measured) + list(context),
                  key=lambda r: (r[0] is None, -(r[0] or 0)))
    # Stated from the data rather than written as prose, so the sentence cannot
    # go stale if a rerun on different inputs changes what the marker recovers.
    deltas = [(th, tps["content"] - tps["study"]) for th, tps, _ in rows
              if tps["content"] != tps["study"]]
    gained = ", ".join(
        f"{d} cluster{'s' if d != 1 else ''} at "
        + (f">= {th}" if th is not None else "the all-clusters row")
        for th, d in deltas) or "no clusters at any row"

    disagree = [(th, tps, n) for th, tps, n in measured
                if th in TABLE4 and (tps["study"], n) != TABLE4[th]]
    shown = [(th, tps, n) for th, tps, n in rows
             if th in TABLE4 and (tps["study"], n) != TABLE4[th]]
    lines = ["## Cross-check against Table 4", "",
             "Section 3.4 of the paper counts a cluster as a true positive if it contains at"
             " least one file attributed to a documented attacker account, where the"
             " attribution may come from Antiy CERT's 12 authors, from Koi's IOC slugs, or"
             " from files confirmed through payload inspection. The strict and study columns"
             " implement the first clause, content tests part of the third, and the scaffold"
             " columns substitute the scan's own cluster tag for the whole rule; no rule"
             " available in this repository implements all three clauses.", "",
             "| row | " + " | ".join(columns) + " | Table 4 | study agrees |",
             "|:--|" + "---:|" * (len(columns) + 1) + ":--|"]
    for th, tps, n in rows:
        label = f">= {th}" if th is not None else "all clusters"
        published = f"{TABLE4[th][0]}/{TABLE4[th][1]}" if th in TABLE4 else "not in Table 4"
        agrees = "yes" if th in TABLE4 and (tps["study"], n) == TABLE4[th] else "NO"
        lines.append(f"| {label} | "
                     + " | ".join(f"{tps[c]}/{n}" for c in columns)
                     + f" | {published} | {agrees} |")
    lines.append("")
    if disagree:
        lines += [
            "**The rows marked NO do not reproduce, and the marker that would close the gap"
            " is unidentified.** The candidate table above rules out three explanations:", "",
            "- Koi's 341 IOC slugs are not the missing marker. Koi's list is not in this"
            " repository; Section 4.4 reports that 337 of the 341 resided in the archive and"
            " that all 337 appeared in clusters. `hightower6eu`, the single author whose"
            " 354-slug IOC subset the paper's threshold and ablation tables use, is present in"
            " every ground truth here, so its clustered files are already credited. Slug"
            " matching is not what separates the columns either: adding every skill slug"
            " `iocs.json` does carry leaves the >= 5 count at 41/163, as the candidate table"
            " above shows.",
            "- The identity of the account list is not the variable either. The March working"
            " notes, which are not part of this artifact, reach 60/163 at >= 5 from a"
            " 10-account list; this script scores that list at 41/163 on the same scan, and"
            " every account list in the candidate table lands between 37 and 41.",
            "- The remaining clause of Section 3.4, files confirmed through payload"
            " inspection, is the unaccounted-for one. The `content` column above tests it"
            " with the payload indicators iocs.json does carry, and "
            + ("closes the gap." if marker_reproduces else
               f"does not close it: over study it adds {gained}, and as the Definitions section explains"
               " the >= 5 gain is a benign mention rather than a payload."), "",
            "**Closest mechanical reconstruction: account attribution OR the scan's own"
            " `scaffold` cluster type.** The scan tags 44 clusters `scaffold` (internal to one"
            " marketplace, >= 5 files, average similarity >= 0.98) and the published Table 4"
            " carries a Scaffold row reading \"44/44\" (Section 4.4), so the triage behind"
            " Table 4 credited every scaffold cluster. `study OR scaffold` reproduces the"
            " >= 20 and >= 15 rows exactly and comes within one cluster at >= 10 (31 against"
            " 30) and one at >= 5 (59 against 60).",
            "",
            "The >= 10 row reproduces exactly under study (30/38); the scaffold rule's 31"
            " overshoots it by one. The Table 4 caption states the boundary of what the"
            " released ground truth reproduces: \"Only the ≥ 20 and ≥ 10 rows reproduce from"
            " the released ground truth.\" The >= 15 and >= 5 rows rest on per-cluster triage"
            " decisions that the released ground truth does not carry, so this script does not"
            " reproduce them. Differences of one cluster are what hand triage under Section"
            " 3.4's third clause would produce.",
            "",
            "**This reconstruction is circular, and the 44/44 row is where the circularity is"
            " clearest.** The `scaffold` tag is assigned by the same clustering pipeline whose"
            " output Table 4 scores (`librarian/cli.py:1582-1585`). That the published table"
            " credits all 44 scaffold clusters is at once the strongest evidence that the tag"
            " drove the triage and the plainest statement that the triage followed the"
            " tool's own structural signal; Section 3.4 states this circularity limitation for"
            " the ground truth as a whole. So 59/163 is a reconstruction of the ground truth,"
            " not a precision figure, and neither it nor any other scaffold row belongs in a"
            " precision claim. The scaffold rule is the closest mechanical reconstruction"
            " available, not an exact one: no rule in this repository reproduces every row, so"
            " the marker stays unidentified.", "",
            "Rows affected:", "",
        ] + [f"- {'>= ' + str(th) if th is not None else 'all clusters'}:"
             f" {tps['study']}/{n} here versus {TABLE4[th][0]}/{TABLE4[th][1]} in Table 4"
             for th, tps, n in shown] + [
            "",
            "Read every figure below as conditional on the ground truth named in its column,"
            " not as a restatement of Table 4.", "",
        ]
    return lines, disagree


def attribution_audit(clusters, malicious):
    """Counts backing the marketplace gate in account_of; returns report lines."""
    locs = [l for c in clusters for l in c["locations"]]
    claw = [l for l in locs if l["marketplace"] == CLAWHUB]
    other = [l for l in locs if l["marketplace"] != CLAWHUB]
    claw_skills = sum(1 for l in claw if l["path"].startswith("skills/"))
    other_skills = sum(1 for l in other if l["path"].startswith("skills/"))
    ungated = [l for l in other
               if l["path"].startswith("skills/") and len(l["path"].split("/")) >= 4]
    leaked = sum(1 for l in ungated if l["path"].split("/")[1] in malicious)
    return [
        "## Attribution audit",
        "",
        f"- locations in scan: {len(locs)} ({len(claw)} ClawHub archive, {len(other)} other marketplaces)",
        f"- ClawHub locations whose path starts with `skills/`: {claw_skills}/{len(claw)}",
        f"- non-ClawHub locations whose path starts with `skills/`: {other_skills}/{len(other)},"
        f" of which {len(ungated)} have >= 4 segments and so would be attributed by a path-only rule",
        f"- of those {len(ungated)}, the number whose second path segment is a known-malicious"
        f" account under any ground truth: {leaked}",
        "",
        "The marketplace gate in `account_of` therefore changes no number below on this scan;"
        " it prevents a cross-marketplace misattribution that the path shapes otherwise allow.",
        "",
    ]


def preamble(antiy, study, indicators, marker, clusters, is_study, content_all):
    """Header of the results file: inputs, definitions, and the denominator caveat."""
    # Derived, not written in: the same helper that feeds the per-threshold lines.
    content_only, weak_only = weak_driver_counts(clusters, marker, is_study)
    return [
        "# File-level precision within size-thresholded clusters (90% scan, 2026-03-14)",
        "",
        f"Input scan: `{SCAN.name}` (the 90% Jaccard, SKILL.md-only scan)."
        f" Ground truth: `{IOCS.relative_to(IOCS.parents[1])}`. Generated by `{Path(__file__).name}`,"
        " run with LIBRARIAN_CORPUS set: `python paper/sources/scans/file_level_precision.py`.",
        "",
        "This file reports, for the clusters of the scan with >= 20, >= 10 and >= 5 files, the"
        " share of files that are malicious under three ground truths, the cluster-level true"
        " positives each ground truth yields, and how many of those clusters are pure versus"
        " mixed. It supports one sentence of Section 4.4 (IOC Validation): \"File-level"
        " precision, promised in Section 3.4, is 305 of 307 files (0.993) at ≥ 20; at ≥ 10"
        " the corresponding figure is membership-level, 557 of 682 memberships over 643"
        " distinct files, 0.817 (per-cluster results are among the files released with the"
        " code, Appendix C).\" The study rows below are those figures with their per-cluster"
        " breakdown. The cross-check section is the computation behind the Table 4 caption in"
        " the same section: \"Only the ≥ 20 and ≥ 10 rows reproduce from the released ground"
        " truth.\" Section 3.4 (Ground Truth and Validation) defines the two levels: \"We report"
        " precision at both cluster level (fraction of clusters containing confirmed malicious"
        " content) and file level (fraction of clustered files confirmed malicious).\"",
        "",
        "## Definitions",
        "",
        f"- **strict**: {len(antiy)} accounts documented by Antiy CERT. A file is malicious if"
        " its ClawHub archive path is under one of them.",
        f"- **study**: {len(study)} accounts, the Antiy 12 together with the"
        f" {len(study) - len(antiy)} further accounts in `clawhub_authors` that this study"
        " confirmed by payload inspection. Same path-attribution rule.",
        f"- **content** (EXPLORATORY, not used for any published figure): malicious under **study**, or"
        f" the file's text on disk contains one of {len(indicators)} payload indicators, drawn"
        f" from {len(INDICATOR_CATEGORIES)} of the eight `payload_infrastructure` categories in"
        f" `iocs.json` ({', '.join('`' + c + '`' for c in INDICATOR_CATEGORIES)}) plus the"
        " literals `openclawcli` and `clawcli`. Files are read from"
        " `$LIBRARIAN_CORPUS/<marketplace>/<path>`; a file that"
        " does not resolve there is counted as carrying no indicator and reported as"
        " unreadable.",
        f"  The other three categories are excluded. `ip_addresses` and `file_hashes` are"
        " inert: adding them changes no figure in this file. `social_engineering_patterns` is"
        " excluded because it is not inert and would wreck the marker: its ZIP-password"
        " literal `openclaw` is long enough to survive the length filter and matches most of"
        f" the corpus, taking the all-clusters content count from {content_all} to"
        f" {SOCIAL_ENGINEERING_ALL_CLUSTERS} (that second figure is"
        " recorded rather than recomputed on each run, since reproducing it means building an"
        " indicator set this script deliberately does not use).",
        "",
        "**What a content match is, and is not.** A content hit is a case-folded substring"
        " search over the file's text. It shows that a file names an indicator, not that the"
        " file delivers a payload: a benign document about the attack, or about a legitimate"
        " tool with a colliding name, matches just as a malicious one does. The dominant and"
        f" weakest driver is `{WEAK_INDICATOR}`, which `iocs.json` records as a typosquat of"
        " clawhub.com with status \"unknown\" rather than as a confirmed payload host; it"
        f" accounts for {weak_only} of the {content_only} content-only files in the scan,"
        " more than every other indicator combined. Each threshold below reports how many of its content-only files"
        f" rest on `{WEAK_INDICATOR}` alone, so they can be subtracted.",
        "",
        "The quality of the content gains is therefore uneven. At >= 20 the two files content"
        " adds are unambiguous: cluster 854 matches `openclawcli`, `openclawcli.zip`,"
        " `ddoy233` and a glot.io payload snippet, and cluster 1543 matches a glot.io snippet"
        " and `hedefbari`. The single cluster content adds over study at >= 5 is cluster 1478,"
        " six files documenting the `clawdhub` npm CLI (for example"
        " `clawhub-archive/skills/steipete/clawdhub/SKILL.md`, whose text is install"
        f" instructions for `npm i -g clawdhub`); every one of them matches on `{WEAK_INDICATOR}`"
        " alone and none is evidence of anything. Treat the >= 5 content figures accordingly.",
        "",
        "- **pure**: every file in the cluster is malicious under that ground truth."
        " **mixed**: at least one file is malicious and at least one is not. Pure and mixed"
        " partition that ground truth's true positives, so pure + mixed = TP by construction.",
        "",
        "**Denominator.** File-level precision below divides by ALL files in the thresholded"
        " set, including the files inside false-positive clusters. It is not a rate within"
        " true-positive clusters: at >= 10 the divisor 682 is the file count of all 38"
        " clusters, not of the 30 true positives. Read it as the share an operator"
        " auto-quarantining every cluster at that size would sweep up. Files are counted as"
        " cluster memberships, one per location record in the scan, so a file that sits in"
        " more than one cluster counts once per cluster; the paper reports the >= 10 figure"
        " as membership-level for that reason. At >= 20 the two"
        " readings coincide, but only because all 11 clusters there are true positives.",
        "",
        f"Files the content marker could not read: {unresolved_in(clusters, marker)} of"
        f" {sum(len(c['locations']) for c in clusters)} locations in the scan.",
        "",
        "This file is written before the run's Table 4 check, so a failing run still produces"
        " it. Trust the script's exit status, not the presence of this file.",
        "",
    ]


def main() -> int:
    # Without this the content marker reads nothing, every file lands in
    # unresolved, and the run still exits 0 with a column of quiet zeros.
    if MARKETPLACE_ROOT is None or not MARKETPLACE_ROOT.is_dir():
        print(f"no corpus at {MARKETPLACE_ROOT}; set LIBRARIAN_CORPUS to the corpus snapshot "
              "recorded in paper/supplementary/repository-commits.md. The content marker "
              "cannot read any file, so its column would be silently empty", file=sys.stderr)
        return 1

    scan = json.loads(SCAN.read_text())
    iocs = json.loads(IOCS.read_text())
    clusters = scan["clusters"]

    # Integrity check on the denominator: every file-level count below is
    # len(locations), so a cluster whose recorded size disagrees with its
    # location list would quietly change both numerator and denominator.
    mismatched = [c["cluster_id"] for c in clusters
                  if c["size"] != len(c["locations"])]
    if mismatched:
        print(f"cluster size disagrees with len(locations) for {len(mismatched)} clusters: "
              f"{mismatched[:10]}", file=sys.stderr)
        return 1

    antiy_refs = [ref for ref in iocs["metadata"]["references"]
                  if ref.get("source") == "Antiy CERT"]
    if len(antiy_refs) != 1:
        print(f"expected exactly 1 Antiy CERT reference in iocs.json, found {len(antiy_refs)}",
              file=sys.stderr)
        return 1
    antiy = set(antiy_refs[0]["authors_documented"])
    if len(antiy) != 12:
        print(f"expected 12 Antiy accounts in iocs.json, found {sorted(antiy)}", file=sys.stderr)
        return 1
    study = set(iocs["clawhub_authors"]) | antiy   # Antiy accounts absent from clawhub_authors are still malicious under 'study'

    indicators = payload_indicators(iocs)
    marker = ContentMarker(indicators)
    is_strict = lambda l: account_of(l) in antiy
    is_study = lambda l: account_of(l) in study
    # marker first, deliberately: `is_study(l) or marker(l)` would short-circuit
    # on files already attributed by account and never attempt to read them, so
    # the unresolved count would silently exclude them.
    is_content = lambda l: marker(l) or is_study(l)
    tests = (("strict", is_strict), ("study", is_study), ("content", is_content))

    # One complete pass before anything reports: the callers below use any(),
    # which short-circuits, so without this the set of files the marker actually
    # attempted would depend on cluster ordering and the unresolved count would
    # understate how many files went unexamined. The cache makes the pass free
    # for every later call.
    for c in clusters:
        for l in c["locations"]:
            marker(l)

    is_scaffold = lambda c: c["type"] == SCAFFOLD_TYPE
    # Cluster-level rules for the cross-check and the candidate table. The first
    # three are the file-level rules lifted by Section 3.4's "any file"; the
    # scaffold pair is a cluster property and has no file-level counterpart, so it
    # never enters `tests` and never appears in the per-cluster file tables.
    cluster_rules = [(name, lift(pred)) for name, pred in tests] + [
        ("strict or scaffold", lambda c: is_scaffold(c) or lift(is_strict)(c)),
        ("study or scaffold", lambda c: is_scaffold(c) or lift(is_study)(c)),
    ]
    columns = [name for name, _ in cluster_rules]

    slugs = {s.lower() for rec in iocs["clawhub_authors"].values()
             for key in ("skill_slugs_with_payload", "skill_slugs_without_payload")
             for s in (rec.get(key) or [])}
    candidates = [
        (f"Antiy CERT accounts (strict), {len(antiy)}", lift(is_strict)),
        (f"`clawhub_authors`, {len(iocs['clawhub_authors'])}",
         lift(lambda l: account_of(l) in set(iocs["clawhub_authors"]))),
        (f"union of the two (study), {len(study)}", lift(is_study)),
        (f"March working-notes account list, {len(MARCH_ACCOUNTS)}",
         lift(lambda l: account_of(l) in MARCH_ACCOUNTS)),
        (f"study plus the {len(slugs)} `iocs.json` skill slugs",
         lift(lambda l: is_study(l) or slug_of(l) in slugs)),
        (f"content marker (exploratory), {len(indicators)} indicators", lift(is_content)),
        (f"scaffold cluster type alone, {sum(1 for c in clusters if is_scaffold(c))} clusters",
         is_scaffold),
        ("strict OR scaffold type", cluster_rules[-2][1]),
        ("study OR scaffold type", cluster_rules[-1][1]),
    ]

    body, measured = [], []
    for th in THRESHOLDS:
        big = [c for c in clusters if c["size"] >= th]
        rows, tot_files = [], 0
        mal = {name: 0 for name, _ in tests}
        tp = {name: 0 for name, _ in tests}
        pure = {name: 0 for name, _ in tests}
        mixed = {name: 0 for name, _ in tests}
        for c in sorted(big, key=lambda c: -c["size"]):
            n = len(c["locations"])
            if n == 0:
                print(f"cluster {c['cluster_id']}: no locations, so its file-level share "
                      f"is undefined", file=sys.stderr)
                return 1
            counts = {name: sum(1 for l in c["locations"] if pred(l))
                      for name, pred in tests}
            # strict implies study implies content, and all three count files, so
            # the counts are ordered; a violation would mean the ground-truth
            # sets or the attribution rules had diverged.
            if not 0 <= counts["strict"] <= counts["study"] <= counts["content"] <= n:
                print(f"cluster {c['cluster_id']}: expected 0 <= strict <= study <= content "
                      f"<= files, got {counts['strict']} <= {counts['study']} <= "
                      f"{counts['content']} <= {n}", file=sys.stderr)
                return 1
            tot_files += n
            for name, _ in tests:
                k = counts[name]
                mal[name] += k
                if k:
                    tp[name] += 1
                    pure[name] += (k == n)
                    mixed[name] += (k != n)
            rows.append("| {} | {} | {} | {} | {} | {:.2f} | {:.2f} | {:.2f} |".format(
                c["cluster_id"], n, counts["strict"], counts["study"], counts["content"],
                counts["strict"] / n, counts["study"] / n, counts["content"] / n))
        for name, _ in tests:
            if pure[name] + mixed[name] != tp[name]:
                print(f"threshold {th}, {name}: pure + mixed does not equal TP "
                      f"({pure[name]}+{mixed[name]} vs {tp[name]})", file=sys.stderr)
                return 1
        # Cluster-level TP for every rule, including the scaffold pair that has no
        # file-level counterpart. The three shared names are cross-checked against
        # the loop's own counts below, so the two computations cannot diverge.
        tp_all = {name: cluster_tp(big, pred) for name, pred in cluster_rules}
        for name, _ in tests:
            if tp_all[name] != tp[name]:
                print(f"threshold {th}, {name}: cluster-level TP computed two ways disagrees "
                      f"({tp_all[name]} vs {tp[name]})", file=sys.stderr)
                return 1
        measured.append((th, tp_all, len(big)))
        # Guarded rather than written as trailing conditional expressions: an
        # empty thresholded set must not emit a blank list entry into the file.
        if tot_files:
            precision = [
                f"- file-level precision over all files at this threshold, {name}:"
                f" {mal[name]}/{tot_files} = {mal[name] / tot_files:.3f}"
                for name, _ in tests
            ]
        else:
            precision = ["- no files"]
        content_only, weak_only = weak_driver_counts(big, marker, is_study)
        body += [f"## Clusters with >= {th} files: {len(big)}", "",
                 f"- files in these clusters: {tot_files}"
                 f" ({unresolved_in(big, marker)} unreadable by the content marker)",
                 f"- files flagged by content alone, that is not attributed by account:"
                 f" {content_only}, of which {weak_only} match on `{WEAK_INDICATOR}` and"
                 f" nothing else and should be discounted",
                 ] + [f"- cluster-level TP ({name}): {tp[name]}/{len(big)};"
                      f" pure {pure[name]}, mixed {mixed[name]}"
                      for name, _ in tests] + precision + [
                 "",
                 "| cluster | files | malicious (strict) | malicious (study) | malicious (content) "
                 "| share strict | share study | share content |",
                 "|---:|---:|---:|---:|---:|---:|---:|---:|"] + rows + [""]

    context = []
    for th in CONTEXT_ROWS:
        subset = clusters if th is None else [c for c in clusters if c["size"] >= th]
        context.append((th, {name: cluster_tp(subset, pred) for name, pred in cluster_rules},
                        len(subset)))

    marker_reproduces = all(
        tps["content"] == TABLE4[th][0]
        for th, tps, _ in list(measured) + list(context) if th in TABLE4)
    cross, disagree = cross_check(measured, context, marker_reproduces, columns)
    content_all = next(tps["content"] for th, tps, _ in context if th is None)
    lines = (preamble(antiy, study, indicators, marker, clusters, is_study, content_all)
             + attribution_audit(clusters, antiy | study)
             + candidate_table(clusters, candidates, (20, 15, 10, 5, None))
             + cross + body)
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    # The exit status binds the two thresholds Section 4.4 quotes and the Table 4 caption names,
    # under the study definition only; the Table 4 caption names those two rows as
    # the ones the released ground truth reproduces. A disagreement there would
    # mean this attribution rule is not the one behind Table 4, which
    # invalidates every number above.
    binding = [th for th, _, _ in disagree if th in (20, 10)]
    if binding:
        print(f"STOP: cluster-level TP under the study definition does not reproduce "
              f"Table 4 at threshold(s) {binding}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
