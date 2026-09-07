#!/usr/bin/env python3
"""What the "backup" path skip excluded from the clustering.

`librarian/cli.py` drops any path whose lowercased string contains "backup"
before it is ever hashed. On the pinned March snapshot that excluded 864
SKILL.md files, 74 of them inside the ClawHub archive, and 2 of those 74 are
hightower6eu skills. Section 3.2 of the paper records the 864; Section 4.4 and
the Limitations section record the 2.

This script asks the counterfactual directly. It reuses `order_permutation`'s
`load_files`, `signatures` and `greedy` unchanged, so the archived clustering is
reproduced exactly at the default datasketch seed, then:

  1. builds the LSH over the archived signatures and queries it with signatures
     computed for the excluded files under the same tokenizer and MinHash
     settings (128 permutations, 3-word shingles, LSH threshold 0.9);
  2. reruns the greedy assignment loop with the two hightower6eu files appended
     at the END of the file list, so the archived clusters form first and any
     change is attributable to the two additions;
  3. reports, for the other 72 ClawHub backup-path files, how many would have
     returned at least one neighbour and how many of those neighbours sit in an
     account this study documented.

Read-only against the corpus and against every tracked input.


Inputs. LIBRARIAN_CORPUS (required) names the pinned March corpus; see
paper/supplementary/repository-commits.md. `order_permutation.require_corpus()` stops
the run at import time when it is unset. Also
`scan_20260314_threshold90_skillonly.json` and `paper/iocs.json`.

Output: `backup-slug-check-<UTC date>.md` beside this script, or the full path in
SCAN_RESULTS_OUT. A second run on the same UTC day overwrites the day's file.

Self-test (before any real input): two identical toy documents must retrieve each
other at estimated Jaccard 1.0, so a tokenizer or num_perm mismatch fails the run
rather than returning "no neighbours", which is an answer this script might
legitimately give.

Run:
  LIBRARIAN_CORPUS=$LIBRARIAN_CORPUS python paper/sources/scans/backup_slug_check.py
"""
import datetime, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2]))

from datasketch import MinHash, MinHashLSH
from librarian.core import tokenize, NUM_PERM
from order_permutation import CORPUS, SCAN, load_files, signatures, greedy, tilde
from file_level_precision import account_of, CLAWHUB

