# Reproduction Steps

Commands that retrieve the corpus snapshot and rerun the published scan,
with the tool commit it ran at. It supports Appendix C (Reproduction) and the
backup-filter description in Section 3.2 (Dataset Construction).

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

The published scan ran with the tool at commit `b55ceff`
(`b55ceff1fde1ef0678a62067d7e0a6cdac852b3e`, the most recent commit to
touch `librarian/`), and that is the filter rule this repository ships.
Under it the scanner skips any path containing `backup` as a substring,
which dropped 864 `SKILL.md` files on this corpus: 780 of them under one
repository's `backups/` tree (`claude-code-plugins-plus/backups/`) and
the other 84 at paths elsewhere in the corpus that contain the
substring. Every count in the paper was produced under this rule, so a
rerun at this commit applies the same exclusions.
