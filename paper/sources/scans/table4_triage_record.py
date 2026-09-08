#!/usr/bin/env python3
"""Per-cluster triage record for Table 4 (precision and recall at cluster size thresholds).

Supports Table 4 in Section 4.4 (IOC Validation), whose caption states that only the >= 20
and >= 10 rows reproduce from the released ground truth. The true-positive rule is stated in
Section 3.4 (Ground Truth and Validation): "A true positive is a cluster containing at least
one file attributed to a documented attacker account (Antiy CERT's 12 authors, Koi IOC slugs,
or files confirmed through payload inspection)." The >= 20 and >= 10 rows reproduce from the
account clause alone; the >= 15, >= 5 and all-clusters rows do not. This record lists, for
every cluster in those three rows, the attributed accounts, the slug hits, and the verdict
each candidate rule returns, so the rows can be checked against evidence rather than against
a stored total.

Inputs: `scan_20260314_threshold90_skillonly.json` beside this script and `paper/iocs.json`.
Account attribution is imported from `file_level_precision.py` rather than restated, so the
two scripts apply one rule by construction. Nothing here reads the corpus: every figure is a
function of those two files, and LIBRARIAN_CORPUS is not needed.

Output: `table4-triage-record-20260907.md` beside this script.

Run from the repository root:
  python paper/sources/scans/table4_triage_record.py
"""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from file_level_precision import (  # noqa: E402
    account_of, slug_of, SCAFFOLD_TYPE, TABLE4, CLAWHUB)

SCAN = HERE / "scan_20260314_threshold90_skillonly.json"
IOCS = HERE.parents[1] / "iocs.json"
OUT = HERE / "table4-triage-record-20260907.md"
REPO = HERE.parents[2]
NON_REPRODUCING = (15, 5, None)   # the Table 4 rows this record exists for
EXAMPLES_PER_CLUSTER = 3


def P(text):
    """A paragraph written across source lines, collapsed to one output line."""
    return " ".join(text.split())


def load_ground_truth(iocs):
    """Antiy 12, the 18-account study union, and the iocs.json slugs; guards as in file_level_precision."""
    refs = [r for r in iocs["metadata"]["references"] if r.get("source") == "Antiy CERT"]
    if len(refs) != 1:
        raise ValueError(f"expected 1 Antiy CERT reference in iocs.json, found {len(refs)}")
    antiy = set(refs[0]["authors_documented"])
    if len(antiy) != 12:
        raise ValueError(f"expected 12 Antiy accounts, got {sorted(antiy)}")
    study = set(iocs["clawhub_authors"]) | antiy
    keys = ("skill_slugs_with_payload", "skill_slugs_without_payload")
    return antiy, study, {s.lower() for rec in iocs["clawhub_authors"].values()
                          for key in keys for s in (rec.get(key) or [])}


def verdicts(cluster, study, slugs):
    """Per-cluster evidence: attributed accounts, slug hits, and each rule's verdict."""
    accounts = {}
    for acct in (a for a in map(account_of, cluster["locations"]) if a in study):
        accounts[acct] = accounts.get(acct, 0) + 1
    hit = sorted({slug_of(loc) for loc in cluster["locations"]} & slugs)
    slug_files = sum(1 for loc in cluster["locations"] if slug_of(loc) in slugs)
    return {"accounts": accounts, "attributed": sum(accounts.values()), "slug_files": slug_files,
            "slug_hits": hit, "account_tp": bool(accounts),
            "scaffold_tp": cluster["type"] == SCAFFOLD_TYPE, "slug_tp": slug_files > 0}


def market_codes(clusters):
    """Marketplace codes: token initials, disambiguated by a digit in sorted order."""
    codes, used = {}, {}
    for name in sorted({m for c in clusters for m in c["marketplaces"]}):
        base = "".join(tok[0] for tok in name.split("-")) or name[:2]
        used[base] = n = used.get(base, 0) + 1
        codes[name] = base if n == 1 else f"{base}{n}"
    return codes


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


