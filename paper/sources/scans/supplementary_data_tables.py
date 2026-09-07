#!/usr/bin/env python3
"""Five supplementary data tables computed from files already in the artifact.

The five, in the order the output file reports them, and the part of the paper
each supports (section numbers follow the order of the paper's section and
subsection headings; table numbers follow caption order):

  1. Precision by cluster size band, at cluster and file level. Supports
     Table 4, "Precision and recall at cluster size thresholds", and the
     caption's statement that only the >= 20 and >= 10 rows reproduce from
     the released ground truth (Section 4.4).
  2. Benign content inside attributed clusters: how much unattributed content
     sits inside the clusters credited as true positives (Table 4 again, read
     from the operator's side).
  3. Payload-indicator recall for the seven unclustered files of Section 5.3,
     "none of these 7 files landed in any cluster": would a grep for the
     iocs.json payload indicators have found what clustering found, and what
     would it add?
  4. Filter effects: whether the tokenizer includes the YAML frontmatter,
     whether the 100-character filter applies before or after tokenization,
     and whether an indexed document can be shorter than three words
     (Section 3.2, "minimum of 100 characters of content"; Section 3.3,
     "individual words were used as shingles").
  5. Populations and denominators: the 341 / 354 / 352 / 351 / 337 counts and
     how each maps to the abstract's within-archive recall claim (Section 4.4,
     "of the 352 scanned, 351 appeared in clusters").

Inputs, all read-only:
  scan_20260314_threshold90_skillonly.json   the archived scan, beside this script
  paper/iocs.json                            the released ground truth
  file-level-precision-20260907.md,
  threshold-sweep-20260314.md                results files beside this script,
                                             read only to check the lines cited
  librarian/core.py, librarian/cli.py        the released tool, resolved by
                                             content hash (see `release_source`)
  LIBRARIAN_CORPUS                           the pinned March corpus, a checkout
                                             of each repository at the commit
                                             recorded in
                                             paper/supplementary/repository-commits.md;
                                             section 4 walks it and the content
                                             marker reads file text from it
  paper/main-acm.tex                         optional; not part of the artifact.
                                             When present, every paper quote is
                                             verified against it; when absent the
                                             run prints "paper quotes not
                                             verified" and continues, and the
                                             rendered quotes are identical.

Environment:
  LIBRARIAN_CORPUS              required; see above
  SUPP_TABLES_TOOL_REVISIONS    comma-separated git refs to search for the
                                released `librarian/` bytes; RELEASE_BLOBS is the
                                authority, so a ref carrying different code is
                                refused
  SUPP_TABLES_REDACT_HISTORY=1  render the repository commit row as a
                                placeholder, which is the released rendering

Output: paper/supplementary/supplementary-data-tables.md, overwritten each run.
Nothing here edits the paper.

Run, with LIBRARIAN_CORPUS set and SUPP_TABLES_REDACT_HISTORY=1:
  python paper/sources/scans/supplementary_data_tables.py

The "backup" path rule. The released tool skips any path whose string contains
"backup" before it reads the file, and the archived scan was made with that
rule. `answer_tokenization` and the `backup_in_path` field of `resolve_absent`
apply the same substring test so that the walk here sees what the archived
scan saw; the numbers in the output file are the released tool's.

The content-marker logic for section 3 is imported from `file_level_precision.py`
rather than restated, so the two files apply one rule: `payload_indicators`,
`ContentMarker`, `account_of` and `WEAK_INDICATOR` all come from there.

DESIGN RATIONALE for CODE CITATIONS: a line citation into a source file goes
stale the moment someone inserts a paragraph above it. Every `librarian/` and
results-file citation this script emits is checked at startup against the
literal it is supposed to point at, and the run aborts if one has moved. A
stale citation is then a failed run rather than a wrong external document.

DESIGN RATIONALE for PAPER CITATIONS: the paper's tex is not part of the
artifact, so a line number into it is nothing a reader could check; it is never
cited by line number here. A paper citation is a
section number plus a verbatim quote of under twelve words. At generation time
the quote is located in `paper/main-acm.tex` with whitespace collapsed, so a
quote may span a line break, and the section number the tex implies is compared
against the number declared in PAPER_QUOTES; a mismatch on either aborts the run,
and an absent tex skips the check rather than failing it. The rendered file
carries only the section number and the quote, so a reader needs no copy of the
tex to check it, and no line number can go stale in it.

Every answer function has a self-test on toy inputs, run before any real input
is read, so a broken counting rule fails on three hand-checked clusters rather
than silently on 2,622 real ones.
"""
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))   # for `librarian.core`, imported inside the self-test

import file_level_precision as FLP  # noqa: E402  (path set above)

SCAN = HERE / "scan_20260314_threshold90_skillonly.json"
IOCS = REPO / "paper" / "iocs.json"
FLP_RESULTS = HERE / "file-level-precision-20260907.md"
SWEEP = HERE / "threshold-sweep-20260314.md"
# `librarian/` citations are LOGICAL paths, resolved against the RELEASED tool
# rather than against whatever tree this script runs in. See `release_source`.
CORE = "librarian/core.py"
CLI = "librarian/cli.py"
PAPER = REPO / "paper" / "main-acm.tex"
OUT = REPO / "paper" / "supplementary" / "supplementary-data-tables.md"

# The released tool: the public repository's release commit, and the only
# git ref tried by default.
RELEASE_COMMIT = "b55ceff1fde1ef0678a62067d7e0a6cdac852b3e"

# Git refs `release_source` will try, in order. A checkout that carries the
# released modules under some other ref name adds it here rather than in the
# source, since a ref name that resolves in one clone and not another is a
# property of the clone:
#     SUPP_TABLES_TOOL_REVISIONS="b55ceff,origin/main"
# This is a convenience for finding the bytes, never a licence to trust them.
# RELEASE_BLOBS below is the authority: whatever a lookup returns must hash to
# these, so a citation is never checked against a tree that differs from the
# release, and an added ref that carries different code is refused exactly
# like a working tree that differs from it.
TOOL_REVISIONS = tuple(r.strip() for r in os.environ.get(
    "SUPP_TABLES_TOOL_REVISIONS", RELEASE_COMMIT).split(",") if r.strip())

RELEASE_BLOBS = {
    CORE: "169d13582c00ef3a117bcfa44989f75ba37f5123750b63675ce3d76f2c3ac332",
    CLI: "96cfd205e1f971fdc4f02b7cdcb16589f3b7f7778c15ca9c18ffcb9f53080ba3",
}

# The repository commit this run was made from. It names a commit only someone
# with that history can resolve, so the released copy renders a placeholder.
# Set SUPP_TABLES_REDACT_HISTORY=1 to produce the released rendering.
HISTORY_PLACEHOLDER = "<private-history>"
REDACT_HISTORY = os.environ.get("SUPP_TABLES_REDACT_HISTORY") == "1"

CORPUS = Path(os.path.expanduser(os.environ.get("LIBRARIAN_CORPUS", ""))) if os.environ.get(
    "LIBRARIAN_CORPUS") else None

CLAWHUB = "clawhub-archive"
IOC_ACCOUNT = "hightower6eu"
SINGLETON_ACCOUNTS = ("moonshine-100rze", "anisafifi")
BANDS = ((2, 2), (3, 4), (5, 9), (10, 19), (20, None))
MAX_EXAMPLES = 10
# Indexed files below this token count are reported as a group. The number is a
# reporting choice, not a threshold in the tool: 20 tokens is about the point
# below which a SKILL.md carries no usable prose after normalization.
LOW_TOKEN = 20
# CJK ideographs, kana and hangul. Used only to classify the low-token files, so
# a script the range misses would be counted in the residual "other" group rather
# than mislabeled.
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")

# Local paths are rendered with these placeholders, matching the artifact
# bundle's convention: no machine-specific path reaches the output file.
CORPUS_PLACEHOLDER = "$LIBRARIAN_CORPUS"
PYTHON_PLACEHOLDER = "python"

# The "backup" path rule as the released tool carries it: a substring test over
# the whole path. Cited wherever the output file explains why 864 SKILL.md files
# never reached the scan. Narrowing the rule to the scan root's own first path
# component is not in the released tool, so no citation exists for it and the
# prose describes it without pointing at a line.
RELEASE_BACKUP_RULE = (CORE, 227)

# Every (file, line, literal) the output file cites, checked at startup.
# `cite()` refuses to render a (file, line) that is not in this list, so a
# citation cannot be emitted without also being checked. The paper is not in
# this list: it is cited by section and quote instead, through `paper_ref`.
# Every `librarian/` line below is a line of the RELEASED tool, not of the tree
# this script runs in.
CITATIONS = [
    (CORE, 32, "SHINGLE_SIZE = 3"),
    (*RELEASE_BACKUP_RULE, 'if "backup" in str(md_file).lower():'),
    (CORE, 152, "text = text.lower()"),
    (CORE, 153, r"re.sub(r'\s+', ' ', text).strip()"),
    (CORE, 155, "DESIGN RATIONALE: Keep dashes and alphanumerics"),
    (CORE, 156, "Markdown files have frontmatter (key: value), code blocks, headers"),
    (CORE, 157, "Removing ALL punctuation was too aggressive"),
    (CORE, 158, "Now we keep dashes (important for YAML keys, multi-word terms)"),
    (CORE, 159, r"re.sub(r'[^a-z0-9\s\-]', '', text)"),
    (CORE, 162, "words = [w for w in text.split() if w]"),
    (CORE, 165, "if len(words) < SHINGLE_SIZE:"),
    (CORE, 168, "return set(words)"),
    (CORE, 171, "return set(text[i:i+SHINGLE_SIZE]"),
    (CORE, 174, "return {text} if text else set()"),
    (CORE, 178, "for i in range(len(words) - SHINGLE_SIZE + 1):"),
    (CORE, 235, "if len(content) < 100:"),
    (CORE, 475, "if len(content) < 100:"),
    (CLI, 1485, 'content = md_file.read_text(encoding="utf-8", errors="replace")'),
    (CLI, 1486, "if len(content) < 100:"),
    (CLI, 1514, "shingles = tokenize(f.content)"),
    (SWEEP, 22, "*Recall computed against 354 hightower6eu slugs"),
    (SWEEP, 23, "337/341 = 98.8%"),
    (FLP_RESULTS, 88, "cluster-level TP (strict): 11/11; pure 9, mixed 2"),
    (FLP_RESULTS, 91, "strict: 305/307 = 0.993"),
    (FLP_RESULTS, 113, "cluster-level TP (strict): 30/38; pure 23, mixed 7"),
    (FLP_RESULTS, 116, "strict: 557/682 = 0.817"),
]

