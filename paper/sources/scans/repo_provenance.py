#!/usr/bin/env python3
"""Whether a results file may record this checkout's commit, and what to record instead.

Every emitter in `paper/sources/scans/` writes a provenance line naming the commit
it ran at. Those files are published, so the commit of a private working repository
must never appear in one. This module holds the single test that decides it and the
single token written when the answer is no.

A real hash is recorded only when the checkout's `origin` remote is the public
repository: the final path segment of `remote.origin.url`, with any `.git` suffix
removed, must equal `plugin-librarian` exactly. Anything else, including a
repository whose name merely begins with that string, records `<private-history>`.
The test is on `origin` rather than on a path so that it travels with a clone
wherever a reader puts it.

Every failure to answer the question is treated as "not the public repository":
no git binary, a timeout, a directory that is not a checkout, no `origin` remote.
The published token is the safe answer, so the fallback is the redaction.

Standard library only, and read-only against the checkout it inspects, so the
scripts the README lists as needing nothing but a Python interpreter can import it.

Self-test: `self_test()` runs at import and covers the three cases below. Run it
on its own with
  python paper/sources/scans/repo_provenance.py [--self-test]
"""
import os
import subprocess
import sys
from pathlib import Path

PUBLIC_REPO = "plugin-librarian"
PRIVATE_HISTORY = "<private-history>"

# Indirected so the self-test can point it at a name that does not exist and
# exercise the missing-binary path through subprocess itself.
GIT = "git"


def _git(d, *args):
    """stdout of a read-only git command in `d`, or None on any failure.

    GIT_OPTIONAL_LOCKS=0 stops `status` refreshing (and so rewriting) the index,
    which keeps this strictly read-only against a tree another job may be reading.
    """
    try:
        r = subprocess.run([GIT, "-C", str(d), *args], capture_output=True, text=True,
                           timeout=30, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def origin_is_public(url) -> bool:
    """True when `url` names the public repository. Pure, so the rule is testable."""
    if not url:
        return False
    name = url.strip().rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name == PUBLIC_REPO


def is_public_repo(d) -> bool:
    """True when `d` sits in a checkout whose `origin` is the public repository."""
    return origin_is_public(_git(d, "config", "--get", "remote.origin.url"))


def public_repo_head(d) -> str:
    """Short HEAD of `d` with a `+dirty` marker, or the redaction token.

    A dirty worktree means the commit alone does not identify the bytes that were
    read, so the marker is part of the answer rather than a footnote to it.
    """
    if not is_public_repo(d):
        return PRIVATE_HISTORY
    head = _git(d, "rev-parse", "--short", "HEAD")
    if head is None:
        return "unknown"
    dirty = _git(d, "status", "--porcelain")
    if dirty is None:
        return f"{head}+status unknown"
    return f"{head}+dirty" if dirty else head


def self_test():
    """Three cases: the public origin, a non-matching origin, and no git binary."""
    results = []

    public = ["https://github.com/galeep/plugin-librarian",
              "https://github.com/galeep/plugin-librarian.git",
              "git@github.com:galeep/plugin-librarian.git",
              "/srv/mirrors/plugin-librarian/"]
    for url in public:
        if not origin_is_public(url):
            raise AssertionError(f"repo_provenance self-test: {url} should be the public repository")
    results.append(f"public origin accepted for {len(public)} URL forms")

    private = ["https://github.com/example/plugin-librarian-fork",
               "https://github.com/example/plugin-librarian-fork.git",
               "https://github.com/galeep/librarian", "", None]
    for url in private:
        if origin_is_public(url):
            raise AssertionError(f"repo_provenance self-test: {url!r} should not be the public repository")
    results.append(f"non-matching origin refused for {len(private)} URL forms")

    global GIT
    saved, GIT = GIT, "git-binary-that-does-not-exist"
    try:
        if _git(Path(__file__).parent, "rev-parse", "HEAD") is not None:
            raise AssertionError("repo_provenance self-test: a missing git binary returned output")
        if is_public_repo(Path(__file__).parent):
            raise AssertionError("repo_provenance self-test: a missing git binary reported a public repo")
        if public_repo_head(Path(__file__).parent) != PRIVATE_HISTORY:
            raise AssertionError("repo_provenance self-test: a missing git binary did not redact")
    finally:
        GIT = saved
    results.append("missing git binary redacts rather than raising")
    return results


self_test()


USAGE = "usage: python paper/sources/scans/repo_provenance.py [--self-test]"

if __name__ == "__main__":
    if sys.argv[1:] not in ([], ["--self-test"]):
        print(USAGE, file=sys.stderr)
        sys.exit(2)
    for line in self_test():
        print(f"self-test PASS: {line}")
    here = Path(__file__).resolve().parents[3]
    print(f"this checkout records: {public_repo_head(here)}")
    sys.exit(0)