def head_commit():
    """Commit the record was generated at, or 'unknown' outside a checkout.

    Recorded only when this checkout is the public repository; a run inside a
    private working repository writes the redaction token instead, because the
    record is published and that history is not.
    """
    if not is_public_repo(REPO):
        return PRIVATE_HISTORY
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], check=True,
                              capture_output=True, text=True).stdout.strip() or "unknown"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def row_counts(clusters, study, slugs, threshold):
    """(clusters in row, account TP, account-or-scaffold TP, plus-slug TP, disagreements)."""
    v = [verdicts(c, study, slugs) for c in clusters if threshold is None or c["size"] >= threshold]
    return (len(v), sum(1 for x in v if x["account_tp"]),
            sum(1 for x in v if x["account_tp"] or x["scaffold_tp"]),
            sum(1 for x in v if x["account_tp"] or x["scaffold_tp"] or x["slug_tp"]),
            sum(1 for x in v if x["account_tp"] != x["scaffold_tp"]))


def cells(cluster, codes, v=None, flag=None):
    """The descriptive columns every table shares; the account evidence when `v` is given; and,
    when `flag` is given, the account verdict, the scaffold verdict and the flag, in that order."""
    row = (f"{cluster['cluster_id']} | {cluster['size']} |"
           f" {'+'.join(codes[m] for m in cluster['marketplaces'])} |"
           f" {cluster['avg_similarity']:.3f} | {cluster['type']}")
    if v is None:
        return row
    accts = sorted(v["accounts"].items(), key=lambda kv: (-kv[1], kv[0]))
    row += f" | {v['attributed']} | " + (", ".join(f"{a} ({n})" for a, n in accts) or "-")
    return row if flag is None else (f"{row} | {'TP' if v['account_tp'] else 'not'} |"
                                     f" {'TP' if v['scaffold_tp'] else 'not'} | {flag}")


def reconciliation(clusters, study, slugs):
    """What each candidate rule scores on every Table 4 row, against the published count."""
    lines = ["## The three rows that do not reproduce", "", P("""
        `account` is the 18-account study rule of `file_level_precision.py` (Antiy CERT's 12 plus the six
        further `clawhub_authors` accounts), lifted to clusters by Section 3.4's "at least one file";
        `scaffold` is the scan's own cluster tag (single marketplace, >= 5 files, average similarity >=
        0.98); `inventory slug` is a file whose directory name is one of the 734 slugs `iocs.json`
        inventories under the study's 11 `clawhub_authors`. It stands in for Section 3.4's Koi-slug clause
        because Koi's published 341-slug list is not part of this artifact, and `file_level_precision.py`
        argues in `cross_check()`, under "What has been ruled out", that "Koi's 341 IOC slugs
        are not the missing marker"."""), "",
        "| row | published TP | account | account OR scaffold | account OR scaffold OR inventory"
        " slug | gap under account | gap under account OR scaffold | rules disagree |",
        "|:--|---:|---:|---:|---:|---:|---:|---:|"]
    plus_by_row, names = {}, {}
    for th in (20, 15, 10, 5, None):
        n, acct, both, plus, dis = row_counts(clusters, study, slugs, th)
        pub = TABLE4[th][0]
        plus_by_row[th] = (pub, plus)
        if TABLE4[th][1] != n:
            raise ValueError(f"row {th}: scan has {n}, Table 4 says {TABLE4[th][1]}")
        names[th] = name = f">= {th}" if th is not None else "all clusters"
        lines.append(f"| {name}{'' if th in NON_REPRODUCING else ' *'} | {pub}/{n} | {acct} |"
                     f" {both} | {plus} | {pub - acct} | {pub - both} | {dis} |")
    tallies = ", ".join(f"{plus} against {pub} at {names[th]}"
                       for th, (pub, plus) in plus_by_row.items() if th in NON_REPRODUCING)
    left = {th: plus_by_row[th][0] - plus_by_row[th][1] for th in NON_REPRODUCING}
    lines += ["", P("""Rows marked `*` reproduce from the account clause alone and are not triaged
        here. A negative gap means the rule credits more clusters than Table 4 publishes, as
        `account OR scaffold` does at >= 10."""), "", P(f"""**Adding the author-inventory slug rule
        closes the all-clusters row arithmetically and no part of the >= 5 gap.** The account rule in
        `file_level_precision.py` implements only the first of Section 3.4's three routes, so on its own
        it misses every cluster whose sole evidence is a slug. Adding this stand-in for
        the second gives {tallies}: every cluster it adds is below size 5, so the >= 5 count does not
        move and the below-5 part of the all-clusters row lands exactly on the published 44, leaving
        {left[5]} cluster at >= 5 and {left[None] - left[5]} elsewhere for the payload-inspection
        clause. The next section qualifies that arithmetic: most of those nine match on a
        short or generic slug."""), ""]
    return lines