# Every (file, line) `cite()` is allowed to render.
_PINNED = {(str(path), lineno) for path, lineno, _ in CITATIONS}

# Every paper citation the output file emits, as (declared section, verbatim
# quote). "abstract" stands for the unnumbered abstract. Each quote must be
# under twelve words and must occur in the tex, with whitespace collapsed, at a
# point whose implied section number equals the declared one.
PAPER_QUOTES = [
    ("abstract", "all 337 Koi-documented malicious skills present in the corpus"),
    ("3.4", "We treated the 341 original IOC slugs from the Clawdex database"),
    ("4.4", "Of the 341 skill slugs in Koi Security's original"),
    ("4.4", "337 resided in the ClawHub archive"),
    ("4.4", "narrower hightower6eu subset (354 IOC slugs)"),
    ("4.4", "of the 352 scanned, 351 appeared in clusters"),
    ("4.4", "rows reproduce from the released ground truth"),
    ("4.4", "Precision and recall at cluster size thresholds"),
    ("3.2", "minimum of 100 characters of content"),
    ("3.2", "the scanner had skipped any path containing"),
    ("3.3", "individual words were used as shingles"),
    ("5.3", "none of these 7 files landed in any cluster"),
    ("5.3", "motivate pairing it with behavioral scanning"),
    ("6", "cluster only with each other"),
    ("abstract", "a within-archive recall expected by construction for template-reuse campaigns"),
]

MAX_QUOTE_WORDS = 12

# Filled by `check_paper_quotes`, read by `paper_ref`. Empty until then, so a
# citation cannot be emitted before the guard has run.
_PAPER_WHERE = {}


_RELEASE_CACHE = {}


def release_source(rel: str) -> str:
    """Return a released `librarian/` module's text, verified by content hash.

    DESIGN RATIONALE: a `librarian/` citation must point at a line of the tool
    a reader can open, which is the release commit, not whatever tree this
    script happens to run in. A checkout ahead of the release would pass a
    line-number check while the emitted numbers pointed at unrelated code.
    Resolution therefore goes to the release, and the content hash is the
    authority rather than the ref name: a lookup that finds the right bytes is
    taken whatever produced it, and a lookup that finds anything else is
    refused even if it came from a ref with the expected name.

    Tried in order: `git show` on each ref in TOOL_REVISIONS, then the working
    tree, which is itself correct when this script runs inside a checkout of
    the release.
    """
    if rel in _RELEASE_CACHE:
        return _RELEASE_CACHE[rel]
    want = RELEASE_BLOBS[rel]
    tried = []
    candidates = [(f"git show {rev}:{rel}", rev) for rev in TOOL_REVISIONS]
    for label, rev in candidates:
        try:
            blob = subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:{rel}"],
                                  capture_output=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            tried.append(f"{label} (unavailable)")
            continue
        if hashlib.sha256(blob).hexdigest() == want:
            _RELEASE_CACHE[rel] = blob.decode("utf-8")
            return _RELEASE_CACHE[rel]
        tried.append(f"{label} (hash mismatch)")
    try:
        blob = (REPO / rel).read_bytes()
        if hashlib.sha256(blob).hexdigest() == want:
            _RELEASE_CACHE[rel] = blob.decode("utf-8")
            return _RELEASE_CACHE[rel]
        tried.append(f"{REPO / rel} (hash mismatch)")
    except OSError:
        tried.append(f"{REPO / rel} (unreadable)")
    raise AssertionError(
        f"cannot resolve the released {rel} (sha256 {want}); tried: "
        + "; ".join(tried)
        + ". Check out the released tool, or name a git ref that carries it in"
          " SUPP_TABLES_TOOL_REVISIONS.")


def _source_lines(path) -> list:
    """The lines a citation is checked against: released text, or a real file."""
    if isinstance(path, str):
        return release_source(path).splitlines()
    return Path(path).read_text(encoding="utf-8").splitlines()


def _rel(path) -> str:
    """How a citation renders: a logical release path, or a repo-relative one."""
    return path if isinstance(path, str) else str(Path(path).relative_to(REPO))


def check_citations(citations=None) -> list:
    """Return the citations whose line no longer holds the literal they cite."""
    stale = []
    for path, lineno, literal in (CITATIONS if citations is None else citations):
        try:
            lines = _source_lines(path)
        except (OSError, AssertionError) as exc:
            stale.append((_rel(path), lineno, literal, f"unreadable: {exc}"))
            continue
        if lineno > len(lines) or literal not in lines[lineno - 1]:
            found = [i + 1 for i, ln in enumerate(lines) if literal in ln]
            stale.append((_rel(path), lineno, literal,
                          f"found at {found}" if found else "not found"))
    return stale


def cite(path, lineno: int) -> str:
    """Render a citation as `relative/path.py:NN`, refusing unpinned lines.

    DESIGN RATIONALE: check_citations only verifies the CITATIONS list, so a
    citation emitted with a line that is not in that list would never be
    checked at all, and could render a plausible-looking wrong number while
    the guard printed success. Rendering therefore goes through the same list
    the guard walks, and an unpinned line is an error.
    """
    if (str(path), lineno) not in _PINNED:
        raise AssertionError(
            f"unpinned citation {_rel(path)}:{lineno}:"
            " add it to CITATIONS so check_citations verifies it")
    return f"`{_rel(path)}:{lineno}`"


# --------------------------------------------------------------------------
# paper citations: section number plus verbatim quote
# --------------------------------------------------------------------------

def normalized_with_lines(text: str):
    """Collapse whitespace per line and join, keeping a source line per character.

    A quote may therefore span a line break in the tex and still be located,
    which is what lets the quotes read as sentences rather than as fragments of
    whichever line the tex wraps on.
    """
    chars, line_of = [], []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        for ch in re.sub(r"\s+", " ", raw).strip():
            chars.append(ch)
            line_of.append(lineno)
        chars.append(" ")
        line_of.append(lineno)
    return "".join(chars), line_of


def section_labels(text: str) -> dict:
    """Map each source line to the section number LaTeX would print for it.

    Counts `\\section{` and `\\subsection{` only, so starred headings and the
    appendix are not numbered here. Lines ahead of the first `\\section` are
    labeled "abstract".
    """
    labels, sec, sub = {}, 0, 0
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.lstrip()
        if stripped.startswith("\\section{"):
            sec += 1
            sub = 0
        elif stripped.startswith("\\subsection{"):
            sub += 1
        if sec == 0:
            labels[lineno] = "abstract"
        else:
            labels[lineno] = str(sec) if sub == 0 else f"{sec}.{sub}"
    return labels


def selftest_paper_refs():
    toy = ("\\begin{abstract}\nalpha beta\n\\end{abstract}\n"
           "\\section{One}\n\\subsection{A}\ngamma\ndelta\n"
           "\\subsection{B}\nepsilon\n"
           "\\section{Two}\nzeta\n"
           "\\section*{Unnumbered}\nomega\n")
    norm, line_of = normalized_with_lines(toy)
    labels = section_labels(toy)

    def where(quote):
        return labels[line_of[norm.index(quote)]]

    assert where("alpha beta") == "abstract", where("alpha beta")
    # "gamma delta" spans a line break in the source and is still found.
    assert "gamma delta" in norm, norm
    assert where("gamma delta") == "1.1", where("gamma delta")
    assert where("epsilon") == "1.2", where("epsilon")
    assert where("zeta") == "2", where("zeta")
    # A starred heading does not advance the counter.
    assert where("omega") == "2", where("omega")
    # A quote that is not in the text is absent rather than mislocated.
    assert "theta" not in norm


def declare_paper_quotes(quotes=None) -> list:
    """Fill `_PAPER_WHERE` from the declared sections, without reading the tex.

    Used when `paper/main-acm.tex` is absent, which is the normal case for a
    reader of the released artifact: the tex is not part of it. The rendered
    citations are identical either way, because a verified quote records the
    section it was found in and that value must equal the declared one for the
    check to pass. Only the word-length rule, which needs no tex, still applies.
    """
    quotes = PAPER_QUOTES if quotes is None else quotes
    bad = []
    for declared, quote in quotes:
        words = len(quote.split())
        if words >= MAX_QUOTE_WORDS:
            bad.append((declared, quote, f"{words} words, must be under {MAX_QUOTE_WORDS}"))
            continue
        _PAPER_WHERE[quote] = declared
    return bad


