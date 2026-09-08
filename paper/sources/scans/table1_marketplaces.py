#!/usr/bin/env python3
"""Recompute Table 1 (corpus repositories) from the archived 90% scan.

Supports Table 1 (Section 3.2, Dataset Construction), whose counts are the SKILL.md
files of each repository that meet the 100-character minimum after filtering.

Counts files per `marketplace` value in the scan's `file_index`, pools every
repository with fewer than 50 files into a single aggregate row, and compares the
result row by row against Table 1 as printed. It never edits the paper: a disagreement
is reported, not repaired.

Input: `scan_20260314_threshold90_skillonly.json`, beside this script. The script
needs no corpus access and no network, and nothing in it is randomized.

Output: `table1-marketplaces-20260907.md` beside this script, with a provenance header
and the comparison table.

Options: --check verifies the existing report instead of rewriting it, comparing every
line except "Repository HEAD at generation", which moves on every commit and would
otherwise fail the check for reasons unrelated to the numbers. The comparison table is
printed either way.

Self-test (before any real input): a toy file_index with counts 60, 50, 49 and 1
exercises the strict `< 50` boundary, so the 50-file repository stays a named row and
only the 49 and the 1 may be pooled.

Run from the repository root (LIBRARIAN_CORPUS is not needed):
  python paper/sources/scans/table1_marketplaces.py [--check]
"""
import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAN = HERE / "scan_20260314_threshold90_skillonly.json"
OUT = HERE / "table1-marketplaces-20260907.md"
SMALL_THRESHOLD = 50
HEAD_LINE_PREFIX = "- Repository HEAD at generation:"

# Values as printed in the paper, Table 1 (Repositories included in the corpus;
# the tex source is not part of this artifact), in the order they appear there.
# The pooled row and the total are compared too.
TEX_ROWS = [
    ("clawhub-archive", 23654),
    ("claude-code-plugins-plus", 2396),
    ("antigravity-awesome-skills", 1249),
    ("sundial-awesome-openclaw-skills", 933),
    ("claude-code-templates", 715),
    ("curated", 639),
    ("han", 429),
    ("alirezarezvani-claude-skills", 421),
    ("leoyeai-openclaw-master-skills", 361),
    ("claude-scientific-skills", 175),
    ("claude-code-workflows", 146),
    ("mag-claude-plugins", 131),
]
TEX_POOLED_REPOS = 20
TEX_POOLED_FILES = 385
TEX_TOTAL_REPOS = 32
TEX_TOTAL_FILES = 31634


def counts_by_marketplace(scan):
    """Files per marketplace value in the scan's file_index, largest first."""
    return collections.Counter(e["marketplace"] for e in scan["file_index"])


def split_rows(counts, threshold=SMALL_THRESHOLD):
    """Named rows (>= threshold files, descending) and the pooled remainder."""
    named = sorted(((n, m) for m, n in counts.items() if n >= threshold),
                   key=lambda p: (-p[0], p[1]))
    pooled = [(n, m) for m, n in counts.items() if n < threshold]
    return ([(m, n) for n, m in named], len(pooled), sum(n for n, _ in pooled))


def without_head_line(text):
    """The report minus its recorded git HEAD, which moves on every commit."""
    return "\n".join(l for l in text.splitlines()
                     if not l.startswith(HEAD_LINE_PREFIX))


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


def git_head():
    if not is_public_repo(HERE):
        return PRIVATE_HISTORY
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(HERE),
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"unavailable ({exc})"
    return (out.stdout.strip() if out.returncode == 0
            else f"unavailable (git rev-parse exited {out.returncode})")


def self_test():
    toy = {"file_index": (
        [{"marketplace": "big"}] * 60
        + [{"marketplace": "exactly-fifty"}] * 50
        + [{"marketplace": "forty-nine"}] * 49
        + [{"marketplace": "singleton"}] * 1)}
    named, pooled_repos, pooled_files = split_rows(counts_by_marketplace(toy))
    want_named = [("big", 60), ("exactly-fifty", 50)]
    if named != want_named or (pooled_repos, pooled_files) != (2, 50):
        sys.exit(f"self-test FAILED: named={named}, pooled=({pooled_repos}, "
                 f"{pooled_files}); want {want_named} and (2, 50)")
    total = sum(n for _, n in named) + pooled_files
    if total != 160:
        sys.exit(f"self-test FAILED: total {total}, want 160")
    print("self-test PASS: 60/50 stay named at the strict <50 boundary, "
          "49+1 pool into 2 repositories and 50 files, total 160")


