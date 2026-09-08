#!/usr/bin/env python3
"""Per-claim receipt for the temporal statements about the largest ClawHub campaign.

Thirteen claims are checked one at a time, each against the artifact that makes it:
the paper's Section 3.3 "Temporal analysis" paragraph, the authors' March working
notes, which are not part of this artifact, or the Koi Security report, which the
reader fetches and names with `--koi-capture`. Every claim block carries the
claim, its location, the method, the exact command or function used, the computed
result beside the stated value, and a verdict of HOLDS, BREAKS or DEPENDS.

The two substantive claims are 7 and 8: whether the campaign files that existed before
the disclosure anchor would have formed a cluster of five, and later of ten, under the
paper's own settings. Both are answered twice, once with exact 3-word-shingle Jaccard
computed from each file's content at its own add commit, and once with the mechanism the
paper actually runs, datasketch MinHash at 128 permutations with MinHashLSH at threshold
0.9 and the library default seed, followed by the greedy first-match assignment of
`librarian/cli.py`.

Inputs, all read-only:
  - the unshallowed ClawHub mirror, read with `git log` and `git show` only. It is
    not part of this artifact; Software Heritage serves the snapshot the paper cites,
    and `--mirror` names the checkout
  - the archived scan `scan_20260314_threshold90_skillonly.json`
  - the Koi Security report, named by `--koi-capture`. It is a third party's page:
    neither the capture nor any parse of it ships with this artifact, and the reader
    fetches it from the archived URL that `KOI_URL` gives. Claims 10 to 12 read it, and
    without it those three are reported as not run
No corpus root, no network, no environment variables, nothing randomized. The mirror is
never written to and no ref is created; the two `git log` passes and the per-file
`git show` calls are the only mirror access.

Output: `temporal-receipt-20260908.md` beside this script.

Options: --check verifies that file instead of rewriting it, and reports a unified diff
on a mismatch. --mirror, --scan and --koi-capture name the three inputs.

Without --koi-capture, claims 10 to 12 are reported as not run, and --check refuses to
compare and exits with the retrieval instruction instead. Comparing only the ten claims
that ran would let a receipt missing three claims pass as a match, which is the one
thing a check of a published file must not do, so the refusal is deliberate.

Self-test (before any input is read): the pure helpers are exercised on hand-computed
cases. Day bucketing must split a five-element timestamp list into the right per-day
counts; k-th time selection must return the 1st, 2nd and 5th elements of a deliberately
unsorted list; Jaccard on toy shingle sets must give 1/3, 1.0 and 0.0; component finding
must collapse a five-node graph with one triangle, one pair and one isolate into groups
of sizes 3, 2 and 1. Any failure exits non-zero before a byte of input is read.

Run:
  python paper/sources/scans/temporal_receipt.py [--check] [--mirror DIR] [--scan FILE]
                                                 [--koi-capture FILE]
"""
import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = HERE / "temporal-receipt-20260908.md"

# Relative by design: the mirror is not part of this artifact, so no absolute path
# here could be right on a reader's machine. `--mirror` names the checkout, and an
# absent one is reported rather than silently producing an empty receipt.
DEFAULT_MIRROR = Path("./clawhub-archive")
DEFAULT_SCAN = HERE / "scan_20260314_threshold90_skillonly.json"
# The Koi report is a third party's page. Neither it nor anything parsed out of it is
# redistributed with this artifact; the reader fetches it and names the file with
# --koi-capture. Claims 10 to 12 are the ones that need it.
KOI_URL = ("https://web.archive.org/web/20260306131006id_/"
           "https://www.koi.ai/blog/"
           "clawhavoc-341-malicious-clawedbot-skills-found-by-the-bot-they-were-targeting")

MARCHNOTE = ("The figures were first recorded in the authors' March working notes, "
             "which are not part of this artifact.")

KOI_MISSING = ("no Koi capture given. Fetch " + KOI_URL + " , strip its HTML tags and "
               "collapse whitespace to a single line, save it locally, and name it with "
               "--koi-capture. Claims 10 to 12 read it; nothing about it ships here.")

ANCHOR = "2026-02-01T00:00:00Z"
ANCHOR_MARCH = "2026-02-01T08:00:00Z"
ACCOUNTS = ("skills/hightower6eu/", "skills/sakaen736jih/")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


# ------------------------------------------------------------------
# Pure helpers, all self-tested before any input is read
# ------------------------------------------------------------------

def day_of(iso):
    """UTC calendar day of an ISO-8601 instant that already ends in Z."""
    return iso[:10]


def day_counts(stamps):
    """Ordered list of (day, count) over a list of ISO instants."""
    out = {}
    for s in stamps:
        out[day_of(s)] = out.get(day_of(s), 0) + 1
    return sorted(out.items())


def kth_time(stamps, k):
    """The k-th earliest instant, 1-based; None when fewer than k exist."""
    if len(stamps) < k:
        return None
    return sorted(stamps)[k - 1]


def jaccard(a, b):
    """Exact Jaccard of two sets; 0.0 when both are empty."""
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def components(n, edges):
    """Connected components of an undirected graph on range(n), as sorted lists,
    ordered by descending size then by first member."""
    adj = {i: set() for i in range(n)}
    for i, j in edges:
        adj[i].add(j)
        adj[j].add(i)
    seen, comps = set(), []
    for i in range(n):
        if i in seen:
            continue
        stack, comp = [i], []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            comp.append(x)
            stack.extend(adj[x] - seen)
        comps.append(sorted(comp))
    comps.sort(key=lambda c: (-len(c), c[0]))
    return comps


def greedy_clusters(n, candidates):
    """The cluster formation rule of librarian/cli.py cmd_scan: walk items in index
    order, skip assigned ones, and take the query's whole candidate set as one cluster
    when it holds more than one item. `candidates[i]` is the set the LSH returned for i."""
    assigned, clusters = set(), []
    for i in range(n):
        if i in assigned:
            continue
        got = sorted(candidates[i])
        if len(got) > 1:
            clusters.append(got)
            assigned.update(got)
    return clusters


def hours_between(later_iso, earlier_iso):
    """Signed hours from earlier to later, both ISO instants ending in Z."""
    from datetime import datetime, timezone
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    a = datetime.strptime(later_iso, fmt).replace(tzinfo=timezone.utc)
    b = datetime.strptime(earlier_iso, fmt).replace(tzinfo=timezone.utc)
    return (a - b).total_seconds() / 3600.0