def check_paper_quotes(path: Path = PAPER, quotes=None) -> list:
    """Verify every paper quote, and fill `_PAPER_WHERE` for `paper_ref`.

    Returns the quotes that are too long, missing, or sitting in a different
    section from the one declared.
    """
    quotes = PAPER_QUOTES if quotes is None else quotes
    text = Path(path).read_text(encoding="utf-8")
    norm, line_of = normalized_with_lines(text)
    labels = section_labels(text)
    bad = []
    for declared, quote in quotes:
        words = len(quote.split())
        if words >= MAX_QUOTE_WORDS:
            bad.append((declared, quote, f"{words} words, must be under {MAX_QUOTE_WORDS}"))
            continue
        at = norm.find(re.sub(r"\s+", " ", quote).strip())
        if at < 0:
            bad.append((declared, quote, "not found in the paper"))
            continue
        found = labels[line_of[at]]
        if found != declared:
            bad.append((declared, quote, f"found in section {found}"))
            continue
        _PAPER_WHERE[quote] = found
    return bad


def paper_ref(quote: str) -> str:
    """Render a paper citation as a section number plus the quote itself."""
    if quote not in _PAPER_WHERE:
        raise AssertionError(
            f"unverified paper quote {quote!r}: add it to PAPER_QUOTES so"
            " check_paper_quotes verifies it")
    where = _PAPER_WHERE[quote]
    label = "the abstract" if where == "abstract" else f"Section {where}"
    return f'{label}, "{quote}"'


# --------------------------------------------------------------------------
# section 4: tokenization and the 100-character filter
# --------------------------------------------------------------------------

def normalize(text: str) -> list:
    """The word list `librarian.core.tokenize` builds before it shingles.

    Mirrors the four normalization statements of `librarian.core.tokenize`,
    which CITATIONS pins by literal rather than by number so this comment cannot
    go stale. Kept as a separate function so the token count of a file can
    be reported without rebuilding its shingles, and cross-checked against the
    real tokenizer in the self-test.
    """
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^a-z0-9\s\-]", "", text)
    return [w for w in text.split() if w]


def selftest_tokenization():
    from librarian.core import tokenize, SHINGLE_SIZE

    assert SHINGLE_SIZE == 3, SHINGLE_SIZE

    # Frontmatter survives normalization: the delimiter becomes a token because
    # dashes are kept, and the YAML keys become tokens because the colon is the
    # only character stripped.
    doc = "---\nname: my-skill\ndescription: Does a thing.\n---\n# Heading\nBody text here.\n"
    words = normalize(doc)
    assert words[:5] == ["---", "name", "my-skill", "description", "does"], words[:5]
    assert "---" in words and "my-skill" in words, words
    shingles = tokenize(doc)
    assert "--- name my-skill" in shingles, sorted(shingles)[:5]

    # The word list and the shingle set agree on which branch a document takes.
    assert len(normalize("one two")) == 2 and tokenize("one two") == {"one", "two"}
    assert normalize("") == [] and tokenize("") == set()
    # Punctuation alone normalizes to the empty string, so the last-resort branch
    # returns an empty set and the scan would count the file as unindexable.
    assert normalize("!!!!") == [] and tokenize("!!!!") == set()
    # Three words is the smallest document that produces a word shingle.
    assert tokenize("a b c") == {"a b c"}


def answer_tokenization(scan, corpus_root: Path) -> dict:
    """Walk the pinned corpus the way cli.py does and count what the filter removes.

    Returns the candidate count, the files the 100-character filter drops, how
    many of those hold fewer than three tokens, and the token counts of the
    files that were indexed.
    """
    indexed = {(f["marketplace"], f["path"]) for f in scan["file_index"]}
    in_cluster = {(f["marketplace"], f["path"]): f["in_cluster"] for f in scan["file_index"]}
    marketplaces = sorted({f["marketplace"] for f in scan["file_index"]})

    candidates = 0
    dropped = []          # (marketplace, path, chars, tokens, excerpt)
    kept = set()
    smallest = []         # (tokens, chars, marketplace, path) for indexed files
    cjk = pax = 0
    under_ten_cjk_or_pax = under_ten = 0
    backup_skipped = Counter()
    for mp in marketplaces:
        base = corpus_root / mp
        for path in base.rglob("*.md"):
            if path.name != "SKILL.md":
                continue
            # The released tool skips any path containing "backup", before the
            # size test and before tokenization, so these files never reached the
            # archived scan. This line applies the same substring test
            # (RELEASE_BACKUP_RULE) on purpose: its job is to see what the archived
            # scan saw.
            if "backup" in str(path).lower():
                backup_skipped[mp] += 1
                continue
            candidates += 1
            rel = str(path.relative_to(base))
            text = path.read_text(encoding="utf-8", errors="replace")
            if len(text) < 100:
                words = normalize(text)
                dropped.append((mp, rel, len(text), len(words),
                                text.strip().replace("\n", " ")[:60]))
                continue
            kept.add((mp, rel))
            if (mp, rel) in indexed:
                n = len(normalize(text))
                smallest.append((n, len(text), mp, rel))
                if n < LOW_TOKEN:
                    has_cjk = bool(CJK_RE.search(text))
                    is_pax = "PaxHeader" in rel
                    cjk += has_cjk
                    pax += (is_pax and not has_cjk)
                    if n < LOW_TOKEN // 2:
                        under_ten += 1
                        under_ten_cjk_or_pax += (has_cjk or is_pax)
    smallest.sort()

    short = [d for d in dropped if d[3] < 3]
    short.sort(key=lambda d: (d[3], d[2], d[1]))
    low = [s for s in smallest if s[0] < LOW_TOKEN]
    return {
        "low_token": len(low),
        "low_token_clustered": sum(1 for _, _, mp, rel in low if in_cluster[(mp, rel)]),
        "low_cjk": cjk,
        "low_pax": pax,
        "low_other": len(low) - cjk - pax,
        "under_ten": under_ten,
        "under_ten_cjk_or_pax": under_ten_cjk_or_pax,
        "backup_skipped": sum(backup_skipped.values()),
        "backup_by_marketplace": backup_skipped.most_common(),
        "low_examples": low[:5],
        "marketplaces": len(marketplaces),
        "candidates": candidates,
        "indexed": len(indexed),
        "kept": len(kept),
        "kept_not_indexed": sorted(kept - indexed),
        "indexed_not_kept": sorted(indexed - kept),
        "dropped": len(dropped),
        "short": short,
        "short_count": len(short),
        "empty": sum(1 for d in dropped if d[2] == 0),
        "indexed_under_three": sum(1 for t, _, _, _ in smallest if t < 3),
        "min_tokens": smallest[0][0] if smallest else None,
        "min_tokens_file": smallest[0][2:] if smallest else None,
        "smallest": smallest[:MAX_EXAMPLES],
    }


# --------------------------------------------------------------------------
# section 5: the denominators
# --------------------------------------------------------------------------

def slug_recall(file_index, slugs, account, marketplace=CLAWHUB) -> dict:
    """How many of `slugs` are present under `account`, and how many clustered.

    A slug is present if the archived scan indexed a file at
    `<marketplace>/skills/<account>/<slug>/...`; it is clustered if that file
    carries a cluster id.
    """
    present, clustered = set(), set()
    for f in file_index:
        if f["marketplace"] != marketplace:
            continue
        parts = f["path"].split("/")
        if len(parts) < 3 or parts[0] != "skills" or parts[1] != account:
            continue
        present.add(parts[2])
        if f["in_cluster"]:
            clustered.add(parts[2])
    return {
        "slugs": len(slugs),
        "present": len(present & slugs),
        "clustered": len(clustered & slugs),
        "absent": sorted(slugs - present),
        "present_unclustered": sorted((present & slugs) - clustered),
        "unlisted_present": sorted(present - slugs),
    }


def selftest_denominators():
    fi = [
        {"marketplace": CLAWHUB, "path": "skills/a/one/SKILL.md", "in_cluster": True},
        {"marketplace": CLAWHUB, "path": "skills/a/two/SKILL.md", "in_cluster": False},
        {"marketplace": CLAWHUB, "path": "skills/b/three/SKILL.md", "in_cluster": True},
        {"marketplace": "other", "path": "skills/a/four/SKILL.md", "in_cluster": True},
    ]
    got = slug_recall(fi, {"one", "two", "three", "four"}, "a")
    assert got["slugs"] == 4, got
    assert got["present"] == 2, got          # three is under b, four is another marketplace
    assert got["clustered"] == 1, got        # only "one"
    assert got["absent"] == ["four", "three"], got
    assert got["present_unclustered"] == ["two"], got


def resolve_absent(slugs, corpus_root: Path, account=IOC_ACCOUNT, marketplace=CLAWHUB):
    """For each slug the scan did not index, say whether the file is on disk anyway.

    A slug can be missing from the scan for two different reasons, and the
    difference matters: the file was never in the snapshot, or the file is there
    and the walk skipped it. The released tool's walk skips any path containing
    "backup", so a slug whose name carries that substring is present on disk and
    absent from the index. `backup_in_path` applies that substring test on
    purpose, to reproduce the archived scan (RELEASE_BACKUP_RULE).
    """
    out = []
    for slug in sorted(slugs):
        path = corpus_root / marketplace / "skills" / account / slug / "SKILL.md"
        out.append({
            "slug": slug,
            "on_disk": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else None,
            "backup_in_path": "backup" in str(path).lower(),
        })
    return out


