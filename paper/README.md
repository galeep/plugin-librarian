# Artifact: data, scripts and results

This directory holds the released material for "Librarian Catches Thief:
Surfacing Supply Chain Attack Campaigns via Document Similarity in an AI
Agent Skill Registry". The tool itself is the repository this directory
sits in; everything here is the data, the analysis scripts and their
recorded outputs.

This directory sits at the repository root, beside `librarian/`. Run the
scripts from inside a full clone: each locates `paper/iocs.json` and the
`librarian` package by walking up from its own directory, so a script
copied elsewhere will not run. Paths in this file are relative to the
repository root.

`paper/MANIFEST.txt` lists every file with its size and SHA-256 digest,
one file per line as path, bytes, digest, so `shasum -a 256` on any
listed file can be compared directly.

```
paper/iocs.json                    ground truth: flagged publisher accounts, skill slugs (the
                                   directory name a skill is published under), payload indicators
paper/supplementary/               commit table, similarity matrix, scaffold list, reproduction commands
paper/sources/scans/               archived scans, analysis scripts, dated results files
paper/sources/baseline-comparisons.md   Section 5.2 baseline summary
paper/figures/                     figure generators
```

Warning: `paper/iocs.json` and the tables in `paper/supplementary/` reproduce live attacker infrastructure (IP addresses, domains, payload URLs) exactly as the cited vendor reports publish it, undefanged, because the scripts here consume the file as data. Do not visit or resolve any of it.


## Start here

1. From the repository root, in a virtual environment, run `pip install -e .`.
   That installs the `librarian` package, its `librarian` command and
   `datasketch`.
2. Export `LIBRARIAN_CORPUS` pointing at a corpus checkout laid out as the
   *Corpus checkout* section below describes. Several scripts need no corpus at
   all; *Pinning the corpus* names them.
3. Run one of those in its verifying mode:
   `python paper/sources/scans/table1_marketplaces.py --check`. That prints the
   recomputed table and compares it against the shipped
   `paper/sources/scans/table1-marketplaces-20260907.md` without rewriting it,
   exiting non-zero on any difference except the recorded repository HEAD, which
   moves on every commit. Running the script without `--check` overwrites the
   shipped file in place, so there is nothing left to compare it with.

## Artifact claims

One row per paper object, with the claim it carries, the script that produces
it, the file in this directory that records the output, and what that file
records about runtime and inputs. Runtimes are wall time on whichever machine ran the script. `tfidf-comparison-20260907.md` is the only results file that records which machine that was, so treat every runtime here as an order of magnitude, not a target.