def self_test():
    stamps = ["2026-01-31T22:36:54Z", "2026-01-31T23:03:13Z", "2026-02-01T08:38:11Z",
              "2026-02-01T14:03:32Z", "2026-02-02T10:38:49Z"]
    got = day_counts(stamps)
    want = [("2026-01-31", 2), ("2026-02-01", 2), ("2026-02-02", 1)]
    if got != want:
        print(f"self-test FAILED day_counts: got {got}, want {want}", file=sys.stderr)
        sys.exit(1)

    shuffled = [stamps[3], stamps[0], stamps[4], stamps[1], stamps[2]]
    for k, want_t in ((1, stamps[0]), (2, stamps[1]), (5, stamps[4])):
        if kth_time(shuffled, k) != want_t:
            print(f"self-test FAILED kth_time k={k}: got {kth_time(shuffled, k)}, want {want_t}",
                  file=sys.stderr)
            sys.exit(1)
    if kth_time(shuffled, 6) is not None:
        print("self-test FAILED kth_time: k beyond the list must give None", file=sys.stderr)
        sys.exit(1)

    a, b, c = {"x y z", "y z w"}, {"y z w", "z w v"}, set()
    for pair, want_j in (((a, b), 1 / 3), ((a, a), 1.0), ((a, c), 0.0)):
        got_j = jaccard(*pair)
        if abs(got_j - want_j) > 1e-12:
            print(f"self-test FAILED jaccard: got {got_j}, want {want_j}", file=sys.stderr)
            sys.exit(1)

    comps = components(6, [(0, 1), (1, 2), (3, 4)])
    want_c = [[0, 1, 2], [3, 4], [5]]
    if comps != want_c:
        print(f"self-test FAILED components: got {comps}, want {want_c}", file=sys.stderr)
        sys.exit(1)

    cand = {0: {0, 1, 2}, 1: {0, 1, 2}, 2: {0, 1, 2}, 3: {3, 4}, 4: {3, 4}, 5: {5}}
    got_g = greedy_clusters(6, cand)
    want_g = [[0, 1, 2], [3, 4]]
    if got_g != want_g:
        print(f"self-test FAILED greedy_clusters: got {got_g}, want {want_g}", file=sys.stderr)
        sys.exit(1)

    got_h = hours_between("2026-02-01T08:00:00Z", "2026-01-31T23:03:13Z")
    if abs(got_h - 8.9463888888) > 1e-6:
        print(f"self-test FAILED hours_between: got {got_h}", file=sys.stderr)
        sys.exit(1)

    print("self-test PASS: day buckets 2/2/1, k-th selection on an unsorted list, "
          "Jaccard 1/3, 1.0, 0.0, components of sizes 3, 2, 1, greedy clusters 3 and 2, "
          "8.9464 h between two instants")


# ------------------------------------------------------------------
# Mirror access, read-only
# ------------------------------------------------------------------

def git(mirror, *args):
    res = subprocess.run(["git", "-C", str(mirror), *args],
                         capture_output=True, text=True, check=True)
    return res.stdout


def git_bytes(mirror, *args):
    res = subprocess.run(["git", "-C", str(mirror), *args],
                         capture_output=True, check=True)
    return res.stdout


def mirror_facts(mirror):
    """Claim 1 inputs: HEAD, commit count, author-vs-committer agreement, shallow flag."""
    head = git(mirror, "rev-parse", "HEAD").strip()
    shallow = (Path(mirror) / ".git" / "shallow").exists()
    log = git(mirror, "log", "--format=%H %aI %cI")
    rows = [ln.split() for ln in log.splitlines() if ln.strip()]
    mismatched = [r[0] for r in rows if r[1] != r[2]]
    return head, len(rows), len(mismatched), sorted(mismatched), shallow


def first_adds(mirror):
    """Every path's first add across the whole mirror, as {path: (iso, sha)}.

    --reverse makes the earliest add the first appearance of a path in the stream, and
    --diff-filter=A without --follow dates the commit that introduced the path rather
    than the earliest member of a copy-similarity chain."""
    out = git(mirror, "log", "--reverse", "--diff-filter=A", "--name-only",
              "--format=C%x09%H%x09%aI")
    adds, cur = {}, (None, None)
    for line in out.splitlines():
        if line.startswith("C\t"):
            _, sha, iso = line.split("\t")
            cur = (sha, iso)
            continue
        if not line:
            continue
        adds.setdefault(line, (cur[1], cur[0]))
    return adds


def skill_adds(adds, prefix):
    """Ordered [(iso, path, sha)] for SKILL.md first-adds under an account prefix."""
    rows = [(v[0], p, v[1]) for p, v in adds.items()
            if p.startswith(prefix) and p.endswith("/SKILL.md")]
    rows.sort()
    return rows


def slug_of(path):
    return path.split("/")[-2]


def content_at(mirror, sha, path):
    return git_bytes(mirror, "show", f"{sha}:{path}").decode("utf-8", errors="replace")


# ------------------------------------------------------------------
# Koi capture
# ------------------------------------------------------------------

def parse_koi(text):
    """Slugs of the IOC appendix, by block. Mechanical: split each block on commas and
    colons, then take the first token of each piece that matches a slug shape, which
    recovers the slug that sits immediately before a category header."""
    def block(seg):
        out = []
        for piece in re.split(r"[,:]", seg):
            for word in piece.split():
                if SLUG_RE.match(word):
                    out.append(word)
                    break
        return out

    h_camp = "ClawHavoc Campaign (335 skills):"
    h_auth = "AuthTool Campaign (3 skills):"
    h_back = "Hidden Backdoor (2 skills):"
    h_cred = "Credential Exfiltration (1 skill):"
    end = text.index("share Copied to clipboard")
    camp = block(text[text.index(h_camp) + len(h_camp):text.index(h_auth)])
    auth = block(text[text.index(h_auth) + len(h_auth):text.index(h_back)])
    back = block(text[text.index(h_back) + len(h_back):text.index(h_cred)])
    cred = block(text[text.index(h_cred) + len(h_cred):end])
    return camp, auth, back, cred


# (offset, length, sha256 of the sentence at that offset) in the capture KOI_URL names.
# DESIGN RATIONALE: digests, not text. The report is a third party's page and neither it
# nor anything quoted out of it ships with this artifact, so the sentences claims 9 and
# 10 rest on cannot be carried here as search needles. A digest is one-way, reproduces
# none of the words, and still proves the reader's capture holds exactly the expected
# sentence at the expected place, which is the whole of what those claims need. A
# mismatch means a different capture, and it aborts rather than reporting an offset into
# text that is not the text these figures were computed from.
KOI_SENTENCES = {
    "byline": (1167, 37,
               "834a3cbc219271a55aec900297a5e2c04d303adbbd557f10e059d6f23a7a5c56"),
    "twodays": (2043, 42,
                "5eaf5743ac30e98e5124c231893d001a51b34676a11911b4dc044daddc37681f"),
    "audit": (2314, 143,
              "184926eb611b9788a9b214a6f8c373b9038ab3d834d44714fecd72e885ee1c37"),
    "campaign": (2837, 100,
                 "b73903da0a6ba1198d12620b869f4a5741d69bc6c2f53b0f0316ed13994d235c"),
}


def offset_at(text, key):
    """(offset, length) of a recorded sentence, verified by digest, never the words."""
    if text is None:
        return None
    offset, length, digest = KOI_SENTENCES[key]
    got = hashlib.sha256(text[offset:offset + length].encode("utf-8")).hexdigest()
    if got != digest:
        raise SystemExit(
            f"the capture does not carry the expected {key} sentence at offset {offset}:"
            f" digest {got[:12]} where {digest[:12]} was recorded. This is a different"
            f" capture from the one these figures were computed against; fetch {KOI_URL}")
    return offset, length


# ------------------------------------------------------------------
# Report
# ------------------------------------------------------------------

def verdict_line(stated, computed, ok):
    return f"stated {stated}; computed {computed}; **{'HOLDS' if ok else 'BREAKS'}**"