def answer_denominators(scan, iocs, corpus_root: Path) -> dict:
    author = iocs["clawhub_authors"][IOC_ACCOUNT]
    with_payload = author["skill_slugs_with_payload"]
    without_payload = author["skill_slugs_without_payload"]
    slugs = set(with_payload) | set(without_payload)
    rec = slug_recall(scan["file_index"], slugs, IOC_ACCOUNT)
    rec["with_payload"] = len(with_payload)
    rec["without_payload"] = len(without_payload)
    rec["total_skills_field"] = author["total_skills"]
    koi = [r for r in iocs["metadata"]["references"] if r.get("source") == "Koi Security"]
    rec["koi_reference_title"] = koi[0]["title"] if koi else None
    rec["koi_reference_count"] = koi[0].get("count") if koi else None
    rec["koi_authors_documented"] = koi[0].get("authors_documented") if koi else None
    rec["koi_slug_list_on_disk"] = False
    rec["clawhub_authors"] = len(iocs["clawhub_authors"])
    rec["absent_detail"] = resolve_absent(rec["absent"], corpus_root)
    rec["unclustered_carries_payload"] = sorted(
        s for s in rec["present_unclustered"] if s in set(with_payload))
    return rec


# --------------------------------------------------------------------------
# section 3: payload-indicator recall for the unclustered files
# --------------------------------------------------------------------------

def indicator_counts(files, marker, weak) -> dict:
    """Files carrying at least one indicator, and those resting on `weak` alone."""
    hits = [f for f in files if marker(f)]
    weak_only = [f for f in hits if set(marker.hits(f)) == {weak}]
    return {"total": len(files), "hits": len(hits), "weak_only": len(weak_only),
            "hit_files": hits, "weak_only_files": weak_only}


def selftest_payload_recall():
    class ToyMarker:
        def __init__(self, table):
            self.table = table

        def hits(self, loc):
            return frozenset(self.table.get(loc["path"], ()))

        def __call__(self, loc):
            return bool(self.hits(loc))

    files = [{"path": "a"}, {"path": "b"}, {"path": "c"}]
    marker = ToyMarker({"a": {"weak"}, "b": {"weak", "real"}})
    got = indicator_counts(files, marker, "weak")
    assert (got["total"], got["hits"], got["weak_only"]) == (3, 2, 1), got
    assert [f["path"] for f in got["hit_files"]] == ["a", "b"], got


def indicator_provenance(iocs) -> dict:
    """Split the marker's indicators into those from iocs.json and those added by hand.

    DESIGN RATIONALE: rather than restate `payload_indicators`, this calls it
    twice with `EXTRA_LITERALS` emptied for the second call. The difference is
    exactly the literals that come from the March working notes, which are not
    part of this artifact, rather than from `payload_infrastructure`, and it
    stays correct if either list changes.
    """
    saved = FLP.EXTRA_LITERALS
    full = FLP.payload_indicators(iocs)
    try:
        FLP.EXTRA_LITERALS = ()
        from_iocs = FLP.payload_indicators(iocs)
    finally:
        FLP.EXTRA_LITERALS = saved
    return {"total": len(full), "from_iocs": len(from_iocs),
            "hand_added": sorted(full - from_iocs)}


def answer_payload_recall(scan, iocs, marker, study) -> dict:
    fi = scan["file_index"]
    unclustered = [f for f in fi if not f["in_cluster"]]
    clustered = [f for f in fi if f["in_cluster"]]

    everything = indicator_counts(unclustered, marker, FLP.WEAK_INDICATOR)
    account_files = [f for f in unclustered if FLP.account_of(f) in study]
    by_account = indicator_counts(account_files, marker, FLP.WEAK_INDICATOR)
    singletons = [f for f in unclustered if FLP.account_of(f) in SINGLETON_ACCOUNTS]
    singleton_rows = []
    for f in sorted(singletons, key=lambda f: (FLP.account_of(f), f["path"])):
        ind = marker.hits(f)
        partners = [g for g in clustered if marker.hits(g) & ind]
        accounts = sorted({FLP.account_of(g) for g in partners if FLP.account_of(g)})
        singleton_rows.append({
            "account": FLP.account_of(f), "path": f["path"],
            "indicators": sorted(ind), "partners": len(partners), "accounts": accounts,
        })

    others = [f for f in everything["hit_files"] if FLP.account_of(f) not in study]
    other_rows = [{"marketplace": f["marketplace"], "path": f["path"],
                   "indicators": sorted(marker.hits(f))}
                  for f in others if set(marker.hits(f)) != {FLP.WEAK_INDICATOR}]
    other_rows.sort(key=lambda r: (r["marketplace"], r["path"]))
    prov = indicator_provenance(iocs)
    hand = set(prov["hand_added"])
    return {
        "indicator_provenance": prov,
        "rows_on_hand_literals": [r for r in other_rows if set(r["indicators"]) <= hand],
        "unclustered": len(unclustered),
        "clustered": len(clustered),
        "clustered_hits": sum(1 for f in clustered if marker(f)),
        "unclustered_hits": everything["hits"],
        "unclustered_weak_only": everything["weak_only"],
        "account_unclustered": by_account["total"],
        "account_unclustered_hits": by_account["hits"],
        "singletons": singleton_rows,
        "other_hits": len(others),
        "other_weak_only": sum(1 for f in others
                               if set(marker.hits(f)) == {FLP.WEAK_INDICATOR}),
        "other_rows": other_rows,
        "unresolved": len(marker.unresolved),
        "indicators": len(marker.indicators),
    }


# --------------------------------------------------------------------------
# section 1: precision by cluster size band
# --------------------------------------------------------------------------

def band_rows(clusters, is_malicious, bands=BANDS) -> list:
    """Cluster-level and file-level precision within each size band.

    A band is closed on both ends, so the bands partition the clusters and the
    rows add up to the all-clusters row. File counts are memberships, that is
    `len(locations)`, which is what the published file-level figures divide by.
    """
    rows = []
    for lo, hi in bands:
        sub = [c for c in clusters if c["size"] >= lo and (hi is None or c["size"] <= hi)]
        tp = pure = mixed = files = mal = 0
        for c in sub:
            n = len(c["locations"])
            k = sum(1 for loc in c["locations"] if is_malicious(loc))
            files += n
            mal += k
            if k:
                tp += 1
                pure += (k == n)
                mixed += (k != n)
        rows.append({
            "lo": lo, "hi": hi, "clusters": len(sub), "tp": tp,
            "cluster_precision": tp / len(sub) if sub else None,
            "files": files, "malicious": mal,
            "file_precision": mal / files if files else None,
            "pure": pure, "mixed": mixed,
        })
    return rows


def selftest_size_bands():
    def cluster(cid, accounts):
        return {"cluster_id": cid, "size": len(accounts), "type": "internal",
                "locations": [{"marketplace": CLAWHUB, "path": f"skills/{a}/s{i}/SKILL.md"}
                              for i, a in enumerate(accounts)]}

    clusters = [
        cluster(1, ["bad", "bad"]),              # size 2, pure
        cluster(2, ["bad", "good"]),             # size 2, mixed
        cluster(3, ["good", "good", "good"]),    # size 3, false positive
        cluster(4, ["bad"] * 10),                # size 10, pure
    ]
    rows = band_rows(clusters, lambda loc: FLP.account_of(loc) == "bad")
    by = {(r["lo"], r["hi"]): r for r in rows}
    two = by[(2, 2)]
    assert (two["clusters"], two["tp"], two["files"], two["malicious"]) == (2, 2, 4, 3), two
    assert (two["pure"], two["mixed"]) == (1, 1), two
    assert by[(3, 4)]["tp"] == 0 and by[(3, 4)]["file_precision"] == 0.0, by[(3, 4)]
    assert by[(5, 9)]["clusters"] == 0 and by[(5, 9)]["file_precision"] is None
    assert by[(10, 19)]["file_precision"] == 1.0, by[(10, 19)]
    # The bands partition: every cluster and every file is counted exactly once.
    assert sum(r["clusters"] for r in rows) == len(clusters)
    assert sum(r["files"] for r in rows) == sum(c["size"] for c in clusters)


def answer_size_bands(scan, is_malicious) -> dict:
    clusters = scan["clusters"]
    rows = band_rows(clusters, is_malicious)
    total_files = sum(len(c["locations"]) for c in clusters)
    total_mal = sum(1 for c in clusters for loc in c["locations"] if is_malicious(loc))
    return {
        "rows": rows,
        "clusters": len(clusters),
        "files": total_files,
        "malicious": total_mal,
        "cluster_tp": sum(r["tp"] for r in rows),
        "banded_clusters": sum(r["clusters"] for r in rows),
        "banded_files": sum(r["files"] for r in rows),
    }


# --------------------------------------------------------------------------
# section 2: benign content inside attributed clusters
# --------------------------------------------------------------------------

def unattributed_rows(clusters, is_malicious, threshold) -> dict:
    """Per-cluster unattributed file counts among the true positives at `threshold`."""
    big = sorted([c for c in clusters if c["size"] >= threshold], key=lambda c: -c["size"])
    rows, tp_files, tp_unattributed = [], 0, 0
    for c in big:
        n = len(c["locations"])
        k = sum(1 for loc in c["locations"] if is_malicious(loc))
        if not k:
            continue
        tp_files += n
        tp_unattributed += n - k
        rows.append({"cluster_id": c["cluster_id"], "size": n, "attributed": k,
                     "unattributed": n - k, "type": c["type"],
                     "marketplaces": c["marketplaces"]})
    return {
        "threshold": threshold,
        "clusters": len(big),
        "tp": len(rows),
        "fp": len(big) - len(rows),
        "files": sum(len(c["locations"]) for c in big),
        "tp_files": tp_files,
        "fp_files": sum(len(c["locations"]) for c in big) - tp_files,
        "unattributed": tp_unattributed,
        "pure": sum(1 for r in rows if r["unattributed"] == 0),
        "mixed": sum(1 for r in rows if r["unattributed"] > 0),
        "rows": rows,
    }


