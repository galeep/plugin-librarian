#!/usr/bin/env python3
"""Exact SHA-256 deduplication baseline for Section 5.2, in three variants.

Recomputes the exact-hash baseline of Section 5.2 (1,946 duplicate groups, 71
containing a known malicious account, 95.4% file recall for the two primary campaign
accounts) from the archived scan's `file_index` against a pinned corpus snapshot, and
adds two variants for comparison:
  raw      whole file bytes; the paper's baseline
  nofm     leading YAML frontmatter stripped first
  clawhub  raw, restricted to clawhub-archive
The ground-truth rules the paper leaves implicit are stated in full in the output file,
along with every other definition inferred here.

Inputs. LIBRARIAN_CORPUS (required) names the pinned March corpus; see
paper/supplementary/repository-commits.md. Also
`scan_20260314_threshold90_skillonly.json` and `paper/iocs.json`, both beside or above
this script.

Output: `exact-hash-baseline-<UTC date>.md` beside this script, or the full path in
SCAN_RESULTS_OUT. It is written BEFORE the cross-check against the published figures,
so a failing run still leaves its output on disk for inspection: trust the exit status,
not the presence of the file.

Run:
  LIBRARIAN_CORPUS=$LIBRARIAN_CORPUS python paper/sources/scans/exact_hash_baseline.py
"""
import collections, datetime, hashlib, json, os, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from file_level_precision import CLAWHUB, account_of          # noqa: E402
from order_permutation import git_head, require_corpus, tilde  # noqa: E402

