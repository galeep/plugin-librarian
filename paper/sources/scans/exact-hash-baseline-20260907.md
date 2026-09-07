# Exact SHA-256 Deduplication Baseline (Section 5.2 recompute)

Recompute of the Section 5.2 exact-hash baseline, which the paper reports with no script and no
archived result, plus two additional variants. March hand record: `paper/sources/baseline-comparisons.md`.

## Provenance

- Corpus root: `$LIBRARIAN_CORPUS`
- Scan: `scan_20260314_threshold90_skillonly.json`, `generated_at` 2026-03-14T18:10:26.003911+00:00
- Repository HEAD: <private-history>
- Command: `LIBRARIAN_CORPUS=$LIBRARIAN_CORPUS python paper/sources/scans/exact_hash_baseline.py`
- Run at 2026-09-07T03:04:06+00:00, runtime 17.9s
- This file is written before the cross-check against the published figures, so a failing run still
  leaves it on disk: trust the exit status, not the presence of the file. The skip counters in the last
  table are reported, not gated; nothing aborts on a non-zero skip (there are none on this corpus).

| Marketplace | git HEAD |
|---|---|
| `alirezarezvani-claude-skills` | c53f2bc |
| `ananddtyagi-cc-marketplace` | b643305 |
| `anthropic-agent-skills` | b0cbd3d |
| `anthropics-skills` | b0cbd3d |
| `antigravity-awesome-skills` | 663c4464 |
| `cc-marketplace` | b643305 |
| `cc-polymath-marketplace` | baa2df1 |
| `chrome-devtools-plugins` | e6b7a09 |
| `claude-code-plugins-plus` | 3739f136 |
| `claude-code-templates` | 014933f |
| `claude-code-workflows` | a6f0f45 |
| `claude-craftkit` | 5b0115d |
| `claude-forge` | 85b40e5 |
| `claude-plugins-official` | b36fd4b |
| `claude-scientific-skills` | 575f1e5 |
| `clawhub-archive` | 16c991dea17+dirty |
| `competition-scout` | b46d068 |
| `curated` | not a git checkout |
| `daymade-claude-code-skills` | 72c16c2 |
| `every-marketplace` | 1e829ba |
| `geoffjay-claude-plugins` | 0ab5ae1 |
| `gmickel-claude-marketplace` | cb72adc |
| `han` | 6605691 |
| `hashicorp-agent-skills` | 876a095 |
| `leoyeai-openclaw-master-skills` | 43d9a8c |
| `mag-claude-plugins` | 6097ad4 |
| `openskills` | 57d933a |
| `plugins-for-claude-natives` | 7895a58 |
| `side-quest-marketplace` | 7f77d7b |
| `skills-marketplace` | 2482c17 |
| `sundial-awesome-openclaw-skills` | b80cde2 |
| `superpowers-marketplace-resolved` | not a git checkout |

## Definitions

The paper states none of these; they are the rules that reproduce its numbers.

- **Hashed unit.** SHA-256 over the whole file bytes, with no normalisation of line endings, encoding or whitespace.
  Files come from the archived scan's `file_index`, resolved as `$LIBRARIAN_CORPUS/<marketplace>/<path>` exactly as
  `order_permutation.load_files` does; a path that does not resolve is a skip, never refetched from a bare
  `$LIBRARIAN_CORPUS/<path>` fallback.
- **Group.** Two or more files sharing one digest. Singletons are not groups, so "1,946 groups" counts 1,946 digests
  of multiplicity >= 2.
- **Malicious, for the group figure.** A group counts as containing malicious content when at least one of its files
  is attributed by `file_level_precision.account_of` to one of the 18 `study` accounts (iocs.json
  `clawhub_authors` union the 12 Antiy CERT accounts). Narrower sets do not reproduce the paper: the Antiy 12
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
| SKILL.md files hashed | 31634 | 31634 | yes |
| Distinct SHA-256 digests | 28264 | 28264 | yes |
| Duplicate groups (size >= 2) | 1946 | 1946 | yes |
| Files in duplicate groups | 5316 | 5316 | yes |
| Groups with >= 1 study-account file | 71 | 71 | yes |
| ...as a share of all groups | 3.6% | 3.6% | yes |
| Group-level false-positive rate | 96.4% | 96.4% | yes |
| Files from the two primary accounts | 564 | 564 | yes |
| Distinct digests among those files | 75 | 75 | yes |
| Primary-account files in a group | 538 | 538 | yes |
| ...file-level recall | 95.4% | 95.4% | yes |
| Primary-account files missed | 26 | 26 | yes |
| ...as a share of 564 | 4.6% | 4.6% | yes |
| MinHash clusters at >= 20 files | 11 | 11 | yes |

## Variants

`nofm` strips a leading YAML frontmatter block before hashing: the file must open with `---` and a
newline, and the first later line equal to `---` after trailing whitespace closes it; an unterminated
block leaves the file whole. `clawhub` restricts the raw-byte baseline to `clawhub-archive`.

| Variant | Groups | Files in groups | Groups w/ malicious | FP rate | Primary files | In groups | Recall | Missed |
|---|---|---|---|---|---|---|---|---|
| raw | 1946 | 5316 | 71 | 96.4% | 564 | 538 | 95.4% | 26 |
| nofm | 2185 | 5955 | 75 | 96.6% | 564 | 539 | 95.6% | 25 |
| clawhub | 931 | 2655 | 71 | 92.4% | 564 | 538 | 95.4% | 26 |

Stripping the frontmatter moves file recall for the two primary accounts from 538 to
539 of 564: 25 of the 26 raw misses still have no exact duplicate once the header is
removed, and the remaining 1 gains a duplicate partner. Group count rises to 2185 and the
group-level false-positive rate to 96.6%, because bodies shared across differing headers form new groups.

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
| raw | 0 | 0 | 0 | 0 |
| nofm | 0 | 0 | 0 | 59 |
| clawhub | 0 | 0 | 7980 | 0 |