def selftest_benign_inverse():
    def cluster(cid, accounts):
        return {"cluster_id": cid, "size": len(accounts), "type": "internal",
                "marketplaces": [CLAWHUB],
                "locations": [{"marketplace": CLAWHUB, "path": f"skills/{a}/s{i}/SKILL.md"}
                              for i, a in enumerate(accounts)]}

    clusters = [
        cluster(1, ["bad"] * 4),                       # pure TP
        cluster(2, ["bad", "good", "good", "good"]),   # mixed TP, 3 unattributed
        cluster(3, ["good"] * 4),                      # false positive
        cluster(4, ["bad", "bad"]),                    # below threshold
    ]
    got = unattributed_rows(clusters, lambda loc: FLP.account_of(loc) == "bad", 4)
    assert (got["clusters"], got["tp"], got["fp"]) == (3, 2, 1), got
    assert (got["pure"], got["mixed"]) == (1, 1), got
    assert (got["tp_files"], got["unattributed"], got["fp_files"]) == (8, 3, 4), got
    assert [r["cluster_id"] for r in got["rows"]] == [1, 2], got


def answer_benign_inverse(scan, is_malicious) -> dict:
    clusters = scan["clusters"]
    fi = scan["file_index"]
    distinct_clustered = [f for f in fi if f["in_cluster"]]
    return {
        "at20": unattributed_rows(clusters, is_malicious, 20),
        "at10": unattributed_rows(clusters, is_malicious, 10),
        "memberships": sum(len(c["locations"]) for c in clusters),
        "memberships_attributed": sum(1 for c in clusters for loc in c["locations"]
                                      if is_malicious(loc)),
        "distinct": len(distinct_clustered),
        "distinct_attributed": sum(1 for f in distinct_clustered if is_malicious(f)),
        "corpus": len(fi),
    }


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def pct(x, digits=1):
    return f"{100 * x:.{digits}f}%"


