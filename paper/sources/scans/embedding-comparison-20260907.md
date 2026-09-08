# Sentence-embedding baseline (Section 5.2 recompute)

This file reports a recompute of the sentence-embedding baseline that Section 5.2
(Comparison with Simple Baselines) sets beside MinHash and TF-IDF, and that Figure 3
plots. Section 5.2 gives the model, the encoded population, the embedding width, the
per-file truncation and the 0.9 cosine threshold, then reports the cluster count,
coverage, recall, precision at the >= 20 and >= 10 cluster sizes, and a wall-clock
runtime split between encoding and clustering. Every one of those figures is set beside
its recompute below. The run reads the archived scan's `file_index` against
the pinned corpus snapshot and writes every recomputed figure beside the published one.

## Provenance

| Item | Value |
|---|---|
| Python | 3.12.11 |
| sentence-transformers | 5.1.2 |
| torch | 2.2.2 |
| scikit-learn | 1.7.2 |
| numpy | 2.3.4 |
| datasketch | not required by this script |
| Model | `all-MiniLM-L6-v2`, 384-dimensional |
| Model snapshot | `c9745ed1d9f207416be6d2e6f8de32d1f16199bf` |
| `HF_HUB_OFFLINE` | `1` |
| Decode mode | `--decode strict` |
| Corpus root | `$LIBRARIAN_CORPUS` |
| Scan | `scan_20260314_threshold90_skillonly.json`, `generated_at` 2026-03-14T18:10:26.003911+00:00 |
| Ground truth | `paper/iocs.json`, `clawhub_authors` (11 accounts) |
| Repository HEAD | `<private-history>` |
| Run at | 2026-09-07T06:01:24+00:00 |

The package versions in the table are the ones this run used, and the published figures
reproduce under them. No lock file pins them, so a rerun records its own.

Command, as run, with LIBRARIAN_CORPUS set. Every non-default flag is interpolated from
the run itself, so copying this block out and running it reproduces the numbers below
rather than the script's defaults:

```
HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
  python \
  paper/sources/scans/embedding_comparison.py \
  --decode strict
```

| Runtime split | Seconds |
|---|---:|
| Model load | 0.3 |
| Corpus read | 11.2 |
| Encode | 786.7 |
| Cosine similarity (batched matmul) | 1.8 |
| Greedy clustering | 2.1 |
| **Total** | **802.2** |

The paper reports one 924 s figure split 805 s encode / 119 s cluster. Its clustering figure
covers similarity and clustering together, so compare it against the sum of the last two
rows (4.0 s). Runtimes here are not comparable to the published figures: wall time depends on the machine and its load.

Snapshot the numbers above and below were computed from. Compare against
`paper/supplementary/repository-commits.md`. Listed here are the 32 marketplaces that
contribute at least one file to the scan's `file_index`; corpus directories with no indexed file
are not read by this script and so are not pinned by it.

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

| Files in index | Loaded | Missing | Unreadable | Undecodable | Under 100 chars |
|---:|---:|---:|---:|---:|---:|
| 31,634 | 31,626 | 0 | 0 | 8 | 0 |

`--decode strict` dropped these 8 files, which are not valid UTF-8:

- `clawhub-archive/skills/2663629531/meme-risk-radar-skill/PaxHeader/SKILL.md`
- `clawhub-archive/skills/eyedark/android-remote-control/SKILL.md`
- `clawhub-archive/skills/shahbaz02197ali-cmd/social-media-lead-generation/SKILL.md`
- `clawhub-archive/skills/theshadowrose/prompt-git/SKILL.md`
- `clawhub-archive/skills/toniaczlog/voice-notes-pro/SKILL.md`
- `clawhub-archive/skills/ultranumblol/memeanalyzer/PaxHeader/SKILL.md`
- `clawhub-archive/skills/ultranumblol/pumpfun-sniper/PaxHeader/SKILL.md`
- `clawhub-archive/skills/ultranumblol/wallet-pnl/PaxHeader/SKILL.md`

## Rules

Section 5.2 gives the model, the population of files that decode as UTF-8 (31,626 of
31,634), the 2,048-character truncation, the 0.9 cosine threshold and the greedy
first-match rule. The remaining rules are stated here in full.

- **Encoded unit.** The first 2048 characters of each file, decoded as UTF-8 with
  `errors="strict"`, encoded by `all-MiniLM-L6-v2` on CPU in batches of 64. Files under
  100 characters are skipped (0 here).
- **Decoding.** Eight indexed files are not valid UTF-8. `--decode strict` skips them, which
  gives the population Section 5.2 states, and names the files it drops; `--decode replace`
  (the script default) substitutes U+FFFD and encodes everything the index names. The two
  give different document counts, so the mode is in the provenance table above.
- **File list.** The archived scan's `file_index`, resolved as `$LIBRARIAN_CORPUS/<marketplace>/<path>`,
  mirroring `order_permutation.load_files`. A bare `$LIBRARIAN_CORPUS/<path>` fallback is not used, so a
  path that does not resolve is a skip.
- **Similarity.** Cosine, computed as a matmul of L2-normalized embeddings, in row batches of
  1000, entirely in torch. Values reach Python only through `.tolist()`, so no array
  crosses between torch and NumPy at any point.
- **Clustering.** The same greedy first-match rule as the MinHash pipeline: walk files in index
  order; skip one already assigned; collect every other still-unassigned file at or above
  0.9; emit the cluster if non-empty and mark all of it assigned. A file matching nothing
  stays unclustered and no cluster is revisited. The implementation finds the matching indices by
  thresholding the row in torch instead of scanning `range(n)` in Python; the startup self-test
  proves the two agree, including across a batch boundary.