| Paper object | Claim | Script | Recorded output | Runtime and inputs |
|---|---|---|---|---|
| Table 1 (Section 3.2) | Corpus composition: `SKILL.md` files per repository after the 100-character minimum | `paper/sources/scans/table1_marketplaces.py` | `paper/sources/scans/table1-marketplaces-20260907.md` | Not recorded; reads the archived scan only, no corpus needed |
| Table 2 (Section 4.1) | Threshold sensitivity: clusters, clustered files and precision at each Jaccard threshold | `paper/sources/scans/table2_distinct_files.py`, `paper/sources/scans/analyze_sweep.py` | `table2-distinct-files-20260907.md`; `threshold-sweep-20260314.md`, which records the stdout of `analyze_sweep.py` | Not recorded; both read the six archived scans and `iocs.json`, no corpus needed |
| Table 3 (Section 4.3) | The campaigns similarity clustering surfaced | `paper/sources/scans/table3_campaigns.py` | `paper/sources/scans/table3-campaigns-20260908.md`; `paper/supplementary/suspicious-scaffold-clusters.md` holds the campaign-consistent clusters that fell short of confirmation and so are absent from this table | Not recorded; reads the archived scan and `paper/iocs.json`, no corpus needed |
| Table 4 (Section 4.4) | Precision and recall at cluster size thresholds; the caption limits reproduction from the released ground truth to the >= 20 and >= 10 rows | `paper/sources/scans/file_level_precision.py`, `paper/sources/scans/table4_triage_record.py` | `file-level-precision-20260907.md`, `table4-triage-record-20260907.md` | Not recorded; `table4_triage_record.py` needs no corpus, and `file_level_precision.py` needs one only for its exploratory content column |
| Table 5 (Section 5.2) | Shingle size ablation at the 90% threshold | `paper/sources/scans/shingle_ablation.py` | `shingle-ablation-20260907.md` | 314.0 s at 2-gram, 396.4 s at 3-gram, 696.3 s at 4-gram; needs the pinned corpus |
| Table 6 (Appendix A) | Attacker accounts documented elsewhere against this study's clustering | none | not regenerated here; the account lists behind it are `paper/iocs.json` | Not applicable; the documentation columns were compiled by hand from the published vendor reports and the clustering column from the archived scan |
| Table 7 (Appendix B) | Behavioral pattern counts over the archived ClawHub snapshot | `paper/sources/scans/behavioral_scan.py` | `behavioral-scan-20260907.md` | 113.3 s; needs the pinned corpus |
| Figure 1 (Section 4.1) | Precision at two cluster sizes against the Jaccard threshold | `paper/figures/generate_figures.py` | No image ships; the plotted series are literals in the script, taken from Table 2, and `threshold-sweep-20260314.md` is where `analyze_sweep.py` recomputes them | Not recorded; needs `matplotlib` and `numpy`, no corpus |
| Figure 2 (Section 4.1) | Cluster size distribution at the 90% threshold | `paper/figures/generate_cluster_distribution.py` | No image ships; the generator reads `scan_20260314_threshold90_skillonly.json` and writes `cluster-distribution.pdf` and `.png` beside itself, identical bytes on two runs | Not recorded; needs `matplotlib` and `numpy`, no corpus |
| Figure 3 (Section 5.2) | Precision and runtime of MinHash, TF-IDF and sentence embeddings | `paper/figures/generate_figures.py` | No image ships; the plotted series are literals in the script, the Section 5.2 values that `paper/sources/baseline-comparisons.md` summarizes and that `tfidf_comparison.py` and `embedding_comparison.py` recompute | Not recorded for the generator, which needs `matplotlib` and `numpy` and no corpus; the two baselines are the rows below |
| Section 3.3 | Seed and order robustness of the clustering | `paper/sources/scans/seed_robustness.py`, `paper/sources/scans/order_permutation.py`, `paper/sources/scans/recompute_ari.py` | `seed-robustness-20260907.md`, `order-permutation-20260907.md`, `recompute-ari-results-20260907.json`, and `reproduction-20260907.md` for the run as a whole | Not recorded; all three need the pinned corpus. `recompute_ari.py` recomputes the Adjusted Rand Index between two clusterings |
| Section 3.1, Dating figures | The temporal statements about the largest ClawHub campaign: first-add instants, the counts per day, and whether the pre-disclosure files would have clustered at the paper's settings | `paper/sources/scans/temporal_receipt.py` | `paper/sources/scans/temporal-receipt-20260908.md`, thirteen claims each with its method, command, computed value and verdict | Not recorded. A full run walks the unshallowed ClawHub mirror, which is not part of this artifact; Software Heritage serves the snapshot the paper cites, and `--mirror` names the checkout. The archived scan is in the bundle. Claims 10 to 12 read the Koi Security report, which is a third party's page: neither it nor any parse of it is part of this artifact, and the reader fetches it from the Wayback Machine at `https://web.archive.org/web/20260306131006id_/https://www.koi.ai/blog/clawhavoc-341-malicious-clawedbot-skills-found-by-the-bot-they-were-targeting` and names the local file with `--koi-capture`; without it those three claims are reported as not run. `--check` verifies the results file instead of rewriting it |
| Sections 3.2, 4.4 and 6 | The backup-path filter and what it excluded from the clustering | `paper/sources/scans/backup_slug_check.py` | `backup-slug-check-20260907.md` | 603 s; needs the pinned corpus |
| Section 3.6 | The artifact and its reproduction commands are described in Appendix C | none | `paper/supplementary/reproduction-steps.md`, with every script in `paper/sources/scans/` and `paper/figures/` and the dated results files beside them | Not recorded; the scan commands need a corpus checkout |
| Section 4.1 | The reported 90% clustering figures come from the archived scan, which a rebuild from the pinned corpus reproduces | `paper/sources/scans/cluster_gap_recompute.py` | `reproduction-20260907.md`, section a; the script reports on stdout and writes no results file | Not recorded; needs the pinned corpus |
| Section 4.2 | Marketplace similarity matrix, including the two mirror pairs | `paper/sources/scans/marketplace_matrix.py` | `paper/supplementary/marketplace-similarity-matrix.md`; the snapshot SHAs behind the mirror pairs are in `paper/supplementary/repository-commits.md` | Not recorded; reads the archived scan only, no corpus needed |
| Section 4.5 | Overlap between behavioral pattern hits and similarity clusters | `paper/sources/scans/rq3_hit_value.py` | `rq3-hit-value-20260907.md` | 67.9 s; needs the pinned corpus |
| Section 5.2, exact-hash baseline | Duplicate groups, group-level false positive rate and hash-based recall | `paper/sources/scans/exact_hash_baseline.py` | `exact-hash-baseline-20260907.md` | 17.9 s; needs the pinned corpus |
| Section 5.2, TF-IDF baseline | Clusters, coverage, precision and runtime for TF-IDF cosine similarity | `paper/sources/scans/tfidf_comparison.py` | `tfidf-comparison-20260907.md` | 1,345.2 s in total, split 305.9 s vectorize, 228.4 s similarity, 810.8 s assignment; needs the pinned corpus |
| Section 5.2, sentence-embedding baseline | The same quantities for sentence embeddings | `paper/sources/scans/embedding_comparison.py` with `embedding_comparison_report.py` | `embedding-comparison-20260907.md` | 802.2 s in total, of which 786.7 s is encoding; needs the pinned corpus and `sentence-transformers` |
| Sections 3.2, 3.3, 4.4 and 5.3, supporting detail | Precision by size band, benign content in attributed clusters, payload-indicator recall, filter effects, and the denominator reconciliation | `paper/sources/scans/supplementary_data_tables.py` | `paper/supplementary/supplementary-data-tables.md` | Not recorded; needs the pinned corpus |
| Section 1 | The scanning tool and the dataset are released as open source | none; the tool is the `librarian/` package in this repository | `paper/sources/scans/scan_20260314_threshold*_skillonly.json`, the six archived scans | Not applicable |
| Appendix C | The artifact holds the tool, the commit table, the similarity matrix, the scaffold-cluster list, the results files behind the figures, and the reproduction commands with the tool commit the scan ran at | none | `librarian/`; `paper/supplementary/repository-commits.md`; `paper/supplementary/marketplace-similarity-matrix.md`; `paper/supplementary/suspicious-scaffold-clusters.md`; the dated results files in `paper/sources/scans/`; `paper/supplementary/reproduction-steps.md` | Not recorded; the scan commands need a corpus checkout |