def size_tables(clusters, study, slugs, codes):
    """One row per cluster in the >= 5 set, then the all-clusters row below size 5."""
    ge5 = sorted([c for c in clusters if c["size"] >= 5], key=lambda c: (-c["size"], c["cluster_id"]))
    lines = [f"## Every cluster in the >= 5 row ({len(ge5)} clusters)", "", P("""
        `flag` is `disagree` where the account and scaffold rules give different verdicts, and `residual`
        where neither credits the cluster: if the published 60 includes the 59 credited here, one more comes
        from this pool. Blank means both rules agree it is a true positive."""),
        "",
        "| cluster | size | marketplaces | avg sim | type | attributed files | accounts | account |"
        " scaffold | flag |", "|---:|---:|:--|---:|:--|---:|:--|:--|:--|:--|"]
    counts = {"disagree": 0, "residual": 0, "": 0}
    for c in ge5:
        v = verdicts(c, study, slugs)
        flag = "disagree" if v["account_tp"] != v["scaffold_tp"] else "" if v["account_tp"] else "residual"
        counts[flag] += 1
        lines.append(f"| {cells(c, codes, v, flag)} |")
    lines += ["", P(f"""Flagged for confirmation: {counts['disagree']} `disagree` and
        {counts['residual']} `residual`; the other {counts['']} are credited by both rules."""), ""]
    small = [c for c in clusters if c["size"] < 5]
    credited, slug_only = [], []
    for c in sorted(small, key=lambda c: (-c["size"], c["cluster_id"])):
        v = verdicts(c, study, slugs)
        if v["account_tp"] or v["scaffold_tp"]:
            credited.append((c, v))
        elif v["slug_tp"]:
            slug_only.append((c, v))
    pool = len(small) - len(credited) - len(slug_only)
    pub_small = TABLE4[None][0] - TABLE4[5][0]
    residue = pub_small - len(credited) - len(slug_only)
    with_claw = sum(1 for c in small if CLAWHUB in c["marketplaces"])
    near = sum(1 for c in small if c["avg_similarity"] >= 0.98)
    lines += [f"## The all-clusters row below size 5 ({len(small)} clusters)", "", P(f"""
        Table 4 publishes {TABLE4[None][0]} true positives over {TABLE4[None][1]} clusters and
        {TABLE4[5][0]} over the {TABLE4[5][1]} of size >= 5, so {pub_small} of them are below size 5. The
        account rule credits {len(credited)}; no cluster below size 5 can carry the scaffold tag, which
        needs >= 5 files, so that rule adds none; the inventory-slug rule credits {len(slug_only)} more, for
        {len(credited) + len(slug_only)} against the published {pub_small}, leaving {residue} for the
        payload-inspection clause out of a pool of {pool} that no released rule credits."""), "",
        f"### Credited by the account rule ({len(credited)})", "",
        "| cluster | size | marketplaces | avg sim | type | attributed files | accounts |",
        "|---:|---:|:--|---:|:--|---:|:--|"]
    lines += [f"| {cells(c, codes, v)} |" for c, v in credited]
    weak = sorted({h for _, v in slug_only for h in v["slug_hits"] if len(h) <= 8})
    lines += ["", f"### Credited by the author-inventory slug rule only ({len(slug_only)})", "", P(f"""
        These carry no file under a documented account and no scaffold tag, but hold a file whose directory
        name is in the `iocs.json` author inventory. Section 3.4 counts slug attribution as a true positive,
        so under the paper's rule they qualify; the account-only rule of
        `file-level-precision-20260907.md` does not credit them. **The matched slug decides whether a credit
        is warranted.** Slug matching compares directory names, and {len(weak)} of the slugs matched here are
        short or generic ({', '.join('`' + w + '`' for w in weak)}), which collide with benign directories
        under accounts nobody has documented; the paths below show that happening. That the arithmetic lands
        on the published total does not show that these are the nine clusters the triage credited."""), "",
        "| cluster | size | marketplaces | avg sim | type | matched slugs | files |",
        "|---:|---:|:--|---:|:--|:--|:--|"]
    lines += [f"| {cells(c, codes)} | {', '.join('`' + h + '`' for h in v['slug_hits'])} | "
              + "<br>".join(f"`{l['marketplace']}/{l['path']}`" for l in c["locations"]) + " |"
              for c, v in slug_only]
    lines += ["", P(f"""**Evidence available for the payload-inspection clause below size 5.** The
        `iocs.json` payload markers, applied to file text as in the exploratory `content` column of
        `file_level_precision.py` (which reads the corpus this script does not), add 13 clusters over the
        account rule at the all-clusters row; `file-level-precision-20260907.md` gives their dominant driver
        as the `clawdhub.com` typosquat, which `iocs.json` carries with status "unknown". Structural
        properties are weaker still: {with_claw} of the {len(small)} clusters here hold a ClawHub archive
        location and {near} reach the scaffold tag's 0.98 average similarity."""), ""]
    return lines, counts, {"small_credited": len(credited), "small_slug_only": len(slug_only),
                           "small_pool": pool, "small_published": pub_small, "small_residue": residue}