def comparison_rows(named, pooled_repos, pooled_files, total_repos, total_files):
    """(label, computed, tex, match) triples for every printed row."""
    computed = dict(named)
    rows = [(label, computed.get(label), tex, computed.get(label) == tex)
            for label, tex in TEX_ROWS]
    rows.append((f"{pooled_repos} repositories with <50 files each",
                 pooled_files, TEX_POOLED_FILES, pooled_files == TEX_POOLED_FILES
                 and pooled_repos == TEX_POOLED_REPOS))
    rows.append((f"Total ({total_repos} repositories)", total_files,
                 TEX_TOTAL_FILES, total_files == TEX_TOTAL_FILES
                 and total_repos == TEX_TOTAL_REPOS))
    extra = [m for m, n in named if m not in dict(TEX_ROWS)]
    return rows, extra


def render(rows):
    out = ["| Row | Computed | Table 1 as printed | Match |", "|---|---:|---:|:--:|"]
    for label, got, tex_value, ok in rows:
        shown = "absent" if got is None else f"{got:,}"
        out.append(f"| {label} | {shown} | {tex_value:,} | {'yes' if ok else 'NO'} |")
    return "\n".join(out)


def build_report(scan, rows, extra, pooled, ordered_named):
    pooled_repos, pooled_files = pooled
    lines = [
        "# Table 1 (corpus repositories) recomputed from the archived 90% scan",
        "",
        "This file reports the file count of every corpus repository, recomputed from"
        " the archived scan, and compares each row against Table 1 as printed. It"
        " supports Table 1 (Section 3.2, Dataset Construction), whose counts are the"
        " `SKILL.md` files of each repository that meet the 100-character minimum"
        " after filtering.",
        "",
        "## Provenance",
        "",
        f"- Input: `paper/sources/scans/{SCAN.name}`",
        f"- Input `metadata.generated_at`: {scan['metadata']['generated_at']}",
        "- Command: `python paper/sources/scans/table1_marketplaces.py`"
        " (run from the repository root)",
        f"{HEAD_LINE_PREFIX} `{git_head()}`",
        f"- Aggregation rule: a repository is named when it holds at least"
        f" {SMALL_THRESHOLD} files; the rest pool into one row.",
        "",
        "Counts are files per `marketplace` value in the scan's `file_index`,"
        " which is the corpus after the 100-character minimum filter.",
        "",
        "## Row-by-row comparison against Table 1 as printed",
        "",
        render(rows),
        "",
    ]
    bad = [f"{lbl} computed {got}, printed {tex}"
           for lbl, got, tex, ok in rows if not ok]
    lines.append(("**Mismatches:** " + "; ".join(bad) if bad
                  else "All rows agree with the printed table") + ".")
    lines += ["", "## Pooled repositories", "",
              f"{pooled_repos} repositories hold fewer than {SMALL_THRESHOLD}"
              f" files each, {pooled_files} files in total:", ""]
    counts = counts_by_marketplace(scan)
    for market, n in sorted(((m, n) for m, n in counts.items()
                             if n < SMALL_THRESHOLD), key=lambda p: (-p[1], p[0])):
        lines.append(f"- {market}: {n}")
    if extra:
        lines += ["", "**Named by this script but absent from the printed table:** "
                  + ", ".join(extra)]
    lines += ["", f"Named repositories: {len(ordered_named)}."
              f" Total repositories: {len(counts)}.", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the existing report instead of rewriting it")
    args = ap.parse_args()
    self_test()
    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    counts = counts_by_marketplace(scan)
    named, pooled_repos, pooled_files = split_rows(counts)
    total_files = sum(counts.values())
    rows, extra = comparison_rows(named, pooled_repos, pooled_files,
                                  len(counts), total_files)
    print(render(rows))
    report = build_report(scan, rows, extra, (pooled_repos, pooled_files), named)
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if without_head_line(current) != without_head_line(report):
            print(f"{OUT.name} is out of date; the table above is the recomputed"
                  f" one", file=sys.stderr)
            return 1
        print(f"{OUT.name} is up to date "
              f"(the recorded repository HEAD is excluded from the comparison)")
        return 0
    OUT.write_text(report, encoding="utf-8")
    print(f"Wrote {OUT.name}")
    return 0 if all(r[3] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