## The tool commit the published scan ran at

The scan reported in the paper ran with the backup filter as this
repository has it at commit `b55ceff1fde1ef0678a62067d7e0a6cdac852b3e`,
the most recent commit to touch `librarian/`. The released `librarian/`
is that tree, so no checkout is needed to reproduce the scan. The rule
skips any path whose string contains `backup`.

The released code keeps that substring rule. Of the 864 files it
dropped, 780 sit under one repository's `backups/` tree and the other 84
at paths elsewhere in the corpus that contain the substring;
`paper/supplementary/reproduction-steps.md` records that division, and
`paper/supplementary/supplementary-data-tables.md` shows what a rule
narrowed to the scan root's own `backups/` directory would have admitted.
`paper/sources/scans/backup-slug-check-20260907.md` reports what the
substring rule excluded from the clustering and what the exclusion cost.

## Pinning the corpus

Every script that reads file contents takes the corpus root from the
`LIBRARIAN_CORPUS` environment variable, which has no default. Set it to
a checkout pinned to the snapshot the paper used, never to a live clone:
the upstream repositories have changed since the snapshot. A script whose
work needs the corpus exits non-zero with a one-line message when the
variable is unset or names no directory, rather than reporting numbers
computed against a tree other than the pinned one.

### Corpus checkout

`LIBRARIAN_CORPUS` must name a directory holding one sub-directory per
corpus repository, named exactly as `paper/supplementary/repository-commits.md`
names it, each checked out at the commit that table records. The ClawHub
archive is `clawhub-archive/`, at commit `16c991de`.

Scripts address a file as `$LIBRARIAN_CORPUS/<marketplace>/<path>`, where `<path>`
is the file's path inside that repository as the archived scan's
`file_index` records it. In the ClawHub archive that shape is
`clawhub-archive/skills/<account>/<slug>/SKILL.md`.

Provenance rows in the results files give the corpus root as
`$LIBRARIAN_CORPUS`, the command as `python paper/sources/scans/<script>.py`
run from the repository root with `LIBRARIAN_CORPUS` set, and the
repository HEAD as either a commit of this repository or the token
`<private-history>`. A real hash is recorded only when the script runs inside a
checkout whose `origin` remote is this artifact's own public repository, so that
the commit it names is one a reader can resolve; `paper/sources/scans/repo_provenance.py`
is the single place that rule lives. Every other case, a private working
repository included, records `<private-history>`, a redaction standing for a
commit that is not part of this artifact and cannot be resolved from it. The
shipped results files carry the token. The corpus is pinned by
`paper/supplementary/repository-commits.md`, not by any repository HEAD.