def how_to_confirm(clusters, study, slugs):
    """Which clusters to open, in what order, and where their files live."""
    pairs = [(c, verdicts(c, study, slugs)) for c in clusters if c["size"] >= 5]
    dis = sorted([p for p in pairs if p[1]["account_tp"] != p[1]["scaffold_tp"]],
                 key=lambda cv: (-cv[0]["size"], cv[0]["cluster_id"]))
    lines = ["## How to confirm", "", P(f"""
        The {len(dis)} `disagree` clusters come first: one rule credits each and the other does not, so each
        needs a reading of its files. Within them the clusters at >= 15 lead, because that row is published
        as 23/23 and a single cluster there decides a 100% precision claim. The `residual` clusters at >= 5
        come last: if the published 60 includes the 59 credited here, one more cluster comes from that pool,
        and no released rule says which. Files live under `$LIBRARIAN_CORPUS/<marketplace>/<path>`; up to
        {EXAMPLES_PER_CLUSTER} per cluster are shown, ClawHub archive first, and the full location list is in
        the scan JSON under `cluster_id`."""), ""]
    for c, v in dis:
        rule = "account only" if v["account_tp"] else "scaffold only"
        locs = sorted(c["locations"], key=lambda l: (l["marketplace"] != CLAWHUB, l["path"]))
        lines.append(f"- **cluster {c['cluster_id']}** ({c['size']} files, {c['type']}, avg sim"
                     f" {c['avg_similarity']:.3f}, TP under {rule})")
        lines += [f"  - `{l['marketplace']}/{l['path']}`" for l in locs[:EXAMPLES_PER_CLUSTER]]
    lines.append("")
    return lines, len(dis)