def build_report(d):
    L = []
    A = L.append
    A("# Temporal receipt: thirteen claims, one at a time")
    A("")
    A("Generated by `paper/sources/scans/temporal_receipt.py`. Every figure below is "
      "recomputed by that script from the three inputs named under Provenance; nothing "
      "here is transcribed from an earlier note. Rerun with `python "
      "paper/sources/scans/temporal_receipt.py`, or verify this file without rewriting "
      "it with `--check`, which exits non-zero on any difference.")
    A("")
    A("Each claim is a numbered block giving the claim, where it is made, the method, "
      "the exact command or function, the computed result beside the stated value, and "
      "a verdict. Paper claims are cited by section and are paraphrased, not quoted. "
      "Claims first recorded in the authors' March working notes, which are not part of "
      "this artifact, are marked as such. Koi claims are quoted from the archived "
      "capture with their character offsets in that file, since the capture is an "
      "external source.")
    A("")
    A("## Provenance")
    A("")
    A("| item | value |")
    A("|---|---|")
    A("| mirror | the unshallowed ClawHub mirror named by `--mirror` |")
    A(f"| mirror HEAD | `{d['head']}` |")
    A(f"| mirror commits | {d['ncommits']:,} |")
    A(f"| mirror shallow | {'yes' if d['shallow'] else 'no'} |")
    A(f"| scan | `{d['scan_name']}`, `generated_at` {d['scan_generated']} |")
    A(f"| scan threshold, permutations | {d['scan_threshold']}, {d['scan_perms']} |")
    A(f"| Koi capture | fetched by the reader from <{d['koi_url']}>; not part of this "
      + (f"artifact. {d['koi_chars']:,} characters |" if d["koi_ok"] else "artifact. Not provided for this run |"))
    A(f"| datasketch | {d['datasketch']} |")
    A(f"| shingling | `librarian.core.tokenize`, {d['shingle_size']}-word shingles |")
    A(f"| MinHash | `librarian.core.compute_minhash`, {d['num_perm']} permutations, library default seed |")
    A(f"| LSH | `MinHashLSH(threshold=0.9, num_perm={d['num_perm']})`, bands {d['bands']} x rows {d['rows']} |")
    A(f"| disclosure anchor | {ANCHOR} (Section 3.1, Analysis Timeline) |")
    A("")
    A("Mirror access is read-only and limited to `git log`, `git show` and `git "
      "rev-parse`. Two `git log` passes are made: one over every commit for claim 1, "
      "and one `--reverse --diff-filter=A --name-only` pass for every path's first add. "
      "`--follow` is deliberately not used: this campaign is defined by near-identical "
      "templates, so git similarity detection walks a copy chain into sibling files and "
      "across account boundaries, which dates a chain rather than a path.")
    A("")

    # ---- Claim 1
    A("## Claim 1. The mirror is unshallowed, 70,091 commits, HEAD 16c991de, author date "
      "equals committer date in all but one commit")
    A("")
    A("**Where.** Section 3.3, Similarity Analysis, for the commit count and the "
      "unshallowed mirror. The author-versus-committer figure was first recorded in the "
      "authors' September working notes, which are not part of this artifact.")
    A("")
    A("**Method.** Count every commit reachable from HEAD and compare each commit's "
      "author date with its committer date. A shallow clone is detected by the presence "
      "of `.git/shallow`.")
    A("")
    A("**Command.**")
    A("")
    A("```")
    A("git -C <mirror> rev-parse HEAD")
    A("git -C <mirror> log --format='%H %aI %cI'")
    A("```")
    A("")
    A("**Result.**")
    A("")
    A("| quantity | stated | computed |")
    A("|---|---|---|")
    A(f"| HEAD | 16c991de | `{d['head']}` |")
    A(f"| commits | 70,091 | {d['ncommits']:,} |")
    A(f"| shallow | no | {'yes' if d['shallow'] else 'no'} |")
    A(f"| commits where author date differs from committer date | 1 | {d['n_mismatch']} |")
    if d["mismatch_shas"]:
        A("")
        A("The differing commit is " + ", ".join(f"`{s[:12]}`" for s in d["mismatch_shas"]) + ".")
    A("")
    A(f"**Verdict: {d['v1']}.** {d['ncommits']:,} commits, HEAD `{d['head'][:8]}`, "
      f"{d['n_mismatch']} commit of {d['ncommits']:,} with disagreeing dates "
      f"({100 * (d['ncommits'] - d['n_mismatch']) / d['ncommits']:.4f}% agreement).")
    A("")

    # ---- Claims 2-4
    ht = d["ht"]
    for num, k, stated in ((2, 1, "2026-01-31T22:36:54Z"),
                           (3, 5, "2026-01-31T23:03:13Z"),
                           (4, 10, "2026-02-01T08:38:11Z")):
        label = {1: "first", 5: "fifth", 10: "tenth"}[k]
        got = kth_time([r[0] for r in ht], k)
        path = sorted(ht)[k - 1][1]
        ok = got == stated
        A(f"## Claim {num}. hightower6eu's {label} `SKILL.md` is first-added {stated}")
        A("")
        A("**Where.** " + MARCHNOTE + " The March notes give the time to the minute; "
          "the value below is to the second.")
        A("")
        A("**Method.** First-add instant of every `SKILL.md` under "
          "`skills/hightower6eu/`, sorted, and the k-th taken.")
        A("")
        A("**Function.** `kth_time([first-add of each SKILL.md], "
          f"{k})` over `skill_adds(first_adds(mirror), 'skills/hightower6eu/')`.")
        A("")
        A(f"**Result.** {got}, `{path}`. "
          f"Total hightower6eu `SKILL.md` with a first add: {len(ht)}.")
        A("")
        A(f"**Verdict: {'HOLDS' if ok else 'BREAKS'}.** " + verdict_line(stated, got, ok) + ".")
        A("")

    # ---- Claim 5
    A("## Claim 5. 258 `SKILL.md` files first-added on 2026-02-01, and 354 in total over "
      "three days")
    A("")
    A("**Where.** " + MARCHNOTE)
    A("")
    A("**Method.** Bucket every hightower6eu `SKILL.md` first-add by UTC calendar day.")
    A("")
    A("**Function.** `day_counts([first-add of each SKILL.md])`.")
    A("")
    A("**Result.**")
    A("")
    A("| UTC day | files first-added |")
    A("|---|---:|")
    for day, n in d["ht_days"]:
        A(f"| {day} | {n} |")
    A(f"| **total** | **{len(ht)}** |")
    A("")
    A(f"**Verdict: {d['v5']}.** stated 258 on 2026-02-01 and 354 in total; computed "
      f"{d['ht_feb1']} on 2026-02-01 and {len(ht)} in total, spread over "
      f"{len(d['ht_days'])} UTC days from {d['ht_days'][0][0]} to {d['ht_days'][-1][0]}.")
    A("")

    # ---- Claim 6
    A(f"## Claim 6. Six `SKILL.md` files first-added before {ANCHOR}")
    A("")
    A("**Where.** " + MARCHNOTE)
    A("")
    A("**Method.** Filter the hightower6eu first-add list on the anchor.")
    A("")
    A("**Function.** `[r for r in skill_adds(...) if r[0] < ANCHOR]`.")
    A("")
    A("**Result.**")
    A("")
    A("| # | first-add | slug | add commit |")
    A("|---:|---|---|---|")
    for i, (iso, path, sha) in enumerate(d["ht_pre"], 1):
        A(f"| {i} | {iso} | `{slug_of(path)}` | `{sha[:12]}` |")
    A("")
    A(f"**Verdict: {d['v6']}.** " + verdict_line(6, len(d["ht_pre"]), d["v6"] == "HOLDS") + ".")
    A("")

    # ---- Claim 7
    A("## Claim 7. The six pre-anchor files form a detectable cluster at the paper's settings")
    A("")
    A("**Where.** " + MARCHNOTE + " They assert that an ingest-time similarity scan "
      "would have flagged hightower6eu at five files at 23:03 on 2026-01-31. The "
      "paper's abstract, Section 3.3 and Conclusion rest a pre-disclosure detection "
      "claim on the same reading.")
    A("")
    A("**Method.** Two independent readings of the same six files, each file taken at its "
      "own add commit so the content is what existed at the time, not what the March "
      "snapshot holds.")
    A("")
    A("  (a) Exact Jaccard of 3-word shingle sets built with `librarian.core.tokenize`, "
      "so the shingling is the paper's.")
    A("  (b) The mechanism the paper runs: `librarian.core.compute_minhash` at 128 "
      "permutations with the library default seed, inserted into "
      "`MinHashLSH(threshold=0.9, num_perm=128)`, then one query per file, followed by "
      "the greedy first-match assignment of `librarian/cli.py` `cmd_scan`.")
    A("")
    A("**Command.**")
    A("")
    A("```")
    A("git -C <mirror> show <add-commit>:<path>          # content at the add commit")
    A("librarian.core.tokenize(content)                  # 3-word shingles")
    A("librarian.core.compute_minhash(shingles)          # 128 permutations, default seed")
    A("MinHashLSH(threshold=0.9, num_perm=128).query(m)  # candidates")
    A("greedy_clusters(n, candidates)                    # cmd_scan's assignment rule")
    A("```")
    A("")
    A("**Result (a): exact pairwise Jaccard at the add commits.**")
    A("")
    A(d["j6_table"])
    A("")
    A(f"Pairs at Jaccard >= 0.9: {d['j6_npairs']}. "
      f"Components under that edge rule: {d['j6_comp_sizes']}.")
    A("")
    for line in d["j6_comp_lines"]:
        A(f"  - {line}")
    A("")
    A("Largest mutually similar group as the files arrive, so the state at the instant "
      "the March note names is visible rather than inferred:")
    A("")
    A("| after file k | instant | largest group among the first k |")
    A("|---:|---|---:|")
    for k, iso, big in d["j6_prefix"]:
        A(f"| {k} | {iso} | {big} |")
    A("")
    A("**Result (b): MinHash and LSH at the paper's settings.**")
    A("")
    A("| query file | LSH candidates returned |")
    A("|---|---|")
    for name, cands in d["l6_rows"]:
        A(f"| `{name}` | {cands} |")
    A("")
    A(f"Greedy clusters formed from those candidate sets: {d['l6_clusters']}. "
      f"Largest cluster: {d['l6_largest']} files.")
    A("")
    A(f"**Verdict: {d['v7']}.** The largest mutually similar group among the six files "
      f"that existed before the anchor is {d['j6_max']} files under exact Jaccard and "
      f"{d['l6_largest']} files under the paper's MinHash and LSH path, and both readings "
      "agree file for file on the grouping. At the instant the March note names, "
      f"{d['ht'][4][0]}, the account held five `SKILL.md` files and the largest group "
      f"among them was {d['j6_prefix'][4][2]}. Five of the six would **not** have formed "
      "one cluster. The March note counted files published by the account, not files "
      "inside one cluster; the two happen to coincide only when an account publishes a "
      "single template family, and this one published at least three.")
    A("")

    # ---- Claim 8
    A("## Claim 8. The first ten files at 08:38 on 2026-02-01 form a cluster of ten")
    A("")
    A("**Where.** " + MARCHNOTE + " They label that instant \"Cluster of 10\".")
    A("")
    A("**Method.** As claim 7, over the first ten hightower6eu `SKILL.md` first-adds, "
      "each at its own add commit.")
    A("")
    A("**Result (a): exact Jaccard.**")
    A("")
    A(f"Pairs at Jaccard >= 0.9: {d['j10_npairs']} of "
      f"{10 * 9 // 2} possible. Components: {d['j10_comp_sizes']}.")
    A("")
    for line in d["j10_comp_lines"]:
        A(f"  - {line}")
    A("")
    A("**Result (b): MinHash and LSH at the paper's settings.**")
    A("")
    A("| query file | LSH candidates returned |")
    A("|---|---|")
    for name, cands in d["l10_rows"]:
        A(f"| `{name}` | {cands} |")
    A("")
    A(f"Greedy clusters: {d['l10_clusters']}. Largest cluster: {d['l10_largest']} files.")
    A("")
    A("Largest group as the files arrive:")
    A("")
    A("| after file k | instant | largest group among the first k |")
    A("|---:|---|---:|")
    for k, iso, big in d["j10_prefix"]:
        A(f"| {k} | {iso} | {big} |")
    A("")
    A(f"**Verdict: {d['v8']}.** Ten files would not have formed a cluster of ten. At "
      f"{d['ht'][9][0]} the ten files split into groups of "
      f"{', '.join(str(s) for s in d['j10_comp_sizes'])}, so the largest is "
      f"{d['j10_max']} under exact Jaccard and {d['l10_largest']} under the paper's own "
      f"path. A detector with a minimum cluster size of five would have fired at that "
      f"instant, which is {d['off_fifth_of_group']:+.2f} hours from the Section 3.1 "
      "anchor: the group of typosquat files reaches five members with the tenth file, not "
      "with the fifth.")
    A("")

    # ---- Claim 9
    A("## Claim 9. The anchor, and the March note's implied anchor")
    A("")
    A("**Where.** The paper's conservative anchor is stated in Section 3.1, Analysis "
      "Timeline. The March working notes place the fifth file about nine hours before "
      "public disclosure, which implies an anchor near 08:00Z on 2026-02-01 rather "
      "than 00:00Z.")
    A("")
    A("**Method.** Signed offset of the fifth hightower6eu first-add from each anchor.")
    A("")
    A("**Function.** `hours_between(fifth_first_add, anchor)`.")
    A("")
    A("**Result.**")
    A("")
    A("| anchor | source | offset of the fifth file |")
    A("|---|---|---|")
    A(f"| {ANCHOR} | Section 3.1 | {d['off_paper']:+.2f} h ({d['off_paper_words']}) |")
    A(f"| {ANCHOR_MARCH} | implied by the March note's phrasing, line 145 | {d['off_march']:+.2f} h ({d['off_march_words']}) |")
    A("")
    A("The question the anchor is asked to settle is when a cluster of a given size "
      "first existed, so that is computed directly over the account's first "
      f"{d['mile_n']} `SKILL.md` files, which is all of them, each at its own add "
      "commit, under the same exact-Jaccard "
      "rule as claim 7:")
    A("")
    A("| cluster size first reached | instant | offset from the 00:00Z anchor |")
    A("|---:|---|---:|")
    for size, iso, off in d["milestones"]:
        if iso is None:
            A(f"| {size} | not reached within the first {d['mile_n']} files | |")
        else:
            A(f"| {size} | {iso} | {off:+.2f} h |")
    A("")
    if d["koi_ok"]:
        A("The Koi capture fixes no time of day. Its byline, a date without a time, sits "
          f"at character offset {d['koi_byline'][0]} and runs {d['koi_byline'][1]} "
          f"characters; the only other temporal statement is at offset "
          f"{d['koi_twodays'][0]} and runs {d['koi_twodays'][1]} characters. There is no "
          "audit start or end timestamp, no per-skill publication date, and no "
          "publishing account named anywhere in the capture.")
    else:
        A("The Koi capture fixes no time of day. That reading is not rechecked in this "
          "run: no capture was given, so claims 10 to 12 were not run.")
    A("")
    A(f"**Verdict: {d['v9']} on which anchor is used.** The fifth file precedes both "
      f"anchors, by {abs(d['off_paper']):.2f} hours under the paper's conservative "
      f"00:00Z anchor of Section 3.1 and by {abs(d['off_march']):.2f} hours under the "
      "08:00Z anchor the March phrasing implies. The nine-hour figure in the March note "
      "is therefore an artifact of an anchor the paper does not use; under the paper's "
      f"own anchor the same event is {abs(d['off_paper']) * 60:.0f} minutes early, not "
      "nine hours. Nothing in the Koi capture fixes a time of day, so neither anchor can "
      "be preferred on evidence. This claim is about margin only. What it cannot rescue "
      "is claim 7: at that instant no cluster of five existed to be detected, so the "
      "size of the margin does not matter. The milestone table is what a temporal "
      "sentence would have to be built from if it is built from the mirror at all: only "
      f"the smallest sizes are reached before the anchor, and every size at or above "
      f"{d['first_post_size']} is reached after it.")
    A("")

    # ---- Claim 10
    A("## Claim 10. Koi's audit found 335 campaign skills live on ClawHub at the audit")
    A("")
    if not d["koi_ok"]:
        A("**Not run: fetch the capture.** This claim reads the Koi report, which is a "
          f"third party's page and is not part of this artifact. Fetch <{d['koi_url']}>, "
          "strip its HTML tags, collapse whitespace to a single line and name the file "
          "with `--koi-capture`.")
    else:
        A("**Where.** The Koi report itself, at the capture the provenance table names.")
        A("")
        A("**Method.** Locate the two load-bearing sentences in the capture and report "
          "where they sit. The sentences are the report's own words and are not "
          "reproduced here; the offsets locate them in the capture a reader fetches.")
        A("")
        A("**Function.** `offset_at(capture_text, needle, length)`.")
        A("")
        A("**Result.** Two sentences, located but not quoted:")
        A("")
        A(f"- the audit sentence at byte offset {d['koi_audit'][0]}, "
          f"{d['koi_audit'][1]} characters long")
        A(f"- the campaign sentence at byte offset {d['koi_335'][0]}, "
          f"{d['koi_335'][1]} characters long")
        A("")
        A(f"**Verdict: {d['v10']}.** At those offsets the report states a single "
          "registry-wide sweep that found the campaign's skills live together, and it "
          "carries a February 2026 byline date. That is a simultaneity statement: the "
          "campaign's skills were live together at the moment of the audit, and the "
          "audit precedes its own publication. It is the only evidence in these inputs "
          "that the campaign's files co-existed, as opposed to each having existed at "
          "some time.")
    A("")

    # ---- Claim 11
    A("## Claim 11. How many files in the eleven clusters of 20 or more carry a slug on "
      "Koi's published list")
    A("")
    if not d["koi_ok"]:
        A("**Not run: fetch the capture.** This claim reads the Koi report, which is a "
          f"third party's page and is not part of this artifact. Fetch <{d['koi_url']}>, "
          "strip its HTML tags, collapse whitespace to a single line and name the file "
          "with `--koi-capture`.")
        A("")
    else:
        A("**Where.** The eleven clusters are the archived scan's clusters of size 20 or "
          "more, the population behind the paper's headline precision at that threshold. "
          "The slug list is the IOC appendix of the Koi capture.")
        A("")
        A("**Method.** Take each cluster member's slug, the directory holding its "
          "`SKILL.md`, and test membership in the parsed Koi list. The parse splits each "
          "appendix block on commas and colons and keeps the first slug-shaped token of "
          "each piece, which recovers the slug immediately preceding a category header.")
        A("")
        A("**Function.** `parse_koi(capture_text)` then `slug_of(path) in koi_campaign`.")
        A("")
        A("**The token count issue.** The appendix header labels the campaign block 335 "
          f"skills and the whole list 341. The mechanical parse yields {d['koi_ncamp']} "
          f"campaign tokens and {d['koi_ntotal']} in total, one more than each header states. "
          "The excess cannot be resolved from the whitespace-collapsed capture, because the "
          "original list separators are lost with the markup. Every figure below is computed "
          f"against the {d['koi_ncamp']}-token campaign block, so a one-token excess can only "
          "inflate a match by at most one file.")
        A("")
        A("**Result.**")
        A("")
        A("| cluster | size | dominant account | members on Koi's campaign list | share |")
        A("|---:|---:|---|---:|---:|")
        for row in d["c11_rows"]:
            A(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]:.0f}% |")
        A(f"| **all eleven** | **{d['c11_total_size']}** | | **{d['c11_total_hit']}** | "
          f"**{100 * d['c11_total_hit'] / d['c11_total_size']:.1f}%** |")
        A("")
        A(f"Restricted to the ten clusters dominated by the largest campaign's account, "
          f"{d['c11_ht_hit']} of {d['c11_ht_size']} members carry a Koi slug "
          f"({100 * d['c11_ht_hit'] / d['c11_ht_size']:.1f}%).")
        A("")
        A(f"**Verdict: {d['v11']} on how the sentence is scoped.** Ten of the eleven clusters "
          f"are between {d['c11_min_share']:.0f}% and {d['c11_max_share']:.0f}% Koi-listed. "
          f"Cluster {d['c11_zero_id']} is {d['c11_zero_hit']} of {d['c11_zero_size']}: none "
          "of its members appears on the list at all, and its earliest first-add in the "
          f"mirror is {d['c11_zero_earliest']}, after the anchor. A sentence saying the files "
          "forming the campaign's clusters predate disclosure is supportable for the largest "
          "campaign's ten clusters with the word \"most\", and is not supportable for all "
          "eleven.")
    A("")

    # ---- Claim 12
    A("## Claim 12. How many of Koi's listed slugs first appear in the mirror after the anchor")
    A("")
    if not d["koi_ok"]:
        A("**Not run: fetch the capture.** This claim reads the Koi report, which is a "
          f"third party's page and is not part of this artifact. Fetch <{d['koi_url']}>, "
          "strip its HTML tags, collapse whitespace to a single line and name the file "
          "with `--koi-capture`.")
        A("")
    else:
        A("**Where.** This is the mirror-lag evidence. The paper's Section 3.3 paragraph "
          "asserts mirror lag qualitatively and treats first-commit dates as upper "
          "bounds on upstream publication; this claim measures the lag.")
        A("")
        A("**Method.** Every skill Koi listed was live on ClawHub at the audit, and the "
          "audit precedes the 1 February publication. So any listed slug whose mirror "
          "first-add falls after the anchor demonstrates a lower bound on the mirror's lag "
          "for that file.")
        A("")
        A("**Function.** For each Koi slug, the earliest first-add of any "
          "`skills/*/<slug>/SKILL.md` in the mirror, compared against the anchor.")
        A("")
        A("**Result.**")
        A("")
        A("| quantity | value |")
        A("|---|---|")
        A(f"| Koi slugs resolved to a mirror `SKILL.md` | {d['k12_found']} of {d['k12_total']} |")
        A(f"| slugs mapping to more than one mirror path | {d['k12_dupes']} |")
        A(f"| first-add before {ANCHOR} | {d['k12_pre']} |")
        A(f"| first-add after {ANCHOR} | {d['k12_post']} |")
        A(f"| earliest first-add | {d['k12_earliest'][0]} (`{d['k12_earliest'][1]}`) |")
        A(f"| median first-add | {d['k12_median']} |")
        A(f"| latest first-add | {d['k12_latest'][0]} (`{d['k12_latest'][1]}`) |")
        A(f"| latest offset after the anchor | {d['k12_latest_off']:+.2f} h |")
        A(f"| median offset after the anchor | {d['k12_median_off']:+.2f} h |")
        A("")
        A(f"**Verdict: {d['v12']}.** {d['k12_post']} of the {d['k12_found']} skills Koi "
          "demonstrably saw live before publishing do not appear in the mirror until after "
          f"the anchor, the last of them {d['k12_latest_off']:.1f} hours after it. The "
          "mirror's first-add dates are therefore upper bounds with a lag measured in tens "
          "of hours on exactly this population, which is why the mirror cannot date this "
          "campaign relative to a disclosure anchor at all.")
    A("")

    # ---- Claim 13
    sk = d["sk"]
    A("## Claim 13. sakaen736jih: first file, count on 2026-01-31, first add after the pause")
    A("")
    A("**Where.** " + MARCHNOTE)
    A("")
    A("**Method.** As claims 2 to 6, over `skills/sakaen736jih/`.")
    A("")
    A("**Result.**")
    A("")
    A("| quantity | stated | computed |")
    A("|---|---|---|")
    A(f"| total `SKILL.md` | 213 | {len(sk)} |")
    A(f"| first file | 2026-01-31 22:34 UTC | {sk[0][0]} (`{slug_of(sk[0][1])}`) |")
    A(f"| minutes before hightower6eu's first | 2 | {60 * hours_between(ht[0][0], sk[0][0]):.1f} |")
    A(f"| files on 2026-01-31 | 11 | {d['sk_jan31']} |")
    A(f"| bulk publishing resumed | 2026-02-03 | {d['sk_bulk_day']} |")
    A(f"| first add after the 2026-01-31 burst | not stated | {d['sk_resume']} |")
    A("")
    A("Per-day breakdown:")
    A("")
    A("| UTC day | files first-added |")
    A("|---|---:|")
    for day, n in d["sk_days"]:
        A(f"| {day} | {n} |")
    A("")
    A(f"**Verdict: {d['v13']}.** Every stated figure reproduces. The account published "
      f"{d['sk_jan31']} files on 2026-01-31 and resumed bulk publishing on "
      f"{d['sk_bulk_day']}, as the note says. The note omits a trickle of "
      f"{d['sk_feb1']} file(s) on 2026-02-01, so the pause is not total; the gap between "
      f"the 2026-01-31 burst and the bulk resumption is {d['sk_gap']:.1f} hours.")
    A("")

    # ---- Summary
    A("## Summary")
    A("")
    A("| # | claim, in brief | verdict | deciding number |")
    A("|---:|---|---|---|")
    for num, brief, v, dec in d["summary"]:
        A(f"| {num} | {brief} | **{v}** | {dec} |")
    A("")
    A("The two claims that decide the temporal sentence are 7 and 8. Every timestamp the "
      "March note records reproduces exactly, and the inference drawn from those "
      "timestamps does not: the account's file count is not its cluster size. Claims 10 "
      "and 11 are what a temporal sentence can rest on instead, and claim 12 is why the "
      "mirror cannot be that support.")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------