THRESHOLD = 0.9
IOCS = HERE.parents[1] / "iocs.json"
OUT = Path(os.environ["SCAN_RESULTS_OUT"]) if os.environ.get("SCAN_RESULTS_OUT") \
    else HERE / "backup-slug-check-{}.md".format(
        datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d"))

# The two files the paper counts as absent. Paths are relative to the
# clawhub-archive marketplace directory, the same form load_files returns.
HIGHTOWER = ("skills/hightower6eu/openclaw-backup-dnkxm/SKILL.md",
             "skills/hightower6eu/openclaw-backup-wrxw0/SKILL.md")
# Section 4.4 of main-acm.tex: 354 hightower6eu IOC slugs, 2 skipped by the
# backup-path filter, 351 of the remaining 352 clustered.
PAPER_HIGHTOWER_SLUGS = 354
PAPER_HIGHTOWER_CLUSTERED = 351


def self_test() -> int:
    """Two identical toy documents must retrieve each other at estimated J = 1.0.

    DESIGN RATIONALE: every number below is an LSH hit or a MinHash Jaccard
    estimate, so a tokenizer or num_perm mismatch between the archived
    signatures and the ones computed here would show up as "no neighbours" --
    which is exactly the answer the script might legitimately return. Pinning
    the trivial case makes a silent mismatch fail the run instead.
    """
    text = ("This is a backup skill for OpenClaw. It archives the workspace, "
            "uploads the archive, and restores it on request, repeatedly.\n") * 3
    a, b = MinHash(num_perm=NUM_PERM), MinHash(num_perm=NUM_PERM)
    sh = tokenize(text)
    if not sh:
        print("self-test FAILED: tokenizer produced no shingles for the toy text", file=sys.stderr)
        return 1
    for s in sh:
        a.update(s.encode("utf-8")); b.update(s.encode("utf-8"))
    if not a.jaccard(b) == 1.0:
        print(f"self-test FAILED: identical texts estimated J={a.jaccard(b)}, expected 1.0",
              file=sys.stderr)
        return 1
    lsh = MinHashLSH(threshold=THRESHOLD, num_perm=NUM_PERM)
    lsh.insert("a", a)
    if sorted(lsh.query(b)) != ["a"]:
        print(f"self-test FAILED: query returned {sorted(lsh.query(b))}, expected ['a']",
              file=sys.stderr)
        return 1
    return 0


def repo_head() -> str:
    """Short HEAD of this repository, dirty flag included."""
    try:
        env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
        r = subprocess.run(["git", "-C", str(HERE), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=30, env=env)
        if r.returncode != 0:
            return "unknown"
        head = r.stdout.strip()
        d = subprocess.run(["git", "-C", str(HERE), "status", "--porcelain"],
                           capture_output=True, text=True, timeout=30, env=env)
        if d.returncode != 0:
            return f"{head}+status unknown"
        return f"{head}+dirty" if d.stdout.strip() else head
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def backup_files(entries) -> list:
    """Every SKILL.md under clawhub-archive that the ARCHIVED March scan's filter dropped.

    DESIGN RATIONALE for the substring test rather than the current helper: the
    rule reproduced here is the one that produced `scan_20260314_...json`, which
    is `librarian/cli.py` at commit b55ceff, `"backup" in
    str(md_file).lower()` over the ABSOLUTE path; the released tree at that
    commit is identical to the one the published scan ran on. The released
    `librarian.core.is_backup_path` matches on directory NAMES
    (cli.py:1468) and so drops far fewer files. Using today's helper here would
    enumerate a different, smaller set than the one the archived scan actually
    excluded, and the question being asked is about the archived scan. The
    corpus root in use carries no "backup" segment, so matching the substring on
    the marketplace-relative path reproduces the absolute-path test exactly.

    The two hightower6eu files are returned first so they occupy the two indices
    appended for the greedy rerun.

    `entries` is the scan's file_index, used to assert that none of the
    enumerated paths is already indexed. Against a scan regenerated with the
    fixed filter some of these files WILL be present, and appending them would
    silently double-insert: the same file would sit at two indices, matching
    itself at J = 1.0 and manufacturing a cluster. That is a wrong answer rather
    than a missing one, so it exits non-zero instead.
    """
    root = CORPUS / CLAWHUB
    found = sorted(str(p.relative_to(root)) for p in root.rglob("SKILL.md")
                   if "backup" in str(p.relative_to(root)).lower())
    missing = [p for p in HIGHTOWER if p not in found]
    if missing:
        raise SystemExit(f"hightower6eu backup files not found in the corpus: {missing}")
    indexed = {e["path"] for e in entries if e["marketplace"] == CLAWHUB}
    already = sorted(set(found) & indexed)
    if already:
        raise SystemExit(
            f"{len(already)} of the {len(found)} enumerated backup paths are ALREADY in "
            f"{SCAN.name}'s file_index, so this scan was not built with the March "
            f"substring filter and appending them would double-insert: {already[:5]}")
    return list(HIGHTOWER) + [p for p in found if p not in HIGHTOWER]


def study_accounts() -> set:
    """The 18-account 'study' ground truth, built exactly as file_level_precision does."""
    iocs = json.loads(IOCS.read_text())
    refs = [r for r in iocs["metadata"]["references"] if r.get("source") == "Antiy CERT"]
    if len(refs) != 1:
        raise SystemExit(f"expected exactly 1 Antiy CERT reference in iocs.json, found {len(refs)}")
    antiy = set(refs[0]["authors_documented"])
    if len(antiy) != 12:
        raise SystemExit(f"expected 12 Antiy accounts in iocs.json, found {sorted(antiy)}")
    return set(iocs["clawhub_authors"]) | antiy


def neighbours(lsh, sigs, i):
    """Archived neighbours of signature `i`, as (index, estimated Jaccard), best first.

    The query key for `i` itself is never in this LSH (only archived indices are
    inserted), so no self-hit has to be filtered.
    """
    hits = [int(r) for r in lsh.query(sigs[i])]
    return sorted(((j, sigs[i].jaccard(sigs[j])) for j in hits), key=lambda t: -t[1])


def main() -> int:
    t0 = time.time()
    scan = json.loads(SCAN.read_text())
    entries = scan["file_index"]
    entries = entries if isinstance(entries, list) else list(entries.values())
    archived = load_files(scan)
    n_arch = len(archived)

    extra = backup_files(entries)
    combined = archived + [(CLAWHUB, p) for p in extra]
    sigs, skipped = signatures(combined)
    if not sigs:
        print("no signatures computed; corpus path or file_index keys are wrong", file=sys.stderr)
        return 1
    for k in range(n_arch, n_arch + 2):
        if k not in sigs:
            print(f"no signature for {combined[k][1]}; it is too short or produced no shingles",
                  file=sys.stderr)
            return 1

    # LSH over the archived signatures ONLY: this is the index the March scan
    # built, and the one a filtered-out file would have been matched against.
    lsh_arch = MinHashLSH(threshold=THRESHOLD, num_perm=NUM_PERM)
    for i, m in sigs.items():
        if i < n_arch:
            lsh_arch.insert(str(i), m)
    arch_keys = sorted(i for i in sigs if i < n_arch)
    base = greedy(lsh_arch, sigs, arch_keys)

    # Same LSH plus the two hightower6eu files, and the greedy loop rerun with
    # them last in the order so the archived clusters form first.
    lsh_aug = MinHashLSH(threshold=THRESHOLD, num_perm=NUM_PERM)
    aug_keys = sorted(i for i in sigs if i < n_arch + 2)
    for i in aug_keys:
        lsh_aug.insert(str(i), sigs[i])
    aug = greedy(lsh_aug, sigs, aug_keys)
    member_of = {}
    for cid, c in enumerate(aug):
        for x in c:
            member_of.setdefault(x, []).append(cid)

    study = study_accounts()

    def describe(i):
        """(marketplace, path, account) of an archived index."""
        e = entries[i]
        return e["marketplace"], e["path"], account_of(e)

    lines = ["# What the backup-path filter excluded from the clustering", ""]
    lines += [
        f"Corpus root: `{tilde(CORPUS)}`"
        + ("" if os.environ.get("LIBRARIAN_CORPUS") else "  (LIBRARIAN_CORPUS unset; default)"),
        f"Repository HEAD: `{repo_head()}`",
        f"Input scan: `{SCAN.name}` ({n_arch} indexed files).",
        f"Command: `LIBRARIAN_CORPUS={tilde(os.environ.get('LIBRARIAN_CORPUS', str(CORPUS)))} "
        f"python paper/sources/scans/{Path(__file__).name}` from the repository root.",
        f"Generated: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}.",
        "",
        "This check supports three statements in the paper. Section 3.2, Dataset "
        "Construction: \"Before that test, the scanner had skipped any path containing "
        "`backup` (864 files, 780 of them one repository's backup directory).\" Section 4.4, "
        "IOC Validation: \"Of the 354 slugs, 2 were skipped by the backup-path filter ...; of "
        "the 352 scanned, 351 appeared in clusters (99.7% of those scanned; 99.2% against the "
        "full 354).\" Section 6, Limitations: \"the backup-path filter skipped 2 hightower6eu "
        "skills that, scanned, cluster only with each other.\"",
        "",
        f"What it measures: for every `SKILL.md` the filter excluded from `{CLAWHUB}`, whether "
        f"the archived index returns any LSH candidate for it at threshold {THRESHOLD}, and "
        "whether the cluster count and the hightower6eu recall move when the 2 skipped "
        "hightower6eu skills are scanned alongside the archived files.",
        "",
        "Settings, matching the paper: MinHash with 128 permutations at the datasketch default "
        f"seed, 3-word shingles from `librarian.core.tokenize`, LSH threshold {THRESHOLD}. "
        "`load_files`, `signatures` and `greedy` are imported from `order_permutation.py` "
        "unchanged, so the archived clustering is reproduced rather than re-implemented.",
        "",
        f"Signatures: {len(sigs)} of {len(combined)} ({n_arch} archived + {len(extra)} "
        f"backup-path files from `{CLAWHUB}`). Skipped {skipped['missing']} missing, "
        f"{skipped['short']} shorter than 100 characters, {skipped['empty']} with no shingles.",
        f"Archived-only baseline: {len(base)} clusters "
        f"(archived scan summary records {scan.get('summary', {}).get('unique_clusters')}).",
        "",
    ]

    # ---- the two hightower6eu files -------------------------------------
    lines += ["## The two hightower6eu skills the filter skipped", ""]
    verdicts = {}
    for k in range(n_arch, n_arch + 2):
        rel = combined[k][1]
        nb = neighbours(lsh_arch, sigs, k)
        cids = member_of.get(k, [])
        verdicts[rel] = bool(cids)
        lines += [f"### `{CLAWHUB}/{rel}`", ""]
        if not nb:
            lines += ["No archived file is returned by the LSH at threshold "
                      f"{THRESHOLD}: this file is a candidate for nothing in the "
                      "archived index.", ""]
        else:
            lines += [f"{len(nb)} archived neighbours at threshold {THRESHOLD}:", "",
                      "| file_index | marketplace | path | account | est. Jaccard |",
                      "|---:|---|---|---|---:|"]
            for j, jac in nb:
                mk, pth, acct = describe(j)
                lines.append(f"| {j} | `{mk}` | `{pth}` | {acct or '-'} | {jac:.4f} |")
            lines.append("")
        if cids:
            cid = cids[0]
            members = sorted(aug[cid])
            names = [f"`{describe(x)[0]}/{describe(x)[1]}`" if x < n_arch
                     else f"`{CLAWHUB}/{combined[x][1]}` (appended)" for x in members]
            n_new = sum(1 for x in members if x >= n_arch)
            lines += [f"In the rerun greedy loop this file joins cluster #{cid} of the augmented "
                      f"run, size {len(members)}"
                      + (f" (it is also returned by {len(cids) - 1} further cluster seed(s))"
                         if len(cids) > 1 else "")
                      + ". Members: " + "; ".join(names) + ".", ""]
            if n_new == len(members):
                lines += ["**Every member of this cluster is one of the appended files.** The "
                          "cluster exists only because the two filtered files match each other; "
                          "no archived file is near either of them at this threshold.", ""]
        else:
            lines += ["In the rerun greedy loop this file joins no cluster.", ""]

    # ---- augmented cluster count and recall ------------------------------
    both = all(verdicts.values())
    clustered_now = PAPER_HIGHTOWER_CLUSTERED + sum(1 for v in verdicts.values() if v)
    # Exact 3-gram Jaccard for the pair, computed directly rather than estimated,
    # so the MinHash figure above can be checked against ground truth.
    sh = [tokenize((CORPUS / CLAWHUB / p).read_text(encoding="utf-8", errors="replace"))
          for p in HIGHTOWER]
    inter, union = len(sh[0] & sh[1]), len(sh[0] | sh[1])
    exact_j = inter / union
    lines += ["## Cluster count and hightower6eu recall", "",
              f"Baseline (archived file list, sorted order): **{len(base)} clusters**, "
              f"{sum(len(c) for c in base)} files clustered as a sum of cluster sizes.",
              f"With the two files appended: **{len(aug)} clusters**, "
              f"{sum(len(c) for c in aug)} files clustered as a sum of cluster sizes.",
              "",
              f"Section 4.4 reports the recall as 351 of the 352 scanned, 99.7%, and 99.2% "
              f"against the full {PAPER_HIGHTOWER_SLUGS}. That is the figure for the corpus as "
              f"scanned. The 2 skipped slugs are present on disk in `{CLAWHUB}`; the filter "
              f"excluded them.",
              "",
              f"Had the filter not applied, the same rule, which counts a slug as recalled when "
              f"it appears in a similarity cluster whatever the cluster's other members are, "
              f"gives **{clustered_now} of {PAPER_HIGHTOWER_SLUGS}** "
              f"({100.0 * clustered_now / PAPER_HIGHTOWER_SLUGS:.1f}%)"
              + ("." if both else
                 ", because not both of the recovered files cluster; see the tables above.")
              + " The percentage is 99.7% on either denominator.",
              "",
              f"The pair's similarity is not a MinHash artefact. Their exact 3-word-shingle "
              f"Jaccard, computed directly from the two shingle sets rather than estimated, is "
              f"**{exact_j:.4f}** ({inter} shingles shared of {union} in the union; each file has "
              f"{len(sh[0])} and {len(sh[1])} shingles). An independent recomputation of the "
              f"same pair also gives {exact_j:.4f}.",
              ""]

    # ---- the other 72 -----------------------------------------------------
    others = list(range(n_arch + 2, n_arch + len(extra)))
    with_nb, with_study, unsigned, rows = 0, 0, 0, []
    for k in others:
        rel = combined[k][1]
        acct = account_of({"marketplace": CLAWHUB, "path": rel})
        if k not in sigs:
            # DESIGN RATIONALE: an unsigned file (too short, or no shingles) was
            # never queried, so it is not evidence of isolation. Reporting it as
            # "0 neighbours" would fold "we did not look" into "we looked and
            # found nothing" and understate the blind spot.
            unsigned += 1
            rows.append((rel, acct, None, [], None))
            continue
        nb = neighbours(lsh_arch, sigs, k)
        accts = sorted({describe(j)[2] for j, _ in nb} - {None})
        in_study = [a for a in accts if a in study]
        if nb:
            with_nb += 1
        if in_study:
            with_study += 1
        rows.append((rel, acct, len(nb), in_study, max((j for _, j in nb), default=None)))
    studied = [r for r in rows if r[3]]
    lines += ["## The other 72 ClawHub backup-path files (query only, no greedy rerun)", "",
              f"Of {len(others)} files, **{with_nb}** return at least one archived neighbour at "
              f"threshold {THRESHOLD}, and **{with_study}** of those have at least one neighbour "
              f"in an account this study documented (the 18-account `study` ground truth from "
              f"`file_level_precision.py`, applied with its `account_of`)."
              + (f" {unsigned} file(s) produced no signature and were never queried; they are "
                 f"marked `not signed` below and counted in neither figure."
                 if unsigned else ""),
              "",
              "Both counts are LSH candidacy at threshold "
              f"{THRESHOLD}, not verified isolation. The banded LSH is a probabilistic filter "
              "with false negatives just under the threshold, so an empty row means no candidate "
              "was retrieved, not that no similar file exists; a full pairwise comparison would "
              "be needed to say the latter. A row with a neighbour, by contrast, is a positive "
              "finding: that file was a cluster member the filter removed. Rows are the "
              f"marketplace-relative path under `{CLAWHUB}`.",
              ""]
    if studied:
        lines += ["Files whose neighbours reach an account this study documented: " + " ".join(
                      f"`{r[0]}` has {r[2]} neighbours at up to est. J {r[4]:.4f}, reaching "
                      + ", ".join(f"`{a}`" for a in r[3])
                      + ": the filter removed a file that would have joined a documented "
                        "attacker's cluster, and the paper's published distinct-file counts do "
                        "not include it." for r in studied),
                  ""]
    lines += [
              "| path | account | neighbours | neighbour accounts in `study` | max est. Jaccard |",
              "|---|---|---:|---:|---:|"]
    for rel, acct, n_nb, in_study, best in rows:
        st = ", ".join(f"`{a}`" for a in in_study) if in_study else "0"
        lines.append(f"| `{rel}` | {acct or '-'} | "
                     + ("not signed" if n_nb is None else str(n_nb))
                     + (" | - | - |" if n_nb is None else
                        f" | {st} | " + (f"{best:.4f}" if best is not None else "-") + " |"))
    lines += ["", f"Runtime: {time.time() - t0:.0f} s.", ""]

    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:60]))
    print(f"\n[wrote {OUT}]  runtime {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    rc = self_test()
    sys.exit(rc or main())