The ClawHub archive was cloned on 2026-03-13 at commit `16c991de`. That
upstream repository has since been removed from GitHub, but Software
Heritage preserves the snapshot under the commit identifier
`swh:1:rev:16c991dea171b9f4e785cb2a70dc1ae2ade83396`, whose corpus tree is
`swh:1:dir:0062bcb4b60e717abcccc9ee548f78957bbec93b`, retrievable
through the vault API. `paper/supplementary/reproduction-steps.md` gives the
vault commands. The per-repository SHAs for the community and curated
marketplaces are in `paper/supplementary/repository-commits.md`; check each
sub-clone out at its recorded SHA rather than at whatever its default
branch now points to.

Five scripts read only the archived scan JSON and `iocs.json` and need
no corpus at all: `analyze_sweep.py`, `marketplace_matrix.py`,
`table1_marketplaces.py`, `table2_distinct_files.py` and
`table3_campaigns.py`. `table4_triage_record.py` computes every
figure it reports from the scan and `iocs.json` as well; it imports
`file_level_precision.py` for the attribution rule.
`file_level_precision.py` needs a corpus only for its exploratory
content-marker column; its two account rules read the scan alone. Every
other script needs the pinned corpus, and `behavioral_scan.py` exits
non-zero before writing anything if `LIBRARIAN_CORPUS` is unset or if
the on-disk `SKILL.md` count under the ClawHub archive is not 23,806.

## Populations and denominators

Five counts recur in the paper's recall figures, on four different
denominators. Section 4.4 (IOC Validation) defines each of them, Section 3.4
(Ground Truth and Validation) states where the ground truth comes from, and
the abstract uses the within-archive form. This table says which count is
which and names the file here that carries it.

| Count | What it counts | Where it comes from |
|---|---|---|
| 341 | Skill slugs in the indicator-of-compromise (IOC) list published by Koi Security with its ClawHavoc report, cited in the paper's references. This is the list the headline recall is measured against. | That list is not redistributed here. `iocs.json` records the payload infrastructure and the accounts, not that list. |
| 337 | Of those 341, the ones present in the archive. All 337 appeared in similarity clusters, which is the 100% within-archive recall, and 337/341 = 98.8% against the full list. The other 4 were absent, 3 likely removed before the snapshot and 1 a probable naming discrepancy. | The same external list, not in this artifact. |
| 354 | This study's own enumeration of one account's skills, the narrower hightower6eu subset, used where an experiment is scoped to that single author. | `paper/iocs.json`, `clawhub_authors.hightower6eu`: 353 slugs with a payload and 1 without, and a `total_skills` of 354. |
| 352 | The 354 minus the 2 the scanner's backup-path filter skipped. That filter is the one Section 3.2 describes: it skipped any path containing the string backup, 864 files in all, 780 of them one repository's backup directory. | `paper/sources/scans/backup-slug-check-20260907.md`, which locates both skipped files on disk and measures what the filter cost. |
| 351 | Of the 352 scanned, the ones that appear in a cluster: 99.7% of those scanned, and 99.2% against the full 354. | `paper/sources/scans/shingle-ablation-20260907.md`, where 351/352 = 99.7% is the recall column at every shingle size, cross-checked against the printed table. |

So 99.7% and 99.2% are the same numerator over different denominators, and
98.8% is a different numerator over a third. The two smaller denominators, 341
and 337, rest on an external list this artifact does not carry, so nothing
here recomputes them; the three that this artifact does carry are 354, 352 and
351. All five are reconciled in one place in
`paper/supplementary/supplementary-data-tables.md`, in its own section on
populations and denominators.

Whether the tokenizer reads the YAML frontmatter, and whether the
100-character minimum applies before or after tokenization, are answered in
`paper/supplementary/supplementary-data-tables.md`, in its section on filter
effects, which covers the tokenizer, the frontmatter and the 100-character
threshold.

## Interpreter and packages

Python 3.10 or later (`requires-python` in `pyproject.toml`); the type annotations use `list[Capability]` and
`tuple[Path, str, str] | None` syntax. From the repository root, in a virtual
environment, `pip install -e .` installs the `librarian` package, its
`librarian` command and `datasketch`. That command is the one
`paper/supplementary/reproduction-steps.md` invokes. Add `scikit-learn`,
`matplotlib`, `numpy` and `sentence-transformers` as the table below
requires; none of the four is a dependency of the package.