def main() -> int:
    self_test()
    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    iocs = json.loads(IOCS.read_text(encoding="utf-8"))
    commit, clusters = head_commit(), scan["clusters"]
    antiy, study, slugs = load_ground_truth(iocs)
    codes = market_codes(clusters)
    header = ["# Table 4 per-cluster triage record", "", P("""
        This file supports Table 4 of the paper (Section 4.4, IOC Validation), whose caption states that
        only the >= 20 and >= 10 rows reproduce from the released ground truth. It lists every cluster in
        the three rows that do not (>= 15, >= 5 and all clusters) with the evidence each candidate rule
        finds, under the true-positive rule of Section 3.4 (Ground Truth and Validation): "A true positive
        is a cluster containing at least one file attributed to a documented attacker account (Antiy CERT's
        12 authors, Koi IOC slugs, or files confirmed through payload inspection)." The published rows come
        from the hand triage Section 4.4 describes, whose per-cluster decisions are not part of the released
        ground truth; a verdict here is what a candidate rule returns, not a record of that triage."""), "",
        f"Generated by `{Path(__file__).name}` at commit `{commit}`. Regenerate from the repository"
        " root with:", "", f"    python paper/sources/scans/{Path(__file__).name}", "",
        P(f"""Inputs: `paper/sources/scans/{SCAN.name}` (the 90% Jaccard, SKILL.md-only scan of
        2026-03-14) and `paper/iocs.json` ({len(antiy)} Antiy CERT accounts,
        {len(iocs['clawhub_authors'])} `clawhub_authors`, {len(slugs)} inventoried slugs). Account
        attribution is imported from `file_level_precision.py`, not reimplemented, and nothing here reads the
        corpus, so LIBRARIAN_CORPUS is not needed, every figure is a function of those two files, and the run
        is deterministic; the commit line is the only part that varies with repository state."""), "",
        P("""**Self-test.** Before either input is read the script runs `self_test()` on a
        five-cluster synthetic scan with a hand-computed answer: clusters credited by both rules, by the
        account rule only, by the scaffold tag only, by neither, and one two-file cluster whose sole evidence
        is an inventory slug. It asserts each cluster's account and slug evidence, the >= 5 row counts (4
        clusters, 2 by account, 3 by account OR scaffold, 3 with the slug rule, 2 disagreements), one rendered
        table row, and the marketplace codes, exiting non-zero on any failure."""), "",
        "**Marketplace codes.** " + "; ".join(
            f"`{c}` {n}" for n, c in sorted(codes.items(), key=lambda kv: kv[1])) + ".", ""]
    tables, counts, small = size_tables(clusters, study, slugs, codes)
    confirm, n_dis = how_to_confirm(clusters, study, slugs)
    stats = {"ge5_disagree": counts["disagree"], "ge5_residual": counts["residual"],
             "ge5_undisputed": counts[""], "confirm_first": n_dis, **small}
    lines = header + reconciliation(clusters, study, slugs) + tables + confirm
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}: " + ", ".join(f"{k} {v}" for k, v in stats.items()))
    return 0


def self_test():
    """Startup check on a toy scan with a hand-computed answer."""
    def clu(cid, kind, sim, locs):
        return {"cluster_id": cid, "size": len(locs), "type": kind, "avg_similarity": sim,
                "marketplaces": sorted({l["marketplace"] for l in locs}), "locations": locs}

    def loc(mkt, path): return {"marketplace": mkt, "path": path}  # noqa: E704
    benign = [loc("other", f"skills/benign/y{i}/SKILL.md") for i in range(5)]
    toy = [clu(1, SCAFFOLD_TYPE, 0.99, [loc(CLAWHUB, f"skills/a01/p{i}/SKILL.md") for i in range(5)]),
           clu(2, "cross-marketplace", 0.95, [loc(CLAWHUB, "skills/a02/x/SKILL.md")] + benign),
           clu(3, SCAFFOLD_TYPE, 1.0, benign), clu(4, "internal", 0.91, benign + benign[:2]),
           clu(5, "internal", 1.0, [loc(CLAWHUB, "skills/benign/known-slug/SKILL.md"),
                                    loc(CLAWHUB, "skills/benign/other/SKILL.md")])]
    study, slugs = {f"a{i:02d}" for i in range(1, 19)}, {"known-slug"}
    got = {c["cluster_id"]: verdicts(c, study, slugs) for c in toy}
    # (account TP, scaffold TP, files attributed, slug-matched files, slugs), computed by hand.
    expected = {1: (True, True, 5, 0, []), 2: (True, False, 1, 0, []), 3: (False, True, 0, 0, []),
                4: (False, False, 0, 0, []), 5: (False, False, 0, 1, ["known-slug"])}
    codes = {CLAWHUB: "ca", "other": "o"}
    checks = [((v["account_tp"], v["scaffold_tp"], v["attributed"], v["slug_files"],
                v["slug_hits"]), expected[cid]) for cid, v in got.items()]
    checks += [(cells(toy[1], codes, got[2], "disagree"),   # column order of the >= 5 table
                "2 | 6 | ca+o | 0.950 | cross-marketplace | 1 | a02 (1) | TP | not | disagree"),
               (got[1]["accounts"], {"a01": 5}), (got[2]["accounts"], {"a02": 1}),
               (row_counts(toy, study, slugs, 5), (4, 2, 3, 3, 2)), (market_codes(toy), codes)]
    for got_value, want in checks:
        if got_value != want:
            raise AssertionError(f"self-test: got {got_value}, expected {want}")


if __name__ == "__main__":
    raise SystemExit(main())