def render(prov, tok, den, pay, band, ben, study, antiy) -> list:
    L = []
    a = L.append

    a("# Supplementary data tables")
    a("")
    a(f"Generated {prov['date']}. This file reports five tables computed from material"
      " already in the artifact: the archived scan, the released ground truth, and the"
      " pinned March corpus. No new experiment is involved, and no number here depends on"
      " anything outside those three inputs. Sections 1 and 2 support Table 4 of the paper"
      f" ({paper_ref('Precision and recall at cluster size thresholds')}) and its caption's"
      " statement that only the >= 20 and >= 10 rows reproduce from the released ground"
      f" truth ({paper_ref('rows reproduce from the released ground truth')}). Section 3"
      " supports the paper's account of the singleton blind spot"
      f" ({paper_ref('none of these 7 files landed in any cluster')}). Section 4 supports"
      " the description of the content filter and the tokenizer"
      f" ({paper_ref('minimum of 100 characters of content')};"
      f" {paper_ref('individual words were used as shingles')}). Section 5 supports the"
      f" recall denominators ({paper_ref('of the 352 scanned, 351 appeared in clusters')})"
      " and the abstract's within-archive recall claim"
      f" ({paper_ref('all 337 Koi-documented malicious skills present in the corpus')}).")
    a("")
    a("Sources. `scan_20260314_threshold90_skillonly.json` is the archived 90 percent"
      " Jaccard, `SKILL.md`-only scan that every published number rests on."
      " `paper/iocs.json` is the released ground truth. The pinned March corpus is a"
      " checkout of each repository at the commit SHA recorded in"
      " `paper/supplementary/repository-commits.md`. Numbers below labeled *computed*"
      f" come from `{prov['script']}`, whose provenance table records the inputs and the"
      " command; numbers labeled with a file and a line are quoted from that line; numbers"
      " attributed to the paper carry the section number and the sentence they come from,"
      " so no line number in this file can go stale.")
    a("")
    a("Every `librarian/` line cited below is a line of the **released** tool, the commit"
      " named in the table below, not of any later commit.")
    a("")
    a("| input | value |")
    a("|:--|:--|")
    a(f"| archived scan | `{prov['scan']}` |")
    a(f"| ground truth | `{prov['iocs']}` |")
    a(f"| pinned corpus | `{prov['corpus']}` |")
    a(f"| released tool | `{prov['release']}` |")
    a(f"| repository commit | `{prov['head']}` |")
    a(f"| script | `{prov['script']}` |")
    a(f"| paper quotes | {prov['quotes']} |")
    a(f"| command | `{prov['command']}` |")
    a("")
    a("The command runs with `LIBRARIAN_CORPUS` set to a checkout pinned to the snapshot"
      " the paper used and with `SUPP_TABLES_REDACT_HISTORY=1`, which renders the"
      f" repository commit row as the placeholder above; `{PYTHON_PLACEHOLDER}` is any"
      " Python 3.10 or later interpreter with the repository root importable.")
    a("")

    # ---------------- section 1 ----------------
    a("## 1. Precision by cluster size band")
    a("")
    a("Table 4 of the paper reports cumulative thresholds, which do not separate"
      " sizes 2 through 9: the >= 5 row includes the 11 clusters at >= 20 that"
      " carry most of the signal. The bands below are disjoint, so each row says what an"
      " operator would see if they triaged only clusters of that size.")
    a("")
    a("Attribution rule: a file is malicious if its ClawHub archive path sits under one of"
      f" the {len(study)} documented accounts, the {len(antiy)} from Antiy CERT together"
      " with the accounts `iocs.json` records from payload inspection. This is the `study`"
      " rule of `file_level_precision.py`, and it reproduces the published cluster-level"
      f" figures at >= 20 and >= 10 ({cite(FLP_RESULTS, 88)}, {cite(FLP_RESULTS, 113)}).")
    a("")
    a("| cluster size | clusters | true positives | cluster precision | files | attributed"
      " | file precision | pure | mixed |")
    a("|:--|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in band["rows"]:
        label = f"{r['lo']}" if r["hi"] == r["lo"] else (
            f"{r['lo']}-{r['hi']}" if r["hi"] else f"{r['lo']}+")
        a(f"| {label} | {r['clusters']:,} | {r['tp']} | {pct(r['cluster_precision'])} |"
          f" {r['files']:,} | {r['malicious']} | {pct(r['file_precision'])} |"
          f" {r['pure']} | {r['mixed']} |")
    a(f"| **all** | **{band['clusters']:,}** | **{band['cluster_tp']}** |"
      f" **{pct(band['cluster_tp'] / band['clusters'])}** | **{band['files']:,}** |"
      f" **{band['malicious']}** | **{pct(band['malicious'] / band['files'])}** | | |")
    a("")
    a("Read down the cluster-precision column. At 20 and above every cluster is a true"
      " positive. Between 10 and 19 seven clusters in ten are. Between 5 and 9 fewer than"
      " one in ten is, and at sizes 2 to 4 the rate is one to three per hundred. The"
      " file-level column falls with it. An operator triaging the 2-file clusters would"
      f" work through {band['rows'][0]['clusters']:,} clusters to find"
      f" {band['rows'][0]['tp']}. That is not a viable operating point. Size is doing the"
      " work in this method, and below 10 it stops working.")
    a("")
    a("Two caveats. First, the bands below 10 are exactly the region the caption of"
      " Table 4 disclaims: only the >= 20 and >= 10 rows"
      " reproduce from the released ground truth"
      f" ({paper_ref('rows reproduce from the released ground truth')}). The hand"
      " triage that produced the published >= 5 row (60 of 163) used a payload-inspection"
      " clause whose per-cluster decisions are not part of the artifact, so the 5-9 band"
      " here, credited by account attribution alone, should be read as a lower bound on"
      " what a full triage would allow, not as a restatement of the published row. Second, file"
      " counts are cluster memberships; 86 files sit in more than one cluster, which is why"
      f" the memberships total {band['files']:,} exceeds the {ben['distinct']:,} distinct"
      " clustered files.")
    a("")

    # ---------------- section 2 ----------------
    a("## 2. Benign content inside attributed clusters")
    a("")
    a("Malicious skills cluster. Benign skills cluster too, and the question a registry"
      " faces is how much benign content an automatic quarantine would sweep up with the"
      " malicious. Two readings, both answered from the archived scan.")
    a("")
    a("**Inside the clusters credited as true positives.** These are the clusters a"
      " registry would quarantine at each threshold. The unattributed column is the benign"
      " content that goes with them.")
    a("")
    for key, res in (("at20", ben["at20"]), ("at10", ben["at10"])):
        a(f"At >= {res['threshold']}: {res['tp']} true positives among {res['clusters']}"
          f" clusters, {res['pure']} pure and {res['mixed']} mixed, holding"
          f" {res['tp_files']} files of which {res['unattributed']} are not attributed to"
          f" any documented account"
          f" ({pct(res['unattributed'] / res['tp_files'], 1)} of the quarantine)."
          + (f" A further {res['fp_files']} files sit in the {res['fp']} clusters that are"
             f" false positives outright." if res["fp"] else ""))
        a("")
    a("Per cluster, at >= 10, the mixed ones only:")
    a("")
    a("| cluster | size | attributed | unattributed | type | marketplaces |")
    a("|---:|---:|---:|---:|:--|:--|")
    for row in ben["at10"]["rows"]:
        if row["unattributed"]:
            a(f"| {row['cluster_id']} | {row['size']} | {row['attributed']} |"
              f" {row['unattributed']} | {row['type']} |"
              f" {', '.join(row['marketplaces'])} |")
    a("")
    a("The shape of the answer is that the swept-up benign content is small at >= 20 and"
      " concentrated at >= 10. At >= 20 two files in 307 are unattributed, one in each of"
      " the two mixed clusters. At >= 10 the count is"
      f" {ben['at10']['unattributed']} across {ben['at10']['mixed']} mixed clusters, and it"
      " is dominated by three cross-marketplace clusters (2618, 942, 2392) where an"
      " attacker's file has clustered with legitimate copies of the same skill in community"
      " aggregator repositories. Cluster 942 is the clearest case: 11 files, one attributed,"
      " ten not. This is the source-copy pairing the paper describes as a detection"
      " property, seen from the operator's side, where it is a cost.")
    a("")
    a("**Across all clustered files.** The wider reading is what share of clustering is"
      " malicious at all, and the answer is that almost none of it is.")
    a("")
    a(f"- Clustered memberships: {ben['memberships']:,}, of which"
      f" {ben['memberships_attributed']} are attributed to a documented account"
      f" ({pct(ben['memberships_attributed'] / ben['memberships'], 1)}) (computed).")
    a(f"- Distinct clustered files: {ben['distinct']:,}, of which"
      f" {ben['distinct_attributed']} are attributed"
      f" ({pct(ben['distinct_attributed'] / ben['distinct'], 1)}) (computed).")
    a("")
    a("Roughly nine in ten clustered files are benign duplication, mostly aggregator"
      " repositories republishing the same skill and template scaffolds. Clustering alone"
      " is therefore not a rejection rule, and the paper does not propose it as one. Size is"
      " the discriminator, and the first table in section 1 above shows where it starts to"
      " discriminate. A registry that blocked on cluster membership alone would act on"
      f" {ben['distinct']:,} of {ben['corpus']:,} files,"
      f" {pct(ben['distinct'] / ben['corpus'], 1)} of the corpus, and roughly nine in ten of"
      " those are benign by the attribution rule used here.")
    a("")

    # ---------------- section 3 ----------------
    a("## 3. Payload-indicator recall for unclustered files")
    a("")
    a("Clustering restricted to extracted payload indicators is the natural alternative to"
      " shingle similarity, and the question it raises is whether such a grouping would"
      " have attached the unclustered files from `moonshine-100rze` and `anisafifi` to the"
      " documented campaigns. This section measures that with the indicators the artifact"
      " already carries. The marker is the one from"
      " `paper/sources/scans/file_level_precision.py`, imported rather than copied:"
      f" {pay['indicators']} literal strings, matched case-folded as substrings against the"
      f" file's text in the pinned corpus. {pay['indicator_provenance']['from_iocs']} of them"
      " come from five of the eight `payload_infrastructure` categories in `iocs.json`, and"
      f" {len(pay['indicator_provenance']['hand_added'])} was added by hand from the March"
      " working notes, which are not part of this artifact"
      f" ({', '.join('`' + x + '`' for x in pay['indicator_provenance']['hand_added'])},"
      " `file_level_precision.py` `EXTRA_LITERALS`), so it carries no vendor provenance and"
      " a hit resting on it alone is the weakest evidence in this section.")
    a("")
    a("**The seven singletons.** These are the `moonshine-100rze` and `anisafifi` files"
      f" the paper describes ({paper_ref('none of these 7 files landed in any cluster')})."
      f" All {len(pay['singletons'])} carry a payload indicator,"
      " and every one of them shares at least one indicator with files that did cluster and"
      " that belong to documented accounts.")
    a("")
    a("| account | file | indicators matched | clustered files sharing an indicator |"
      " accounts of those files |")
    a("|:--|:--|:--|---:|:--|")
    for row in pay["singletons"]:
        inds = ", ".join(f"`{i}`" for i in row["indicators"])
        accts = ", ".join(f"`{x}`" for x in row["accounts"][:6])
        if len(row["accounts"]) > 6:
            accts += f", and {len(row['accounts']) - 6} more"
        a(f"| `{row['account']}` | `{row['path']}` | {inds} | {row['partners']} | {accts} |")
    a("")
    a("The result is encouraging, with one qualification. No payload-anchored clustering was"
      " run; what is measured here is that all seven files share at least one indicator with"
      " clustered files belonging to documented accounts. That is the ingredient such a"
      " grouping would use, not the grouping itself, and building it properly means deciding"
      " how to weight an indicator and what counts as a link. The indicators cost nothing to"
      " obtain, since they come from the same vendor reports that supply the ground truth, so"
      " the pairing with behavioral scanning that the paper calls for"
      f" ({paper_ref('motivate pairing it with behavioral scanning')}) looks reachable"
      " rather than proven.")
    a("")
    a("**What payload grep alone would and would not do.** Run over every unclustered file"
      " in the corpus, the marker is far weaker than the clustering it would supplement.")
    a("")
    a(f"The populations are distinct files, not memberships: {pay['unclustered']:,}"
      " unclustered files rather than the released scan's"
      f" `summary.unclustered_files` of {ben['corpus'] - ben['memberships']:,}, which counts"
      f" memberships because {ben['memberships'] - ben['distinct']} files sit in two clusters"
      " each.")
    a("")
    a("| population | files | carrying an indicator |")
    a("|:--|---:|---:|")
    a(f"| unclustered files in the scan | {pay['unclustered']:,} | {pay['unclustered_hits']} |")
    a(f"| of those, under one of the {len(study)} documented accounts |"
      f" {pay['account_unclustered']} | {pay['account_unclustered_hits']} |")
    a(f"| of those, under no documented account | {pay['unclustered'] - pay['account_unclustered']:,}"
      f" | {pay['other_hits']} |")
    a(f"| clustered files in the scan | {pay['clustered']:,} | {pay['clustered_hits']} |")
    a("")
    a(f"Of the {pay['other_hits']} hits under no documented account,"
      f" {pay['other_weak_only']} match on `{FLP.WEAK_INDICATOR}` alone, which `iocs.json`"
      " records as a typosquat with status unknown rather than as a confirmed payload host,"
      f" and should be discounted. That leaves {len(pay['other_rows'])} files that a payload"
      " grep would surface and clustering did not, of which"
      f" {len(pay['rows_on_hand_literals'])} rests on the hand-added literal alone"
      f" ({', '.join('`' + r['path'].rsplit('/', 2)[-2] + '`' for r in pay['rows_on_hand_literals'])}):")
    a("")
    a("| marketplace | path | indicators |")
    a("|:--|:--|:--|")
    for row in pay["other_rows"]:
        a(f"| {row['marketplace']} | `{row['path']}` |"
          f" {', '.join('`' + i + '`' for i in row['indicators'])} |")
    a("")
    a("Most of that list is defensive: skills named `skillvet`, `guava-guard`,"
      " `openclaw-defender`, `skill-security-auditor` and the like, which quote the IOCs"
      " because they scan for them, plus test fixtures under `fixtures/malicious-skill/`."
      " A grep-only pipeline would open every one of them. Two entries are not defensive"
      " and deserve a look: `sundial-awesome-openclaw-skills/skills/bybit-trading/SKILL.md`"
      " and `.../polymarket-traiding-bot/SKILL.md`, which carry the `authtool.zip` and"
      " `aslaep123` infrastructure of the documented AuthTool campaign inside a community"
      " aggregator repository, and which no cluster captured.")
    a("")
    a(f"For contrast, {pay['clustered_hits']} clustered files carry an indicator, against"
      f" {pay['unclustered_hits']} unclustered ones. The marker is not a detector on its"
      " own. It is a linker, and its value in this corpus is that it attaches the singleton"
      " blind spot to campaigns that clustering already found."
      f" Files the marker could not read: {pay['unresolved']}.")
    a("")

    # ---------------- section 4 ----------------
    a("## 4. Filter effects: tokenizer, frontmatter, and the 100-character threshold")
    a("")
    a("Three questions about the front of the pipeline: whether tokenization includes or"
      " excludes the YAML frontmatter, whether the 100-character filter applies before or"
      " after tokenization, and whether an indexed document can be shorter than three"
      " words.")
    a("")
    a("**The tokenizer includes the frontmatter.** Nothing in the pipeline strips it."
      f" `tokenize` ({cite(CORE, 152)} to {cite(CORE, 178)}) lowercases the text, collapses"
      " whitespace, and then removes every character outside `[a-z0-9\\s-]`:")
    a("")
    a("```python")
    a(f"text = text.lower()                              # {cite(CORE, 152).strip('`')}")
    a("text = re.sub(r'\\s+', ' ', text).strip()")
    a("text = re.sub(r'[^a-z0-9\\s\\-]', '', text)")
    a("words = [w for w in text.split() if w]")
    a("```")
    a("")
    a("The comment above that substitution says so directly: \"Markdown files have"
      " frontmatter (key: value), code blocks, headers (#, ##) ... Now we keep dashes"
      f" (important for YAML keys, multi-word terms)\" ({cite(CORE, 156)} to"
      f" {cite(CORE, 158)}). Dashes"
      " survive, so the `---` fence becomes a token of its own; the colon after a YAML key"
      " is stripped, so `name: my-skill` yields the tokens `name` and `my-skill`. A skill"
      " whose frontmatter differs and whose body is identical to another therefore differs"
      " in a handful of shingles, which is the mechanism behind the paper's observation"
      " that exact hashing misses per-skill template variations.")
    a("")
    a("**The filter applies before tokenization, to the decoded text of the whole file.**"
      " The scan reads each candidate file and drops it if the string is shorter than 100"
      f" characters ({cite(CLI, 1485)} to {cite(CLI, 1486)}):")
    a("")
    a("```python")
    a('content = md_file.read_text(encoding="utf-8", errors="replace")')
    a("if len(content) < 100:")
    a("    continue")
    a("```")
    a("")
    a("The unit is characters of decoded text, not bytes and not tokens, and the whole"
      " file including the frontmatter is measured. Tokenization happens later, over the"
      f" files that survived ({cite(CLI, 1514)}).")
    a("")
    a("**So a document in the scan cannot be shorter than three words.** The shingle size"
      f" is 3 ({cite(CORE, 32)}), and `tokenize` carries three fallbacks for documents that"
      " cannot produce a 3-word shingle: individual words when there are one or two"
      f" ({cite(CORE, 165)} to {cite(CORE, 168)}), character trigrams when there are no"
      f" words but at least three characters ({cite(CORE, 171)}), and the text itself as a"
      f" single shingle otherwise ({cite(CORE, 174)}). How often any of them fires on the"
      " corpus that was scanned: never.")
    a("")
    a("- Files in the archived scan with fewer than three tokens after normalization:"
      f" **{tok['indexed_under_three']}** of {tok['indexed']:,} (computed).")
    a(f"- Smallest indexed file by token count: {tok['min_tokens']} tokens"
      f" (`{tok['min_tokens_file'][0]}/{tok['min_tokens_file'][1]}`) (computed).")
    a("")
    a("The filter is what prevents it, though not by construction. The test counts"
      " characters, so a 100-character file of punctuation would still normalize to nothing"
      " and take a fallback branch. No file on this corpus does. Walking the pinned corpus"
      f" the way the scan does, over the same {tok['marketplaces']} marketplaces,"
      f" {tok['candidates']:,} `SKILL.md` files are candidates and **{tok['dropped']}** are"
      f" dropped by the 100-character test. {tok['short_count']} of those {tok['dropped']}"
      f" hold fewer than three tokens, and {tok['empty']} of them are empty files"
      " (computed).")
    a("")
    a(f"What the sub-threshold files contain, {min(MAX_EXAMPLES, tok['short_count'])} of"
      f" the {tok['short_count']}, smallest first:")
    a("")
    a("| marketplace | path | characters | tokens | content |")
    a("|:--|:--|---:|---:|:--|")
    for mp, path, chars, toks, excerpt in tok["short"][:MAX_EXAMPLES]:
        shown = excerpt if excerpt else "(empty file)"
        a(f"| {mp} | `{path}` | {chars} | {toks} | `{shown}` |")
    a("")
    a(f"These are abandoned or placeholder skills. {tok['empty']} are empty files and the"
      " rest hold a word or two of scaffolding such as `test` or `# Test`. They are the"
      " documents that would otherwise reach a fallback branch, and the filter removes all"
      " of them before the tokenizer sees them. The fallback branches in `tokenize` are"
      " therefore dead code on this corpus, and they are dead code for the tool as a whole:"
      " all three call sites that feed `tokenize` apply the same 100-character test first"
      f" ({cite(CLI, 1486)}, {cite(CORE, 235)}, {cite(CORE, 475)}). The branches survive as"
      " defensive code, not because any command reaches them.")
    a("")
    a("**One nuance in the normalization.** It keeps only"
      " `[a-z0-9\\s-]`, so it erases every non-Latin script. In all,"
      f" {tok['low_token']} indexed files reduce to fewer than {LOW_TOKEN} tokens:"
      f" {tok['low_cjk']} contain CJK text, {tok['low_pax']} are `PaxHeader` tar metadata"
      f" that the archive carries alongside real skills, and {tok['low_other']} are short"
      " Latin-script files, a mix of test fixtures and genuinely brief English skills. The"
      f" erasure is what drives the shortest cases: all {tok['under_ten']} files under"
      f" {LOW_TOKEN // 2} tokens are CJK or `PaxHeader`. Of the {tok['low_token']} files,"
      f" {tok['low_token_clustered']} landed in a cluster, grouped on whatever Latin"
      " fragments survived. The smallest is"
      f" `{tok['min_tokens_file'][0]}/{tok['min_tokens_file'][1]}`, 100 characters of"
      f" Chinese instructions that normalize to {tok['min_tokens']} tokens. Nothing in the"
      " paper's results turns on this, since the corpus is overwhelmingly English, but a"
      " registry deploying the method on a multilingual corpus would need a"
      " Unicode-aware tokenizer.")
    a("")
    a("**A second filter sat ahead of the size test.** The walk skipped any path whose"
      " string contained \"backup\", case-folded, before it read the file"
      f" ({cite(*RELEASE_BACKUP_RULE)}), as the paper states"
      f" ({paper_ref('the scanner had skipped any path containing')}). On the pinned"
      " corpus that removes"
      f" {tok['backup_skipped']} `SKILL.md` files from consideration: "
      + ", ".join(f"{n} in `{mp}`" for mp, n in tok["backup_by_marketplace"])
      + ". The rule was written to skip vendored backup directories, and it does that, but"
      " it matched on the whole path, so it also dropped any skill whose own name contains"
      " the word. Section 5 below shows one instance. Of the 864, 780 were that"
      " intended tree in `claude-code-plugins-plus`, 2 were skills whose own directory is"
      " named `backups` or `backup`, and 82 were collateral from the substring match."
      " Narrowing the test to the scan root's own first path component, so that a"
      " marketplace's top-level `backups/` tree is skipped and nothing else is, would"
      " admit 84 more files; the released tool does not do that, and the numbers in this"
      " document are the released tool's.")
    a("")
    if tok["kept_not_indexed"] or tok["indexed_not_kept"]:
        a("One caveat on the replication. The walk over the pinned corpus finds"
          f" {tok['kept']:,} files passing the filter against the archived scan's"
          f" {tok['indexed']:,}. The whole difference is"
          f" {len(tok['kept_not_indexed'])} file present in the pinned corpus and absent"
          f" from the archived scan"
          f" (`{tok['kept_not_indexed'][0][0]}/{tok['kept_not_indexed'][0][1]}`, a"
          " directory the archived scan did not index), with nothing missing in"
          " the other direction. Every file in the archived scan resolves under the pinned"
          " corpus, so the token counts above cover the whole scan.")
        a("")

    # ---------------- section 5 ----------------
    a("## 5. Populations and denominators")
    a("")
    a("The corpus-level populations first, since several of the counts above divide by"
      " different ones.")
    a("")
    a("| population | files |")
    a("|:--|---:|")
    a(f"| files in the archived scan | {ben['corpus']:,} |")
    a(f"| distinct clustered files | {ben['distinct']:,} |")
    a(f"| cluster memberships | {ben['memberships']:,} |")
    a(f"| distinct unclustered files | {pay['unclustered']:,} |")
    a("| unclustered memberships (`summary.unclustered_files`) |"
      f" {ben['corpus'] - ben['memberships']:,} |")
    a("")
    a("The ground-truth denominators next. The paper uses two independent lists, Koi's"
      f" slug list and the `{IOC_ACCOUNT}` slugs recorded in `iocs.json`, and this table"
      " says which number belongs to which.")
    a("")
    a("| number | what it counts | recomputable from the artifact | source |")
    a("|---:|:--|:--|:--|")
    a("| 341 | skill slugs in Koi Security's original ClawHavoc report of 2026-02-01, the"
      " list the paper's headline recall is measured against | **no**, the slug list is"
      " not in the artifact | "
      + paper_ref("Of the 341 skill slugs in Koi Security's original") + "; "
      + paper_ref("We treated the 341 original IOC slugs from the Clawdex database") + " |")
    a("| 337 | of those 341, the slugs that resided in the ClawHub archive | **no**, it"
      " needs the 341 list | "
      + paper_ref("337 resided in the ClawHub archive") + "; " + cite(SWEEP, 23) + " |")
    a(f"| {den['slugs']} | `{IOC_ACCOUNT}` skill slugs recorded in `iocs.json`,"
      f" {den['with_payload']} with a payload and {den['without_payload']} without | yes |"
      " `paper/iocs.json` `clawhub_authors.hightower6eu`; "
      + paper_ref("narrower hightower6eu subset (354 IOC slugs)") + " |")
    a(f"| {den['present']} | of those {den['slugs']}, the slugs the scan indexed. The"
      f" other {den['slugs'] - den['present']} are on disk and were skipped by the walk's"
      f" \"backup\" path rule ({cite(*RELEASE_BACKUP_RULE)}), not missing from the snapshot |"
      " yes | computed; " + paper_ref("of the 352 scanned, 351 appeared in clusters") + " |")
    a(f"| {den['clustered']} | of those {den['present']}, the slugs whose file landed in a"
      " cluster | yes | computed; "
      + paper_ref("of the 352 scanned, 351 appeared in clusters") + " |")
    a("")
    a("**What `iocs.json` does and does not carry.** It carries the Koi reference as"
      f" metadata: the title (\"{den['koi_reference_title']}\"), the URL, the dates, the"
      f" updated count of {den['koi_reference_count']}, and the single account Koi"
      f" documented ({', '.join(den['koi_authors_documented'])}). It does not carry the 341"
      " slugs. The per-skill verdicts sit in Koi's Clawdex database behind a per-skill API"
      f" ({paper_ref('We treated the 341 original IOC slugs from the Clawdex database')}),"
      " so 341 and 337 cannot be recomputed here, and no attempt is made to reconstruct"
      " them. What the file does carry is two account lists, the"
      f" {den['clawhub_authors']} in `clawhub_authors` and the {len(antiy)} Antiy CERT accounts"
      f" in the reference metadata, {len(study)} in union, together with the"
      f" {den['slugs']} `{IOC_ACCOUNT}` slugs, which is the subset the threshold and"
      " shingle experiments use because those experiments were scoped to one author"
      f" ({paper_ref('narrower hightower6eu subset (354 IOC slugs)')}).")
    a("")
    a(f"**The chain from {den['slugs']} to {den['clustered']}.**"
      f" Two of the {den['slugs']} slugs were skipped by the backup-path filter, as the"
      f" paper states ({paper_ref('of the 352 scanned, 351 appeared in clusters')}). Both"
      f" ({', '.join('`' + d['slug'] + '`' for d in den['absent_detail'])}) sit in the"
      " pinned corpus at "
      + " and ".join(f"{d['bytes']:,} bytes" for d in den["absent_detail"])
      + ", and the scan never saw them because the walk's rule"
      f" ({cite(*RELEASE_BACKUP_RULE)}) skipped any path containing \"backup\" and both slug"
      " names do. The same rule removes"
      f" {tok['backup_skipped']} `SKILL.md` files corpus-wide. The paper reports that the"
      f" two, when scanned, cluster only with each other ({paper_ref('cluster only with each other')}); the"
      f" point for the denominator table is that {den['slugs'] - den['present']} of the"
      f" {den['slugs']} left the count through the tool's path filter rather than through"
      f" upstream deletion. Of the {den['present']} the scan did index,"
      f" {den['clustered']} appear in clusters and one does not:"
      f" `{den['present_unclustered'][0]}`. That single unclustered slug is the one entry in"
      " `skill_slugs_without_payload` for this account, so the one file the clusterer"
      " missed is the one file the ground truth records as carrying no payload.")
    a("")
    a("**How each maps to the abstract's within-archive recall claim.** The abstract"
      " reports that all 337 Koi-documented malicious skills present in the corpus"
      " appeared in a cluster"
      f" ({paper_ref('all 337 Koi-documented malicious skills present in the corpus')}),"
      " so its denominator is 337, the within-archive subset of Koi's 341. It is not 341"
      f" (recall against the full list is 337/341 = 98.8%, {cite(SWEEP, 23)}) and it is not"
      f" {den['present']} (the"
      f" `{IOC_ACCOUNT}` subset gives {den['clustered']}/{den['present']} = "
      f"{pct(den['clustered'] / den['present'], 1)} against the slugs the scan indexed, and"
      f" {den['clustered']}/{den['slugs']} = {pct(den['clustered'] / den['slugs'], 1)}"
      f" against the recorded slugs, {cite(SWEEP, 22)}). Three different denominators"
      " produce three different figures, all of them correct for their own list. The"
      " abstract scopes the 100 percent figure as within-archive recall against Koi's"
      " 341-slug list on a single template-reuse campaign class"
      f" ({paper_ref('a within-archive recall expected by construction for template-reuse campaigns')}).")
    a("")

    a("## What is not computed here, and why")
    a("")
    a("- Koi's 341-slug list and the 337 present in the archive. The slug list is not in the"
      " artifact. `iocs.json` carries the Koi reference metadata and the account Koi"
      " documented, and the individual verdicts live behind the Clawdex per-skill API"
      f" ({paper_ref('We treated the 341 original IOC slugs from the Clawdex database')})."
      " Both figures are quoted from the paper, not recomputed.")
    a("- The published >= 15, >= 5 and all-clusters rows of Table 4."
      " Those record the hand triage of Section 4.4, whose per-cluster decisions are not"
      " part of the artifact. The band table above credits the same clusters by account attribution, which"
      " is a different and stricter rule, and it is labeled as such rather than presented as"
      " a reproduction.")
    a("- Anything requiring a new scan, a temporal split, or a paraphrase experiment. Every"
      " number here comes from the archived scan, `iocs.json`, and the pinned corpus.")
    a("")
    return L


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

SELF_TESTS = (
    ("paper_ref", selftest_paper_refs),
    ("answer_tokenization", selftest_tokenization),
    ("answer_denominators", selftest_denominators),
    ("answer_payload_recall", selftest_payload_recall),
    ("answer_size_bands", selftest_size_bands),
    ("answer_benign_inverse", selftest_benign_inverse),
)


def git_head() -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> int:
    for name, test in SELF_TESTS:
        try:
            test()
        except AssertionError as exc:
            print(f"self-test for {name} failed: {exc}", file=sys.stderr)
            return 1
    print(f"self-tests passed ({len(SELF_TESTS)} functions)")

    if CORPUS is None or not CORPUS.is_dir():
        print("LIBRARIAN_CORPUS must name the pinned March corpus; section 4 walks it and"
              " the content marker reads from it, so without it the run would report quiet"
              " zeros", file=sys.stderr)
        return 1
    if FLP.MARKETPLACE_ROOT != CORPUS:
        print(f"file_level_precision resolved its corpus to {FLP.MARKETPLACE_ROOT}, not"
              f" {CORPUS}; the imported content marker would read a different tree",
              file=sys.stderr)
        return 1

    stale = check_citations()
    if stale:
        for path, lineno, literal, note in stale:
            print(f"stale citation {path}:{lineno} for {literal!r}: {note}", file=sys.stderr)
        return 1
    print(f"citations checked ({len(CITATIONS)} line references against"
          f" {RELEASE_COMMIT[:7]})")

    # The paper source is not part of the released artifact, so a reader will not
    # have it. Verify against it when it is here, and otherwise fall back to the
    # declared sections, which render identically. The fallback is announced on
    # stdout and recorded in the output's provenance table, so an unverified run
    # is never silent.
    if PAPER.is_file():
        bad_quotes = check_paper_quotes()
        verified = True
    else:
        bad_quotes = declare_paper_quotes()
        verified = False
        print(f"paper quotes not verified: {PAPER.relative_to(REPO)} not present")
    if bad_quotes:
        for declared, quote, note in bad_quotes:
            print(f"bad paper quote for section {declared}: {quote!r}: {note}",
                  file=sys.stderr)
        return 1
    if verified:
        # Prove the two modes agree rather than asserting it in a comment: the
        # declared sections must reproduce exactly what verification recorded.
        recorded = dict(_PAPER_WHERE)
        _PAPER_WHERE.clear()
        declare_paper_quotes()
        if _PAPER_WHERE != recorded:
            print(f"declared sections disagree with the paper: {recorded} vs"
                  f" {dict(_PAPER_WHERE)}", file=sys.stderr)
            return 1
        print(f"paper quotes checked ({len(PAPER_QUOTES)} section references)")

    scan = json.loads(SCAN.read_text())
    iocs = json.loads(IOCS.read_text())

    antiy_refs = [r for r in iocs["metadata"]["references"] if r.get("source") == "Antiy CERT"]
    if len(antiy_refs) != 1:
        print(f"expected one Antiy CERT reference, found {len(antiy_refs)}", file=sys.stderr)
        return 1
    antiy = set(antiy_refs[0]["authors_documented"])
    study = set(iocs["clawhub_authors"]) | antiy
    is_study = lambda loc: FLP.account_of(loc) in study  # noqa: E731

    marker = FLP.ContentMarker(FLP.payload_indicators(iocs))
    # One complete pass before any short-circuiting caller, so `unresolved` counts
    # every file the marker was asked about rather than only those reached.
    for f in scan["file_index"]:
        marker(f)

    tok = answer_tokenization(scan, CORPUS)
    den = answer_denominators(scan, iocs, CORPUS)
    pay = answer_payload_recall(scan, iocs, marker, study)
    band = answer_size_bands(scan, is_study)
    ben = answer_benign_inverse(scan, is_study)

    # Cross-checks against published figures. A disagreement means the attribution
    # rule here is not the one the results file used, which would invalidate the
    # band and inverse tables.
    checks = [
        ("bands partition the clusters", band["banded_clusters"], band["clusters"]),
        ("bands partition the memberships", band["banded_files"], band["files"]),
        (">= 20 cluster TP", ben["at20"]["tp"], 11),
        (">= 20 files", ben["at20"]["files"], 307),
        (">= 20 attributed", ben["at20"]["files"] - ben["at20"]["unattributed"]
         - ben["at20"]["fp_files"], 305),
        (">= 10 cluster TP", ben["at10"]["tp"], 30),
        (">= 10 files", ben["at10"]["files"], 682),
        (">= 20 pure/mixed", (ben["at20"]["pure"], ben["at20"]["mixed"]), (9, 2)),
        (">= 10 pure/mixed", (ben["at10"]["pure"], ben["at10"]["mixed"]), (23, 7)),
        ("hightower6eu slugs", den["slugs"], 354),
        ("slugs present", den["present"], 352),
        ("slugs clustered", den["clustered"], 351),
        ("distinct clustered files", ben["distinct"], 7061),
        ("corpus size", ben["corpus"], 31634),
    ]
    failed = [(name, got, want) for name, got, want in checks if got != want]
    if failed:
        for name, got, want in failed:
            print(f"cross-check failed: {name}: got {got}, expected {want}", file=sys.stderr)
        return 1
    print(f"cross-checks passed ({len(checks)})")

    prov = {
        "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "script": str(Path(__file__).resolve().relative_to(REPO)),
        "scan": SCAN.name,
        "iocs": str(IOCS.relative_to(REPO)),
        "corpus": CORPUS_PLACEHOLDER,
        "head": HISTORY_PLACEHOLDER if REDACT_HISTORY else git_head(),
        "release": RELEASE_COMMIT,
        "quotes": ("verified against `paper/main-acm.tex`" if verified
                   else "not verified: `paper/main-acm.tex` not present"),
        "command": f"{PYTHON_PLACEHOLDER} {Path(__file__).resolve().relative_to(REPO)}",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(render(prov, tok, den, pay, band, ben, study, antiy)) + "\n")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