- **Attribution.** `clawhub-archive` files whose path begins `skills/` with at least three
  segments are attributed to the second segment. This is one segment looser than
  `file_level_precision.account_of` (which requires four), and is kept because it is the rule the
  published figures used.
- **Malicious.** The 11 accounts in `iocs.json` `clawhub_authors`, which is the
  single source for the set, so no second copy can disagree with it.
- **Precision at size s.** Of clusters holding at least s files, the share holding at least one
  file attributed to one of those accounts. Cluster-level, not file-level.
- **Recall.** Of the hightower6eu files in the loaded corpus (352), the share landing in any
  cluster (351).

## Comparison with the published values

| Quantity | Paper | Recomputed | Match |
|---|---:|---:|:--:|
| Clusters | 3,626 | 3,626 | yes |
| Files in clusters (memberships) | 9,462 | 9,462 | yes |
| Distinct files in clusters | n/a | 9,462 | n/a |
| ...as a share of the corpus | 29.9% | 29.9% | yes |
| Recall (hightower6eu) | 99.7% | 99.7% | yes |
| P@>=20 (13/14 published; 13/14 here) | 92.9% | 92.9% | yes |
| P@>=10 (27/43 published; 27/43 here) | 62.8% | 62.8% | yes |
| Runtime, wall | 924s | 802s | n/a |
| ...encoding | 805s | 787s | n/a |
| ...similarity + clustering | 119s | 4s | n/a |

Runtime rows carry no verdict: wall time depends on the machine and its load, so a
wall-clock disagreement says nothing about the method. The similarity + clustering figure is also
not like-for-like, because the greedy loop here finds its matching indices by thresholding the row
in torch rather than scanning `range(n)` in Python.

## Where the recompute differs, and why

Every published cell reproduces exactly, so there is no difference to explain.

## Decode mode

The eight undecodable files above are the whole difference between the two decode modes. One
full run per mode on this corpus, both deterministic. Only one mode runs at a time, so the last
column says which row this run measured and which is quoted from a previous one:

| `--decode` | Documents encoded | Clusters | Files in clusters | Source |
|---|---:|---:|---:|---|
| `strict` (the population the paper states) | 31,626 | 3,626 | 9,462 | **this run**, cross-checked against the recorded value: match |
| `replace` (the script default) | 31,634 | 3,627 | 9,466 | recorded from a prior run; not executed here |
| Section 5.2 as published | not stated | 3,626 | 9,462 | the paper |

The row for `strict` is not a literal: this run measured 31,626 documents,
3,626 clusters and 9,462 files in clusters, and the
script compares that triple against its recorded `DECODE_OBSERVED` entry before writing this
file. The two agree. The other mode's row cannot be checked by a run that did
not execute it, and is marked accordingly.

`strict` matches the published figures exactly; `replace` differs by +1 cluster and +4 files,
because the eight documents outside the stated population are encoded and four of them find a
partner at 0.9. The same eight files separate the TF-IDF baseline's document count from the full
index, so one decode decision shows up in both baselines rather than two independent
discrepancies.

`strict` is the mode that reproduces Section 5.2. `replace` is kept so a reader can measure
what the eight files add, and this file names its mode in the provenance table so the two
cannot be confused.

The 9,462-file cell (29.9%) can be read as cluster memberships or as distinct files. Here
memberships are 9,462 and distinct files 9,462; the greedy rule
only ever assigns an unassigned file, so the two coincide by construction, and the published
figure is a membership count under a rule that makes it also a file count. (The MinHash side of
the same sentence differs: the archived scan's 7,147 is a membership count over 7,061 distinct
files, because MinHash clusters overlap; the caption of Table 2 says the same, memberships
running higher than files at the 90% threshold.)

## Precision by cluster size

| Size threshold | Clusters | With >= 1 malicious file | Precision |
|---|---:|---:|---:|
| >= 5 | 190 | 35 | 18.4% |
| >= 10 | 43 | 27 | 62.8% |
| >= 15 | 23 | 20 | 87.0% |
| >= 20 | 14 | 13 | 92.9% |

## MinHash comparison row

Recomputed from the archived scan under the same precision and recall rules as the embedding
row, not quoted from a stored literal. datasketch is not needed for this.

| Method | Clusters | Memberships | Distinct | Rate | Recall | P@>=20 | P@>=10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Embeddings (all-MiniLM-L6-v2) | 3,626 | 9,462 | 9,462 | 29.9% | 99.7% | 92.9% (13/14) | 62.8% (27/43) |
| MinHash (archived scan) | 2,622 | 7,147 | 7,061 | 22.6% | 99.7% (351/352) | 100.0% (11/11) | 78.9% (30/38) |
| MinHash, as the paper prints it | 2,622 | 7,147 | n/a | 22.6% | 99.2% | 100.0% | 78.9% |

Every MinHash cell recomputes except the recall cell of the printed row: it says 99.2%,
and the archived scan under this script's own recall rule gives 99.7%
(351/352).

Both figures are the paper's, and Section 4.4 (IOC Validation) states how they relate: of
the 352 scanned, 351 appeared in clusters, which is 99.7% of those scanned and 99.2%
against the full 354. The 354-denominator form is the one Section 3.3 (Similarity Analysis)
uses for recall across the six thresholds, the one the captions of Table 2 and Figure 1
carry, and the one Section 5.2 gives where it leaves recall out of Figure 3 because all three
methods reach near-identical values. The 352-denominator form,
99.7% (351/352), is the one Table 5 prints for the 3-gram MinHash row.

This script counts recall over the hightower6eu files the loaded corpus holds
(352), for the embedding row and the MinHash row alike, so its recomputed MinHash
row reads 99.7% beside the printed 99.2%. The two are the same 351
files over different denominators, and the table above carries the recomputed row beside the
printed one so that both denominators are visible.