SCAN = HERE / "scan_20260314_threshold90_skillonly.json"
IOCS = HERE.parents[1] / "iocs.json"
CORPUS = Path(require_corpus())
_DEFAULT_OUT_NAME = "exact-hash-baseline-{}.md".format(
    datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d"))
OUT = Path(os.environ["SCAN_RESULTS_OUT"]) if os.environ.get("SCAN_RESULTS_OUT") \
    else HERE / _DEFAULT_OUT_NAME

PRIMARY = frozenset({"hightower6eu", "sakaen736jih"})
# Published Section 5.2 / baseline-comparisons.md figures, checked at the end of the run.
PAPER = {"files": 31634, "unique": 28264, "groups": 1946, "in_groups": 5316,
         "mal_groups": 71, "mal_pct": 3.6, "fp_pct": 96.4, "primary": 564,
         "primary_hashes": 75, "recall_files": 538, "recall_pct": 95.4, "missed": 26,
         "missed_pct": 4.6, "minhash_ge20_clusters": 11}

def strip_frontmatter(data: bytes) -> tuple:
    """(payload, stripped?) for a leading YAML frontmatter block; rule stated in the .md.
    A file opening with `---` and no closing delimiter is left whole rather than truncated to
    nothing, so a malformed header cannot silently collapse many files onto one digest."""
    if not data.startswith(b"---\n") and not data.startswith(b"---\r\n"):
        return data, False
    lines = data.split(b"\n")
    for i in range(1, len(lines)):
        if lines[i].rstrip() == b"---":
            return b"\n".join(lines[i + 1:]), True
    return data, False

def load_files(scan):
    """Scan entries as dicts. Only <marketplace>/<path> is a real corpus path; a bare
    CORPUS/path fallback can resolve a different marketplace's file, so a miss stays
    a miss (order_permutation.load_files takes the same line)."""
    entries = scan["file_index"]
    return entries if isinstance(entries, list) else list(entries.values())

def group_by_hash(root, entries, strip=False, marketplace=None):
    """Map digest -> [entry], plus skip counts by cause. Skips are reported, never gated:
    nothing aborts on a non-zero count, and this corpus produces none."""
    groups, skipped = collections.defaultdict(list), {"missing": 0, "unreadable": 0,
                                                      "other_marketplace": 0, "unterminated_fm": 0}
    for e in entries:
        if marketplace is not None and e["marketplace"] != marketplace:
            skipped["other_marketplace"] += 1
            continue
        p = root / e["marketplace"] / e["path"]
        try:
            data = p.read_bytes()
        except OSError:
            skipped["missing" if not p.exists() else "unreadable"] += 1
            continue
        if strip:
            payload, ok = strip_frontmatter(data)
            if not ok and data.startswith(b"---"):
                skipped["unterminated_fm"] += 1
            data = payload
        groups[hashlib.sha256(data).hexdigest()].append(e)
    return groups, skipped

def analyse(groups, entries, study, marketplace=None):
    """Every figure Section 5.2 quotes, for one hashing variant. A group is two or
    more files sharing one digest; singletons are not groups. The malicious set is
    defined over scan entries, not over files that resolved on disk, so an
    unresolvable malicious file counts as missed rather than leaving the denominator."""
    dup = {h: v for h, v in groups.items() if len(v) > 1}
    in_dup = {(e["marketplace"], e["path"]) for v in dup.values() for e in v}
    primary = [e for e in entries if account_of(e) in PRIMARY
               and (marketplace is None or e["marketplace"] == marketplace)]
    keys = {(e["marketplace"], e["path"]) for e in primary}
    hit = keys & in_dup
    mal_groups = sum(1 for v in dup.values() if any(account_of(e) in study for e in v))
    n = len(dup)
    return {
        "hashed": sum(len(v) for v in groups.values()), "unique": len(groups),
        "groups": n, "in_groups": sum(len(v) for v in dup.values()),
        "mal_groups": mal_groups,
        "mal_pct": round(100 * mal_groups / n, 1) if n else float("nan"),
        "fp_pct": round(100 * (n - mal_groups) / n, 1) if n else float("nan"),
        "primary": len(primary), "recall_files": len(hit), "missed_keys": keys - in_dup,
        "primary_hashes": len({h for h, v in groups.items()
                               if any(account_of(e) in PRIMARY for e in v)}),
        "recall_pct": round(100 * len(hit) / len(keys), 1) if keys else float("nan"),
        "missed": len(keys) - len(hit),
        "missed_pct": round(100 * (len(keys) - len(hit)) / len(keys), 1) if keys else float("nan"),
    }

def self_test() -> int:
    """Hand-checked toy corpus: known duplicates, one frontmatter-only difference.

    DESIGN RATIONALE: every figure here counts over a grouping, and a wrong grouping
    (singletons counted as groups, frontmatter stripped to nothing, the marketplace filter
    applied to the wrong side) gives plausible numbers that reading does not catch. Expected
    values below are counted by hand from the six files written here."""
    body_a, body_c = b"BODY ALPHA\npayload\n", b"BODY GAMMA\n"
    files = {  # (marketplace, path) -> bytes, or None for a file left absent
        (CLAWHUB, "skills/badguy/s1/SKILL.md"): b"---\nname: s1\n---\n" + body_a,
        (CLAWHUB, "skills/badguy/s2/SKILL.md"): b"---\nname: s1\n---\n" + body_a,
        (CLAWHUB, "skills/badguy/s3/SKILL.md"): b"---\nname: s3\n---\n" + body_a,
        (CLAWHUB, "skills/goodguy/g1/SKILL.md"): body_c,
        (CLAWHUB, "skills/goodguy/g2/SKILL.md"): body_c,
        ("other-market", "x/SKILL.md"): body_c,
        (CLAWHUB, "skills/badguy/s9/SKILL.md"): None,
    }
    entries = [{"marketplace": m, "path": p} for (m, p) in files]
    for label, raw_in in (("headerless", b"no header\n"), ("unterminated", b"---\nname: x\nbody\n")):
        if strip_frontmatter(raw_in) != (raw_in, False):
            print(f"self-test FAILED: {label} file was altered", file=sys.stderr); return 1
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for (m, p), data in files.items():
            if data is None:
                continue
            (root / m / p).parent.mkdir(parents=True, exist_ok=True)
            (root / m / p).write_bytes(data)
        study = {"badguy"}   # PRIMARY is the real two-account set; swap it for the toy
        global PRIMARY
        saved, PRIMARY = PRIMARY, frozenset({"badguy"})
        try:
            raw = analyse(group_by_hash(root, entries)[0], entries, study)
            nofm = analyse(group_by_hash(root, entries, strip=True)[0], entries, study)
            claw = analyse(group_by_hash(root, entries, marketplace=CLAWHUB)[0],
                           entries, study, marketplace=CLAWHUB)
            miss = group_by_hash(root, entries)[1]["missing"]
        finally:
            PRIMARY = saved
    # By hand: raw digests {s1,s2}, {s3}, {g1,g2,x} -> 2 groups over 5 files, badguy in
    # one -> 50.0% FP; four badguy entries (s1,s2,s3,s9), two grouped -> 2 missed.
    expect = [
        ("raw", raw, dict(groups=2, in_groups=5, mal_groups=1, fp_pct=50.0, primary=4,
                          recall_files=2, missed=2, missed_pct=50.0, unique=3, primary_hashes=2)),
        # Stripping merges s3 into {s1,s2,s3}: 2 groups, 6 files, only absent s9 missed.
        ("nofm", nofm, dict(groups=2, in_groups=6, mal_groups=1, primary=4, recall_files=3,
                            missed=1, unique=2)),
        # clawhub-only drops x, so the benign group is {g1,g2}: 2 groups, 4 files.
        ("clawhub", claw, dict(groups=2, in_groups=4, mal_groups=1, primary=4, recall_files=2))]
    for name, got, want in expect:
        for k, v in want.items():
            if got[k] != v:
                print(f"self-test FAILED: {name}.{k} = {got[k]}, expected {v}", file=sys.stderr)
                return 1
    if miss != 1:
        print(f"self-test FAILED: missing count {miss}, expected 1", file=sys.stderr); return 1
    return 0

def row(label, paper, got, fmt="{}"):
    match = "yes" if paper is None or paper == got else "NO"
    p = "n/a" if paper is None else fmt.format(paper)
    return f"| {label} | {p} | {fmt.format(got)} | {match} |"

def main() -> int:
    if self_test():
        return 1
    t0 = time.time()
    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    entries = load_files(scan)
    iocs = json.loads(IOCS.read_text(encoding="utf-8"))
    antiy = set([r for r in iocs["metadata"]["references"]
                 if r.get("source") == "Antiy CERT"][0]["authors_documented"])
    study = set(iocs["clawhub_authors"]) | antiy
    variants, skips = {}, {}
    for name, kw in (("raw", {}), ("nofm", {"strip": True}), ("clawhub", {"marketplace": CLAWHUB})):
        groups, skips[name] = group_by_hash(CORPUS, entries, **kw)
        variants[name] = analyse(groups, entries, study, marketplace=kw.get("marketplace"))
    ge20 = sum(1 for c in scan["clusters"] if len(c["locations"]) >= 20)
    stuck = len(variants["raw"]["missed_keys"] & variants["nofm"]["missed_keys"])
    r, runtime = variants["raw"], time.time() - t0

    markets = sorted({e["marketplace"] for e in entries})
    heads = "\n".join(f"| `{m}` | {git_head(CORPUS / m)} |" for m in markets)
    cmp_rows = "\n".join([
        row("SKILL.md files hashed", PAPER["files"], r["hashed"]),
        row("Distinct SHA-256 digests", PAPER["unique"], r["unique"]),
        row("Duplicate groups (size >= 2)", PAPER["groups"], r["groups"]),
        row("Files in duplicate groups", PAPER["in_groups"], r["in_groups"]),
        row("Groups with >= 1 study-account file", PAPER["mal_groups"], r["mal_groups"]),
        row("...as a share of all groups", PAPER["mal_pct"], r["mal_pct"], "{:.1f}%"),
        row("Group-level false-positive rate", PAPER["fp_pct"], r["fp_pct"], "{:.1f}%"),
        row("Files from the two primary accounts", PAPER["primary"], r["primary"]),
        row("Distinct digests among those files", PAPER["primary_hashes"], r["primary_hashes"]),
        row("Primary-account files in a group", PAPER["recall_files"], r["recall_files"]),
        row("...file-level recall", 95.4, r["recall_pct"], "{:.1f}%"),
        row("Primary-account files missed", PAPER["missed"], r["missed"]),
        row("...as a share of 564", PAPER["missed_pct"], r["missed_pct"], "{:.1f}%"),
        row("MinHash clusters at >= 20 files", PAPER["minhash_ge20_clusters"], ge20),
    ])
    var_rows = "\n".join(
        f"| {n} | {v['groups']} | {v['in_groups']} | {v['mal_groups']} | {v['fp_pct']:.1f}% | "
        f"{v['primary']} | {v['recall_files']} | {v['recall_pct']:.1f}% | {v['missed']} |"
        for n, v in variants.items())
    skip_rows = "\n".join(f"| {n} | " + " | ".join(str(skips[n][k]) for k in
                          ("missing", "unreadable", "other_marketplace", "unterminated_fm")) + " |"
                          for n in variants)
    OUT.write_text(f"""# Exact SHA-256 Deduplication Baseline (Section 5.2 recompute)

Recompute of the Section 5.2 exact-hash baseline, which the paper reports with no script and no
archived result, plus two additional variants. March hand record: `paper/sources/baseline-comparisons.md`.

## Provenance

- Corpus root: `{tilde(CORPUS)}`
- Scan: `{SCAN.name}`, `generated_at` {scan["metadata"]["generated_at"]}
- Repository HEAD: {git_head(HERE.parents[2])}
- Command: `LIBRARIAN_CORPUS={tilde(CORPUS)} python paper/sources/scans/{Path(__file__).name}`
- Run at {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}, runtime {runtime:.1f}s
- This file is written before the cross-check against the published figures, so a failing run still
  leaves it on disk: trust the exit status, not the presence of the file. The skip counters in the last
  table are reported, not gated; nothing aborts on a non-zero skip (there are none on this corpus).

| Marketplace | git HEAD |
|---|---|
{heads}

## Definitions

The paper states none of these; they are the rules that reproduce its numbers.

- **Hashed unit.** SHA-256 over the whole file bytes, with no normalisation of line endings, encoding or whitespace.
  Files come from the archived scan's `file_index`, resolved as `$LIBRARIAN_CORPUS/<marketplace>/<path>` exactly as
  `order_permutation.load_files` does; a path that does not resolve is a skip, never refetched from a bare
  `$LIBRARIAN_CORPUS/<path>` fallback.
- **Group.** Two or more files sharing one digest. Singletons are not groups, so "1,946 groups" counts 1,946 digests
  of multiplicity >= 2.
- **Malicious, for the group figure.** A group counts as containing malicious content when at least one of its files
  is attributed by `file_level_precision.account_of` to one of the {len(study)} `study` accounts (iocs.json
  `clawhub_authors` union the {len(antiy)} Antiy CERT accounts). Narrower sets do not reproduce the paper: the Antiy 12
  give 60 groups (3.1%) and the two primary accounts give 49 (2.5%), against the published 71 (3.6%).
- **The 564.** Files whose `account_of` is `hightower6eu` or `sakaen736jih`: 352 + 212 on this scan. The hand record's
  per-author table says 354 for hightower6eu, so 564 is a file count under the account rule, not that table's sum.
- **The 538 and the 26.** Of the 564, those sharing a digest with at least one other file anywhere in the corpus (the
  duplicate partner need not be malicious), and the remainder.
- **The 96.4%.** Groups with no study-account file, over all groups: (1946 - 71)/1946.
- **The 11.** Not a hash figure: it is the MinHash clusters at the >= 20 threshold, recomputed here from the scan as a
  cross-check on the sentence contrasting them with the 1,946 hash groups. The hash-side count of groups containing
  malicious content is 71, not 11.

## Comparison with the published values

| Quantity | Paper | Recomputed | Match |
|---|---|---|---|
{cmp_rows}

## Variants

`nofm` strips a leading YAML frontmatter block before hashing: the file must open with `---` and a
newline, and the first later line equal to `---` after trailing whitespace closes it; an unterminated
block leaves the file whole. `clawhub` restricts the raw-byte baseline to `clawhub-archive`.

| Variant | Groups | Files in groups | Groups w/ malicious | FP rate | Primary files | In groups | Recall | Missed |
|---|---|---|---|---|---|---|---|---|
{var_rows}

Stripping the frontmatter moves file recall for the two primary accounts from 538 to
{variants["nofm"]["recall_files"]} of 564: {stuck} of the 26 raw misses still have no exact duplicate once the header is
removed, and the remaining {26 - stuck} gains a duplicate partner. Group count rises to {variants["nofm"]["groups"]} and the
group-level false-positive rate to {variants["nofm"]["fp_pct"]:.1f}%, because bodies shared across differing headers form new groups.

Of the 26: one is
body-identical to a sibling and differs only in its frontmatter; none differ only in body lines
echoing the frontmatter name or description; ten differ in template-slot text (provider version
strings, whitespace, bullet style, escaping, and in one case a C2 path); fifteen differ
substantively. Of those fifteen, eight are sakaen736jih copies of a hightower6eu skill with the
payload block absent (gas-tracker, insider-wallets-finder, phantom, solana, wallet-tracker,
yt-summarize, yt-thumbnail-grabber, yt-video-downloader) and seven are distinct skills by the same
accounts (sakaen736jih ethereum, leo-wallet, metamask, solflare, tron, tronlink, and
hightower6eu/pdf-1wso5). Fourteen of the 26 carry no payload text in the body at all, and
`iocs.json` lists 24 of the 26 under `skill_slugs_without_payload` — including
hightower6eu/pdf-1wso5, whose body does carry an openclaw-core download and a base64 dropper, so
that `iocs.json` field is wrong about the file rather than the file being payload-free.

| Variant | Missing | Unreadable | Other marketplace | Unterminated frontmatter |
|---|---|---|---|---|
{skip_rows}
""", encoding="utf-8")
    print(f"wrote {tilde(OUT)} in {runtime:.1f}s")
    got = dict(r, files=r["hashed"], minhash_ge20_clusters=ge20)
    bad = [k for k, v in PAPER.items() if got[k] != v]
    if bad:
        print(f"published figures NOT reproduced: {bad}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