| Script | Needs beyond the standard library |
|---|---|
| `order_permutation.py`, `seed_robustness.py`, `recompute_ari.py`, `shingle_ablation.py`, `backup_slug_check.py`, `cluster_gap_recompute.py`, `exact_hash_baseline.py`, `temporal_receipt.py` | `datasketch`, plus the `librarian` package, which `pip install -e .` at the repository root provides |
| `tfidf_comparison.py` | `scikit-learn`, plus `datasketch` and the `librarian` package through its import of `order_permutation.py` |
| `embedding_comparison.py`, `embedding_comparison_report.py` | `sentence-transformers` and `torch`, imported lazily inside the run |
| `paper/figures/generate_figures.py`, `paper/figures/generate_cluster_distribution.py` | `matplotlib`, `numpy` |
| `analyze_sweep.py`, `behavioral_scan.py`, `file_level_precision.py`, `marketplace_matrix.py`, `rq3_hit_value.py`, `table1_marketplaces.py`, `table2_distinct_files.py`, `table3_campaigns.py`, `table4_triage_record.py` | standard library only, though several import a sibling script in this directory |
| `repo_provenance.py` | standard library only; a helper module rather than a script, holding the one test that decides whether a results file may record this checkout's commit |
| `supplementary_data_tables.py` | the `librarian` package (imports `librarian.core` for the tokenizer) and `file_level_precision.py` |

`embedding_comparison.py` needs `sentence-transformers`, which brings torch.
The model is `all-MiniLM-L6-v2` at the snapshot recorded in
`paper/sources/scans/embedding-comparison-20260907.md`, whose provenance table also
lists the package versions the published run used. Encoding, normalization and
the cosine similarity are computed in torch throughout, so no NumPy
interoperability is required; any environment with a working
`sentence-transformers` will do.

The corpus-reading scripts that write a results file name it for the
current UTC date (`<name>-<UTC date>.md`), so a rerun on a later day never
overwrites the dated file shipped here; set `SCAN_RESULTS_OUT` to a full
path to direct a rerun somewhere specific. `recompute_ari.py` takes an
`OUT_SUFFIX` instead, and the shipped
`recompute-ari-results-20260907.json` was written with
`OUT_SUFFIX=-20260907`. Six scripts write the shipped file name and
overwrite it in place: `table1_marketplaces.py`, `table2_distinct_files.py`,
`table3_campaigns.py`, `table4_triage_record.py`, `temporal_receipt.py` and
`marketplace_matrix.py`, of which the first five take `--check` to verify the
shipped file instead of rewriting it. `supplementary_data_tables.py` also
writes a fixed name in place, and it needs the pinned corpus rather than the
archived scans alone. `analyze_sweep.py` and
`cluster_gap_recompute.py` report on stdout and write no results file;
`cluster_gap_recompute.py` leaves `sigs.pkl` and `clusterings.pkl`
intermediates in `CLUSTER_GAP_OUT` (default: the current directory),
which are safe to delete.

## Reproducing on Linux

The corpus was checked out on macOS, whose default filesystem is
case-insensitive. Section 6 (Limitations) records 35 case-insensitive path
collisions on macOS, affecting 28 files in the checkout. No script here
measures those two counts, and no file here lists the 28.

A Linux checkout is case-sensitive and will therefore contain those 28
files where the macOS checkout did not. A rerun on Linux will index
slightly more files than the archived scan and will not reproduce it
byte for byte. The archived scan JSONs shipped here are the macOS run
and are the reference for every published number. Compare against them
rather than against a fresh Linux clone.

## The archived scans

Six scans at thresholds 70, 75, 80, 85, 90 and 95 percent back Table 2
and Figure 1. The 90 percent scan is the primary analysis and the input
to most scripts here. Each carries a `file_index` of 31,634 entries with
relative marketplace paths, a `clusters` list, a `filename_index`, and a
`marketplace_index` covering only marketplaces with at least one clustered
file. The six carry no local paths, so a rerun can be diffed against them
directly. The relative paths they do carry name the publishing account for
every ClawHub skill, the `<account>` segment of
`clawhub-archive/skills/<account>/<slug>/SKILL.md`, and 8,919 distinct
accounts appear across the archive. Those account names are the only
personal data in the six files; they carry no other field about a person.
