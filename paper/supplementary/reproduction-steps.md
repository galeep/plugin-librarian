# Reproduction Steps

The primary analysis ran on the ClawHub archive snapshot cloned on
2026-03-13 at commit `16c991de` (full SHA
`16c991dea171b9f4e785cb2a70dc1ae2ade83396`). The upstream
`openclaw/skills` repository has since been removed from GitHub; the
exact snapshot is preserved by Software Heritage under the revision
identifier `swh:1:rev:16c991dea171b9f4e785cb2a70dc1ae2ade83396`, whose
corpus tree is `swh:1:dir:0062bcb4b60e717abcccc9ee548f78957bbec93b`,
and is retrievable through the Software Heritage vault API. The
per-repository commit SHAs for the community marketplaces are in
`repository-commits.md`.

```bash
D=swh:1:dir:0062bcb4b60e717abcccc9ee548f78957bbec93b
V=https://archive.softwareheritage.org/api/1/vault/flat
curl -X POST $V/$D/   # request cooking
# poll $V/$D/ until "status": "done"
curl -L -o skills.tar.gz $V/$D/raw/
mkdir skills
tar xzf skills.tar.gz -C skills --strip-components=1
librarian scan --dir ./skills --threshold 0.9 --skill-only
librarian stats
```

The scan reported in the paper ran with the backup filter as this
repository has it at commit `b55ceff`
(`b55ceff1fde1ef0678a62067d7e0a6cdac852b3e`, the most recent commit to
touch `librarian/`). Under that rule the scanner skips any path
containing `backup` as a substring, which dropped 864 `SKILL.md` files on
this corpus. A later fix, not released here, skips only a top-level
`backup` or `backups` directory of the scan root; under it a rerun indexes
84 more files than the published scan, and the remaining 780 stay skipped,
all of them under one repository's `backups/` tree
(`claude-code-plugins-plus/backups/`). No published count changes.
