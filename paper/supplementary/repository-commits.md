# Repository Commit SHAs

This file records the commit at which each repository of the corpus was
cloned and the date of that clone. It is the commit table the paper
refers to in Appendix C (Reproduction):

> "The ClawHub archive was cloned on 2026-03-13 at commit `16c991de`, and
> the community and curated repositories between 2026-01-02 and
> 2026-03-13."

It also supports the mirror-pair sentence of Section 4.2 (Marketplace
Similarity Matrix):

> "Each is one upstream repository cloned into the corpus under two
> names, as the artifact's commit table records (Appendix C)."

Every repository was cloned with `git clone --depth 1`. The commit SHA
of each clone is given in full for the ClawHub archive and abbreviated
for the others. Table 1 of the paper (Section 3.2, Dataset
Construction) gives `SKILL.md` file counts by repository after the
100-character minimum filter; this file gives the commits. Rebuilding
the corpus means checking out each repository at the commit listed
here; `reproduction-steps.md` in this directory gives the retrieval and
scan commands for the ClawHub archive.

## Primary Archive

| Repository | Commit SHA | Date |
|------------|-----------|------|
| clawhub-archive | 16c991dea171b9f4e785cb2a70dc1ae2ade83396 | 2026-03-13 |

The upstream `openclaw/skills` repository has since been removed from
GitHub (it was absent by 2026-07-11). Software Heritage preserves the
exact snapshot listed above and serves it publicly:

- Revision: `swh:1:rev:16c991dea171b9f4e785cb2a70dc1ae2ade83396`
- Corpus tree: `swh:1:dir:0062bcb4b60e717abcccc9ee548f78957bbec93b`
- Browse: <https://archive.softwareheritage.org/swh:1:rev:16c991dea171b9f4e785cb2a70dc1ae2ade83396>
- Retrieval: Software Heritage vault API
  (`/api/1/vault/flat/swh:1:dir:0062bcb4b60e717abcccc9ee548f78957bbec93b/`);
  `reproduction-steps.md` gives the `curl` sequence, and Appendix C of
  the paper cites the snapshot.

## Community Marketplace Repositories

| Repository | Commit SHA | Date |
|------------|-----------|------|
| alirezarezvani-claude-skills | c53f2bcb | 2026-03-13 |
| ananddtyagi-cc-marketplace | b6433051 | 2026-01-18 |
| anthropic-agent-skills | b0cbd3df | 2026-03-06 |
| anthropics-skills | b0cbd3df | 2026-03-06 |
| antigravity-awesome-skills | 663c4464 | 2026-03-12 |
| awesome-agent-skills | 9f1edf3d | 2026-03-12 |
| cc-marketplace | b6433051 | 2026-01-18 |
| cc-polymath-marketplace | baa2df11 | 2026-02-28 |
| chrome-devtools-plugins | e6b7a09e | 2026-03-12 |
| claude-code-plugins-plus | 3739f136 | 2026-03-12 |
| claude-code-templates | 014933fb | 2026-03-12 |
| claude-code-workflows | a6f0f457 | 2026-03-07 |
| claude-craftkit | 5b0115d3 | 2026-02-03 |
| claude-forge | 85b40e51 | 2026-03-06 |
| claude-hud | c02787bf | 2026-03-09 |
| claude-plugins-official | b36fd4b7 | 2026-03-11 |
| claude-scientific-skills | 575f1e58 | 2026-03-11 |
| competition-scout | b46d068b | 2025-12-10 |
| criticalthink | 049ea25e | 2025-10-11 |
| daymade-claude-code-skills | 72c16c2b | 2026-03-11 |
| every-marketplace | 1e829ba4 | 2026-03-11 |
| geoffjay-claude-plugins | 0ab5ae1b | 2025-11-04 |
| gmickel-claude-marketplace | cb72adc1 | 2026-03-06 |
| han | 66056915 | 2026-03-10 |
| hashicorp-agent-skills | 876a095c | 2026-03-04 |
| leoyeai-openclaw-master-skills | 43d9a8c7 | 2026-03-12 |
| mag-claude-plugins | 6097ad46 | 2026-02-16 |
| openskills | 57d933a4 | 2026-01-18 |
| plugins-for-claude-natives | 7895a585 | 2026-03-12 |
| side-quest-marketplace | 7f77d7b2 | 2026-03-08 |
| skills-marketplace | 2482c176 | 2026-01-13 |
| sundial-awesome-openclaw-skills | b80cde2e | 2026-03-06 |
| superpowers-marketplace | 646f1d92 | 2026-03-11 |
| taskmaster | 2d1211bf | 2026-02-04 |

## Curated Sub-Repositories

These repositories are nested inside the corpus directory `curated/`,
each an individually cloned repository. Table 1 of the paper counts
their files under the single row `curated`.

| Repository | Commit SHA | Date |
|------------|-----------|------|
| curated/ai-marketing-skills | 3c48080f | 2026-03-08 |
| curated/ai-research-skills-orchestra | 0ae58722 | 2026-03-05 |
| curated/aws-skills | fea94551 | 2026-03-06 |
| curated/beautiful-prose | bf44efb7 | 2025-12-30 |
| curated/clarity-gate | 88eaf21b | 2026-03-02 |
| curated/claude-bootstrap | 2ce2c15d | 2026-02-14 |
| curated/claude-seo | 162584a8 | 2026-03-12 |
| curated/clawsec | 277c0abe | 2026-03-12 |
| curated/creative-director | 1609cef5 | 2026-02-27 |
| curated/data-structure-protocol | ad9b1034 | 2026-02-20 |
| curated/eval-skills | febdb335 | 2026-03-03 |
| curated/humanizer | d8085c7d | 2026-02-20 |
| curated/marketingskills | 2f5db8d9 | 2026-03-04 |
| curated/openai-skills | ecc1fb8b | 2026-03-11 |
| curated/pm-product-manager-skills | 0dae9250 | 2026-03-09 |
| curated/pm-skills-huryn | 36ccefd | 2026-03-09 |
| curated/recursive-decomposition | 1780d46a | 2026-01-25 |
| curated/rootly-incident-responder | b418a908 | 2026-03-12 |
| curated/security-bluebook | bbf77219 | 2025-12-24 |
| curated/skill-seekers | 0ca271cd | 2026-03-02 |
| curated/superpowers | 363923f7 | 2026-03-11 |
| curated/terraform-skill | 5a68694c | 2026-02-02 |
| curated/trailofbits-skills | c6097699 | 2026-03-03 |
| curated/write-concisely | 554814cf | 2026-02-24 |

## Notes

- `anthropics-skills` and `anthropic-agent-skills` share the commit
  SHA b0cbd3df1533b396d281a6886d5132f623393a9c: one upstream
  repository cloned into the corpus under two directory names. Both
  clone names are listed above against that SHA, so the 1.000 pair in
  `marketplace-similarity-matrix.md` can be checked against this
  table.
- `cc-marketplace` and `ananddtyagi-cc-marketplace` are the same
  repository, sharing the commit SHA
  b643305146890bda9b2e694d2c42206ae4d0a4df, and both clone names are
  listed above for the same reason.
- Three community repositories predate the ClawHub ecosystem
  (competition-scout, criticalthink, geoffjay-claude-plugins) and
  contribute few or no `SKILL.md` files.