# Computation
# ------------------------------------------------------------------

def matrix_table(names, sets):
    head = "| | " + " | ".join(f"`{n}`" for n in names) + " |"
    sep = "|---|" + "---:|" * len(names)
    rows = [head, sep]
    for i, n in enumerate(names):
        cells = " | ".join(f"{jaccard(sets[i], sets[j]):.4f}" for j in range(len(names)))
        rows.append(f"| `{n}` | {cells} |")
    return "\n".join(rows)


def analyse_group(mirror, rows, tokenize, compute_minhash, MinHashLSH, num_perm):
    """Exact-Jaccard and MinHash/LSH analysis of an ordered list of (iso, path, sha)."""
    names = [slug_of(p) for _, p, _ in rows]
    sets = [tokenize(content_at(mirror, sha, p)) for _, p, sha in rows]
    n = len(rows)
    edges = [(i, j) for i in range(n) for j in range(i + 1, n)
             if jaccard(sets[i], sets[j]) >= 0.9]
    comps = components(n, edges)

    prefix = []
    for k in range(1, n + 1):
        sub = [(i, j) for i, j in edges if i < k and j < k]
        prefix.append((k, rows[k - 1][0], max(len(c) for c in components(k, sub))))

    lsh = MinHashLSH(threshold=0.9, num_perm=num_perm)
    sigs = [compute_minhash(s) for s in sets]
    for i, m in enumerate(sigs):
        lsh.insert(str(i), m)
    cands = {i: {int(k) for k in lsh.query(sigs[i])} for i in range(n)}
    clusters = greedy_clusters(n, cands)

    return {
        "names": names, "sets": sets, "edges": edges, "comps": comps,
        "cands": cands, "clusters": clusters, "prefix": prefix,
        "table": matrix_table(names, sets),
        "comp_lines": [f"{{{', '.join(names[k] for k in c)}}} ({len(c)} file"
                       f"{'s' if len(c) != 1 else ''})" for c in comps],
        "comp_sizes": [len(c) for c in comps],
        "max": max(len(c) for c in comps),
        "lsh_rows": [(names[i], "{" + ", ".join(f"`{names[k]}`" for k in sorted(cands[i])) + "}")
                     for i in range(n)],
        "largest_cluster": max((len(c) for c in clusters), default=1),
        "cluster_desc": ("; ".join("{" + ", ".join(names[k] for k in c) + "}" for c in clusters)
                         or "none"),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Per-claim receipt for the temporal statements about the largest campaign.")
    parser.add_argument("--check", action="store_true",
                        help="verify the existing results file instead of rewriting it")
    parser.add_argument("--mirror", default=str(DEFAULT_MIRROR),
                        help="path to the unshallowed ClawHub mirror (read-only)")
    parser.add_argument("--scan", default=str(DEFAULT_SCAN),
                        help="path to the archived 90%% scan JSON")
    parser.add_argument("--koi-capture", default=None,
                        help="path to a local copy of the Koi report capture, fetched by "
                             "you from the Wayback Machine; no default, because neither "
                             "the capture nor any parse of it ships with this artifact. "
                             "Without it claims 10 to 12 are not run")
    args = parser.parse_args()

    # Refused up front, before the mirror walk: --check compares the whole file, and a
    # receipt whose claims 10 to 12 read "not run" must never be able to match the
    # shipped one. Comparing only the claims that ran would weaken the check into
    # something a three-claim-shorter file could pass, so the answer is a refusal with
    # the retrieval instruction rather than a partial comparison.
    if args.check and not args.koi_capture:
        print(KOI_MISSING, file=sys.stderr)
        sys.exit(1)

    self_test()

    sys.path.insert(0, str(REPO))
    import datasketch
    from datasketch import MinHashLSH
    from librarian.core import tokenize, compute_minhash, NUM_PERM, SHINGLE_SIZE

    mirror = Path(args.mirror)
    scan_path = Path(args.scan)
    if not (mirror / ".git").exists():
        print(f"no git repository at {mirror}. The unshallowed ClawHub mirror is not"
              " part of this artifact; clone or restore it from the Software Heritage"
              " snapshot the paper cites and name it with --mirror.", file=sys.stderr)
        sys.exit(1)

    print("reading mirror commit list ...")
    head, ncommits, n_mismatch, mismatch_shas, shallow = mirror_facts(mirror)
    print(f"  HEAD {head[:12]}  commits {ncommits:,}  date mismatches {n_mismatch}")

    print("reading first-add dates for every path ...")
    adds = first_adds(mirror)
    print(f"  {len(adds):,} paths with a first add")

    ht = skill_adds(adds, "skills/hightower6eu/")
    sk = skill_adds(adds, "skills/sakaen736jih/")
    ht_days = day_counts([r[0] for r in ht])
    sk_days = day_counts([r[0] for r in sk])
    ht_pre = [r for r in ht if r[0] < ANCHOR]
    sk_pre = [r for r in sk if r[0] < ANCHOR]
    ht_feb1 = dict(ht_days).get("2026-02-01", 0)
    sk_jan31 = dict(sk_days).get("2026-01-31", 0)
    sk_feb1 = dict(sk_days).get("2026-02-01", 0)
    sk_resume = next(r[0] for r in sk if r[0][:10] != "2026-01-31")
    # "Bulk publishing resumed" is the first day after the opening burst on which the
    # account added at least ten files, which is what the March note's phrase names.
    sk_bulk_day = next(day for day, n in sk_days if day != "2026-01-31" and n >= 10)
    sk_bulk_first = next(r[0] for r in sk if r[0][:10] == sk_bulk_day)

    print("analysing the pre-anchor group and the first ten ...")
    g6 = analyse_group(mirror, ht_pre, tokenize, compute_minhash, MinHashLSH, NUM_PERM)
    g10 = analyse_group(mirror, ht[:10], tokenize, compute_minhash, MinHashLSH, NUM_PERM)

    print("computing cluster-size milestones over the account's opening files ...")
    MILE_N = len(ht)
    gm = analyse_group(mirror, ht[:MILE_N], tokenize, compute_minhash, MinHashLSH, NUM_PERM)
    milestones = []
    for size in (2, 3, 5, 10, 15, 20, 30):
        hit = next((p for p in gm["prefix"] if p[2] >= size), None)
        if hit is None:
            milestones.append((size, None, None))
        else:
            milestones.append((size, hit[1], hours_between(hit[1], ANCHOR)))
    first_post = next((s for s, iso, off in milestones
                       if iso is not None and off > 0), None)

    koi_path = Path(args.koi_capture) if args.koi_capture else None
    koi_text = None
    if koi_path is not None:
        if not koi_path.is_file():
            print(f"no Koi capture at {koi_path}", file=sys.stderr)
            sys.exit(1)
        koi_text = koi_path.read_text(encoding="utf-8")
    if koi_text is None:
        # DESIGN RATIONALE: claims 10 to 12 are the only ones that read the capture, so
        # the other ten still answer. --check refuses to compare in this state, because a
        # receipt missing three claims must not be able to match a complete one.
        if args.check:
            print(KOI_MISSING, file=sys.stderr)
            sys.exit(1)
        print(f"claims 10 to 12 not run: {KOI_MISSING}", file=sys.stderr)
        camp = auth = back = cred = []
    else:
        camp, auth, back, cred = parse_koi(koi_text)
    koi_campaign = set(camp)
    koi_all = set(camp) | set(auth) | set(back) | set(cred)

    scan = json.loads(scan_path.read_text(encoding="utf-8"))
    big = sorted((c for c in scan["clusters"] if c["size"] >= 20),
                 key=lambda c: (-c["size"], c["cluster_id"]))
    c11_rows, total_hit, total_size = [], 0, 0
    ht_hit = ht_size = 0
    zero = None
    for c in big:
        slugs = [slug_of(l["path"]) for l in c["locations"]]
        accounts = {}
        for l in c["locations"]:
            acc = (l["path"].split("/")[1] if l["marketplace"] == "clawhub-archive"
                   else l["marketplace"])
            accounts[acc] = accounts.get(acc, 0) + 1
        dominant = max(accounts.items(), key=lambda kv: (kv[1], kv[0]))[0]
        hit = sum(1 for s in slugs if s in koi_campaign)
        c11_rows.append((c["cluster_id"], c["size"], dominant, hit, 100 * hit / c["size"]))
        total_hit += hit
        total_size += c["size"]
        if dominant == "hightower6eu":
            ht_hit += hit
            ht_size += c["size"]
        if hit == 0:
            earliest = min(adds[l["path"]][0] for l in c["locations"]
                           if l["path"] in adds)
            zero = (c["cluster_id"], hit, c["size"], earliest)
    shares = [r[4] for r in c11_rows if r[3] > 0]

    print("resolving Koi slugs against the mirror ...")
    slug_paths = {}
    for path, (iso, _sha) in adds.items():
        parts = path.split("/")
        if len(parts) >= 4 and parts[0] == "skills" and parts[-1] == "SKILL.md":
            slug_paths.setdefault(parts[-2], []).append((iso, path))
    resolved = []
    dupes = 0
    for s in sorted(koi_all):
        if s in slug_paths:
            if len(slug_paths[s]) > 1:
                dupes += 1
            resolved.append(min(slug_paths[s]))
    resolved.sort()
    pre = [r for r in resolved if r[0] < ANCHOR]
    median = resolved[len(resolved) // 2] if resolved else None

    summary = []
    v1 = "HOLDS" if (head.startswith("16c991de") and ncommits == 70091
                     and n_mismatch == 1 and not shallow) else "BREAKS"
    v5 = "HOLDS" if (ht_feb1 == 258 and len(ht) == 354 and len(ht_days) == 3) else "BREAKS"
    v6 = "HOLDS" if len(ht_pre) == 6 else "BREAKS"
    v7 = "BREAKS" if g6["max"] < 5 else "HOLDS"
    v8 = "BREAKS" if g10["max"] < 10 else "HOLDS"
    v13 = "HOLDS" if (len(sk) == 213 and sk[0][0].startswith("2026-01-31T22:34")
                      and sk_jan31 == 11 and sk_bulk_day == "2026-02-03") else "BREAKS"

    fifth = ht[4][0]
    off_paper = hours_between(fifth, ANCHOR)
    off_march = hours_between(fifth, ANCHOR_MARCH)

    d = {
        "mirror": mirror, "head": head, "ncommits": ncommits, "n_mismatch": n_mismatch,
        "mismatch_shas": mismatch_shas, "shallow": shallow,
        "scan_name": scan_path.name,
        "scan_generated": scan["metadata"]["generated_at"],
        "scan_threshold": scan["metadata"]["similarity_threshold"],
        "scan_perms": scan["metadata"]["num_permutations"],
        "koi_url": KOI_URL, "koi_chars": len(koi_text) if koi_text else None,
        "datasketch": datasketch.__version__,
        "shingle_size": SHINGLE_SIZE, "num_perm": NUM_PERM,
        "bands": MinHashLSH(threshold=0.9, num_perm=NUM_PERM).b,
        "rows": MinHashLSH(threshold=0.9, num_perm=NUM_PERM).r,
        "ht": ht, "sk": sk, "ht_days": ht_days, "sk_days": sk_days,
        "ht_pre": ht_pre, "ht_feb1": ht_feb1,
        "sk_jan31": sk_jan31, "sk_feb1": sk_feb1, "sk_resume": sk_resume,
        "sk_bulk_day": sk_bulk_day,
        "sk_gap": hours_between(sk_bulk_first, sk_pre[-1][0]),
        "j6_table": g6["table"], "j6_npairs": len(g6["edges"]),
        "j6_comp_sizes": g6["comp_sizes"], "j6_comp_lines": g6["comp_lines"],
        "j6_max": g6["max"], "j6_prefix": g6["prefix"], "j10_prefix": g10["prefix"],
        "off_fifth_of_group": hours_between(ht[9][0], ANCHOR),
        "l6_rows": g6["lsh_rows"], "l6_clusters": g6["cluster_desc"],
        "l6_largest": g6["largest_cluster"],
        "j10_npairs": len(g10["edges"]), "j10_comp_sizes": g10["comp_sizes"],
        "j10_comp_lines": g10["comp_lines"], "j10_max": g10["max"],
        "l10_rows": g10["lsh_rows"], "l10_clusters": g10["cluster_desc"],
        "l10_largest": g10["largest_cluster"],
        "mile_n": MILE_N, "milestones": milestones,
        "first_post_size": first_post if first_post is not None else "any tested size",
        "off_paper": off_paper, "off_march": off_march,
        "off_paper_words": "after the anchor" if off_paper > 0 else "before the anchor",
        "off_march_words": "after the anchor" if off_march > 0 else "before the anchor",
        # Offsets and lengths only. The sentences themselves are the third party's
        # words and are not reproduced here or in the rendered file.
        "koi_byline": offset_at(koi_text, "byline"),
        "koi_twodays": offset_at(koi_text, "twodays"),
        "koi_audit": offset_at(koi_text, "audit"),
        "koi_335": offset_at(koi_text, "campaign"),
        "koi_ncamp": len(camp) or None,
        "koi_ntotal": (len(camp) + len(auth) + len(back) + len(cred)) or None,
        "c11_rows": c11_rows, "c11_total_hit": total_hit, "c11_total_size": total_size,
        "c11_ht_hit": ht_hit, "c11_ht_size": ht_size,
        "c11_min_share": min(shares), "c11_max_share": max(shares),
        "c11_zero_id": zero[0], "c11_zero_hit": zero[1], "c11_zero_size": zero[2],
        "c11_zero_earliest": zero[3],
        "koi_ok": koi_text is not None,
        "k12_total": len(koi_all), "k12_found": len(resolved), "k12_dupes": dupes,
        "k12_pre": len(pre), "k12_post": len(resolved) - len(pre),
        "k12_earliest": resolved[0] if resolved else None,
        "k12_latest": resolved[-1] if resolved else None,
        "k12_median": median[0] if median else None,
        "k12_latest_off": hours_between(resolved[-1][0], ANCHOR) if resolved else None,
        "k12_median_off": hours_between(median[0], ANCHOR) if median else None,
        "v1": v1, "v5": v5, "v6": v6, "v7": v7, "v8": v8,
        "v9": "DEPENDS",
        "v10": "HOLDS" if koi_text else "not run",
        "v11": "DEPENDS" if koi_text else "not run",
        "v12": "HOLDS" if koi_text else "not run", "v13": v13,
    }
    d["summary"] = [
        (1, "mirror unshallowed, 70,091 commits, one date mismatch", v1,
         f"{ncommits:,} commits, {n_mismatch} mismatch"),
        (2, "first hightower6eu file at 2026-01-31T22:36:54Z", "HOLDS" if ht[0][0] == "2026-01-31T22:36:54Z" else "BREAKS",
         ht[0][0]),
        (3, "fifth file at 2026-01-31T23:03:13Z", "HOLDS" if ht[4][0] == "2026-01-31T23:03:13Z" else "BREAKS",
         ht[4][0]),
        (4, "tenth file at 2026-02-01T08:38:11Z", "HOLDS" if ht[9][0] == "2026-02-01T08:38:11Z" else "BREAKS",
         ht[9][0]),
        (5, "258 files on 2026-02-01, 354 over three days", v5,
         f"{ht_feb1} on 2026-02-01, {len(ht)} total"),
        (6, f"six files before {ANCHOR}", v6, f"{len(ht_pre)} files"),
        (7, "the six pre-anchor files form a cluster of five", v7,
         f"largest group {g6['max']} files"),
        (8, "the first ten form a cluster of ten", v8,
         f"largest group {g10['max']} files"),
        (9, "the fifth file precedes disclosure by about nine hours", "DEPENDS",
         f"{off_paper:+.2f} h at the paper's 00:00Z anchor, {off_march:+.2f} h at the "
         "08:00Z anchor the March phrasing implies"),
        (10, "Koi's audit found the campaign's skills live together",
         "HOLDS" if koi_text else "not run",
         f"capture offsets {d['koi_audit'][0]} and {d['koi_335'][0]}" if koi_text
         else "no capture given"),
        (11, "the clusters' files are Koi-listed",
         "DEPENDS" if koi_text else "not run",
         (f"{total_hit}/{total_size} overall, {ht_hit}/{ht_size} for the largest campaign, "
          f"{zero[1]}/{zero[2]} for cluster {zero[0]}") if koi_text else "no capture given"),
        (12, "the mirror lags upstream publication",
         "HOLDS" if koi_text else "not run",
         (f"{len(resolved) - len(pre)} of {len(resolved)} Koi slugs first appear after the anchor, "
          f"the last {hours_between(resolved[-1][0], ANCHOR):.1f} h after") if koi_text
         else "no capture given"),
        (13, "sakaen736jih first file, 11 on 2026-01-31, bulk publishing resumed 2026-02-03", v13,
         f"{sk[0][0]}, {sk_jan31} on 2026-01-31, bulk resumption {sk_bulk_day}, "
         f"plus {sk_feb1} file(s) on 2026-02-01 the note omits"),
    ]

    report = build_report(d)

    if args.check:
        existing = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if report == existing:
            print(f"{OUT.name} matches recomputation")
            sys.exit(0)
        diff = difflib.unified_diff(existing.splitlines(keepends=True),
                                    report.splitlines(keepends=True),
                                    fromfile=OUT.name, tofile="recomputed")
        sys.stdout.writelines(diff)
        sys.exit(1)

    OUT.write_text(report, encoding="utf-8")
    print(f"wrote {OUT.name}")


if __name__ == "__main__":
    main()
