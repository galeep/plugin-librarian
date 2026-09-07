# Supplementary data tables

Generated 2026-09-07. Five tables computed from material already in the artifact: the archived scan, the released ground truth, and the pinned March corpus. No new experiment is involved, and no number here depends on anything outside those three inputs.

Sources. `scan_20260314_threshold90_skillonly.json` is the archived 90 percent Jaccard, `SKILL.md`-only scan that every published number rests on. `paper/iocs.json` is the released ground truth. The pinned March corpus is the reconstruction of the snapshot from the commit SHAs in `paper/supplementary/repository-commits.md`. Numbers below labeled *computed* come from `paper/sources/scans/supplementary_data_tables.py`, whose provenance table records the inputs and the command; numbers labeled with a file and a line are quoted from that line; numbers attributed to the paper carry the section number and the sentence they come from, so no line number in this file can go stale.

Every `librarian/` line cited below is a line of the **released** tool, the commit named in the table above, not of whatever tree this file was generated in. The later change to the backup-path filter is not in that revision, so this file describes its effect without citing a line for it.

| input | value |
|:--|:--|
| archived scan | `scan_20260314_threshold90_skillonly.json` |
| ground truth | `paper/iocs.json` |
| pinned corpus | `$LIBRARIAN_CORPUS` |
| released tool | `b55ceff1fde1ef0678a62067d7e0a6cdac852b3e` |
| repository commit | `<private-history>` |
| script | `paper/sources/scans/supplementary_data_tables.py` |
| paper quotes | not verified: `paper/main-acm.tex` not present |
| command | `LIBRARIAN_CORPUS=$LIBRARIAN_CORPUS python paper/sources/scans/supplementary_data_tables.py` |

`LIBRARIAN_CORPUS` names a checkout pinned to the snapshot the paper used; `python` is any Python 3.10 or later interpreter with the repository root importable.

## 1. Precision by cluster size band

The published precision table reports cumulative thresholds, which hides what happens between sizes 2 and 9: the >= 5 row includes the 11 clusters at >= 20 that carry most of the signal. The bands below are disjoint, so each row says what an operator would see if they triaged only clusters of that size.

Attribution rule: a file is malicious if its ClawHub archive path sits under one of the 18 documented accounts, the 12 from Antiy CERT together with the accounts `iocs.json` records from payload inspection. This is the `study` rule of `file_level_precision.py`, and it reproduces the published cluster-level figures at >= 20 and >= 10 (`paper/sources/scans/file-level-precision-20260907.md:88`, `paper/sources/scans/file-level-precision-20260907.md:113`).

| cluster size | clusters | true positives | cluster precision | files | attributed | file precision | pure | mixed |
|:--|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 1,846 | 17 | 0.9% | 3,692 | 28 | 0.8% | 11 | 6 |
| 3-4 | 613 | 18 | 2.9% | 1,975 | 36 | 1.8% | 5 | 13 |
| 5-9 | 125 | 11 | 8.8% | 798 | 34 | 4.3% | 0 | 11 |
| 10-19 | 27 | 19 | 70.4% | 375 | 252 | 67.2% | 14 | 5 |
| 20+ | 11 | 11 | 100.0% | 307 | 305 | 99.3% | 9 | 2 |
| **all** | **2,622** | **76** | **2.9%** | **7,147** | **655** | **9.2%** | | |

Read down the cluster-precision column. At 20 and above every cluster is a true positive. Between 10 and 19 seven clusters in ten are. Between 5 and 9 fewer than one in ten is, and at sizes 2 to 4 the rate is one to three per hundred. The file-level column falls with it. An operator triaging the 2-file clusters would work through 1,846 clusters to find 17. That is not a viable operating point. Size is doing the work in this method, and below 10 it stops working.

Two caveats. First, the bands below 10 are exactly the region the paper's own precision-and-recall table caption disclaims: only the >= 20 and >= 10 rows reproduce from the released ground truth (Section 4.4, "rows reproduce from the released ground truth"). The March hand triage that produced the published >= 5 row (60 of 163) used a payload-inspection clause whose per-cluster decisions were never written down, so the 5-9 band here, credited by account attribution alone, should be read as a lower bound on what a full triage would allow, not as a restatement of the published row. Second, file counts are cluster memberships; 86 files sit in more than one cluster, which is why the memberships total 7,147 exceeds the 7,061 distinct clustered files.

## 2. Benign content inside attributed clusters

Malicious skills cluster. Benign skills cluster too, and the question a registry faces is how much benign content an automatic quarantine would sweep up with the malicious. Two readings, both answered from the archived scan.

**Inside the clusters credited as true positives.** These are the clusters a registry would quarantine at each threshold. The unattributed column is the benign content that goes with them.

At >= 20: 11 true positives among 11 clusters, 9 pure and 2 mixed, holding 307 files of which 2 are not attributed to any documented account (0.7% of the quarantine).

At >= 10: 30 true positives among 38 clusters, 23 pure and 7 mixed, holding 588 files of which 31 are not attributed to any documented account (5.3% of the quarantine). A further 94 files sit in the 8 clusters that are false positives outright.

Per cluster, at >= 10, the mixed ones only:

| cluster | size | attributed | unattributed | type | marketplaces |
|---:|---:|---:|---:|:--|:--|
| 854 | 35 | 34 | 1 | cross-marketplace | clawhub-archive, sundial-awesome-openclaw-skills |
| 1543 | 35 | 34 | 1 | scaffold | clawhub-archive |
| 2618 | 18 | 5 | 13 | cross-marketplace | clawhub-archive, leoyeai-openclaw-master-skills, sundial-awesome-openclaw-skills |
| 1613 | 15 | 14 | 1 | scaffold | clawhub-archive |
| 2392 | 13 | 11 | 2 | cross-marketplace | clawhub-archive, sundial-awesome-openclaw-skills |
| 942 | 11 | 1 | 10 | cross-marketplace | clawhub-archive, leoyeai-openclaw-master-skills, sundial-awesome-openclaw-skills |
| 1652 | 11 | 8 | 3 | internal | clawhub-archive |

The shape of the answer is that the swept-up benign content is small at >= 20 and concentrated at >= 10. At >= 20 two files in 307 are unattributed, one in each of the two mixed clusters. At >= 10 the count is 31 across 7 mixed clusters, and it is dominated by three cross-marketplace clusters (2618, 942, 2392) where an attacker's file has clustered with legitimate copies of the same skill in community aggregator repositories. Cluster 942 is the clearest case: 11 files, one attributed, ten not. This is the source-copy pairing the paper describes as a detection property, seen from the operator's side, where it is a cost.

**Across all clustered files.** The wider reading is what share of clustering is malicious at all, and the answer is that almost none of it is.

- Clustered memberships: 7,147, of which 655 are attributed to a documented account (9.2%) (computed).
- Distinct clustered files: 7,061, of which 621 are attributed (8.8%) (computed).

Roughly nine in ten clustered files are benign duplication, mostly aggregator repositories republishing the same skill and template scaffolds. Clustering alone is therefore not a rejection rule, and the paper does not propose it as one. Size is the discriminator, and the first table in section 1 above shows where it starts to discriminate. A registry that blocked on cluster membership alone would act on 7,061 of 31,634 files, 22.3% of the corpus, and roughly nine in ten of those are benign by the attribution rule used here.

## 3. Payload-indicator recall for unclustered files

Clustering restricted to extracted payload indicators is the natural alternative to shingle similarity, and the question it raises is whether such a grouping would have attached the unclustered files from `moonshine-100rze` and `anisafifi` to the documented campaigns. This section measures that with the indicators the artifact already carries. The marker is the one from `paper/sources/scans/file_level_precision.py`, imported rather than copied: 27 literal strings, matched case-folded as substrings against the file's text in the pinned corpus. 26 of them come from five of the eight `payload_infrastructure` categories in `iocs.json`, and 1 was added by hand from the March working notes, which are not part of this artifact (`clawcli`, `file_level_precision.py` `EXTRA_LITERALS`), so it carries no vendor provenance and a hit resting on it alone is the weakest evidence in this section.

**The seven singletons.** All 7 carry a payload indicator, and every one of them shares at least one indicator with files that did cluster and that belong to documented accounts.

| account | file | indicators matched | clustered files sharing an indicator | accounts of those files |
|:--|:--|:--|---:|:--|
| `anisafifi` | `skills/anisafifi/academic-research-hub/SKILL.md` | `clawcli`, `openclawcli` | 52 | `hightower6eu`, `jordanprater`, `kenblive`, `shylee1`, `stveenli`, `thiagoruss0`, and 2 more |
| `anisafifi` | `skills/anisafifi/dataset-finder/SKILL.md` | `clawcli`, `openclawcli` | 52 | `hightower6eu`, `jordanprater`, `kenblive`, `shylee1`, `stveenli`, `thiagoruss0`, and 2 more |
| `anisafifi` | `skills/anisafifi/qr-code-generator/SKILL.md` | `clawcli`, `openclawcli` | 52 | `hightower6eu`, `jordanprater`, `kenblive`, `shylee1`, `stveenli`, `thiagoruss0`, and 2 more |
| `anisafifi` | `skills/anisafifi/web-search-hub/SKILL.md` | `clawcli`, `openclawcli` | 52 | `hightower6eu`, `jordanprater`, `kenblive`, `shylee1`, `stveenli`, `thiagoruss0`, and 2 more |
| `moonshine-100rze` | `skills/moonshine-100rze/excel-1kl/SKILL.md` | `denboss99`, `download.setup-service.com`, `openclaw-core`, `openclawcore-1.0.3.zip` | 46 | `iqbalnaveliano`, `pierremenard`, `sakaen736jih`, `senthazalravi`, `wistec-ai-it-department`, `zaycv` |
| `moonshine-100rze` | `skills/moonshine-100rze/moltbook-lm8/SKILL.md` | `denboss99`, `download.setup-service.com`, `openclaw-core`, `openclawcore-1.0.3.zip` | 46 | `iqbalnaveliano`, `pierremenard`, `sakaen736jih`, `senthazalravi`, `wistec-ai-it-department`, `zaycv` |
| `moonshine-100rze` | `skills/moonshine-100rze/twitter-6ql/SKILL.md` | `denboss99`, `openclaw-core`, `openclawcore-1.0.3.zip`, `rentry.co/openclaw-core` | 7 | `senthazalravi`, `wistec-ai-it-department`, `zaycv` |

The result is encouraging, with one qualification. No payload-anchored clustering was run; what is measured here is that all seven files share at least one indicator with clustered files belonging to documented accounts. That is the ingredient such a grouping would use, not the grouping itself, and building it properly means deciding how to weight an indicator and what counts as a link. The indicators cost nothing to obtain, since they come from the same vendor reports that supply the ground truth, so the hybrid design the limitations section gestures at looks reachable rather than proven.

**What payload grep alone would and would not do.** Run over every unclustered file in the corpus, the marker is far weaker than the clustering it would supplement.

The populations are distinct files, not memberships: 24,573 unclustered files rather than the released scan's `summary.unclustered_files` of 24,487, which counts memberships because 86 files sit in two clusters each.

| population | files | carrying an indicator |
|:--|---:|---:|
| unclustered files in the scan | 24,573 | 73 |
| of those, under one of the 18 documented accounts | 86 | 31 |
| of those, under no documented account | 24,487 | 42 |
| clustered files in the scan | 7,061 | 492 |

Of the 42 hits under no documented account, 27 match on `clawdhub.com` alone, which `iocs.json` records as a typosquat with status unknown rather than as a confirmed payload host, and should be discounted. That leaves 15 files that a payload grep would surface and clustering did not, of which 1 rests on the hand-added literal alone (`tinkclaw`):

| marketplace | path | indicators |
|:--|:--|:--|
| clawhub-archive | `skills/adibirzu/openclaw-security-monitor/SKILL.md` | `54.91.154.110` |
| clawhub-archive | `skills/akhmittra/skill-security-auditor/SKILL.md` | `91.92.242.30`, `openclaw-agent.zip` |
| clawhub-archive | `skills/deeqyaqub1-cmd/skillfence/SKILL.md` | `54.91.154.110` |
| clawhub-archive | `skills/dieub/tinkclaw/SKILL.md` | `clawcli` |
| clawhub-archive | `skills/koatora20/guard-scanner/test/fixtures/malicious-skill/SKILL.md` | `91.92.242.30` |
| clawhub-archive | `skills/koatora20/guard-scanner/ts-src/__tests__/fixtures/malicious-skill/SKILL.md` | `91.92.242.30` |
| clawhub-archive | `skills/koatora20/guava-guard/SKILL.md` | `91.92.242.30` |
| clawhub-archive | `skills/mohibshaikh/clawvet/apps/api/test/fixtures/malicious-stealer/SKILL.md` | `openclaw-core` |
| clawhub-archive | `skills/nightfullstar/openclaw-defender/SKILL.md` | `91.92.242.30`, `aslaep123`, `ddoy233` |
| clawhub-archive | `skills/oakencore/skillvet/SKILL.md` | `54.91.154.110`, `91.92.242.30`, `ddoy233`, `openclaw-core` |
| clawhub-archive | `skills/renixaus/yahoo-finance-lpm-1-0-0/SKILL.md` | `denboss99`, `download.setup-service.com`, `openclaw-core`, `openclawcore-1.0.3.zip` |
| clawhub-archive | `skills/vincentchan/claw-skill-guard/SKILL.md` | `openclaw-core` |
| clawhub-archive | `skills/y01026350884-cyber/scam-guards/test_scenarios/malicious/SKILL.md` | `54.91.154.110`, `91.92.242.30` |
| sundial-awesome-openclaw-skills | `skills/bybit-trading/SKILL.md` | `aslaep123`, `authtool.zip`, `clawd-authtool` |
| sundial-awesome-openclaw-skills | `skills/polymarket-traiding-bot/SKILL.md` | `aslaep123`, `authtool.zip`, `polymarketauthtool`, `polymarketauthtool.zip` |

Most of that list is defensive: skills named `skillvet`, `guava-guard`, `openclaw-defender`, `skill-security-auditor` and the like, which quote the IOCs because they scan for them, plus test fixtures under `fixtures/malicious-skill/`. A grep-only pipeline would open every one of them. Two entries are not defensive and deserve a look: `sundial-awesome-openclaw-skills/skills/bybit-trading/SKILL.md` and `.../polymarket-traiding-bot/SKILL.md`, which carry the `authtool.zip` and `aslaep123` infrastructure of the documented AuthTool campaign inside a community aggregator repository, and which no cluster captured.

For contrast, 492 clustered files carry an indicator, against 73 unclustered ones. The marker is not a detector on its own. It is a linker, and its value in this corpus is that it attaches the singleton blind spot to campaigns that clustering already found. Files the marker could not read: 0.

## 4. Filter effects: tokenizer, frontmatter, and the 100-character threshold

Three questions about the front of the pipeline: whether tokenization includes or excludes the YAML frontmatter, whether the 100-character filter applies before or after tokenization, and whether an indexed document can be shorter than three words.

**The tokenizer includes the frontmatter.** Nothing in the pipeline strips it. `tokenize` (`librarian/core.py:152` to `librarian/core.py:178`) lowercases the text, collapses whitespace, and then removes every character outside `[a-z0-9\s-]`:

```python
text = text.lower()                              # librarian/core.py:152
text = re.sub(r'\s+', ' ', text).strip()
text = re.sub(r'[^a-z0-9\s\-]', '', text)
words = [w for w in text.split() if w]
```

The comment above that substitution says so directly: "Markdown files have frontmatter (key: value), code blocks, headers (#, ##) ... Now we keep dashes (important for YAML keys, multi-word terms)" (`librarian/core.py:156` to `librarian/core.py:158`). Dashes survive, so the `---` fence becomes a token of its own; the colon after a YAML key is stripped, so `name: my-skill` yields the tokens `name` and `my-skill`. A skill whose frontmatter differs and whose body is identical to another therefore differs in a handful of shingles, which is the mechanism behind the paper's observation that exact hashing misses per-skill template variations.

**The filter applies before tokenization, to the decoded text of the whole file.** The scan reads each candidate file and drops it if the string is shorter than 100 characters (`librarian/cli.py:1485` to `librarian/cli.py:1486`):

```python
content = md_file.read_text(encoding="utf-8", errors="replace")
if len(content) < 100:
    continue
```

The unit is characters of decoded text, not bytes and not tokens, and the whole file including the frontmatter is measured. Tokenization happens later, over the files that survived (`librarian/cli.py:1514`).

**So a document in the scan cannot be shorter than three words.** The shingle size is 3 (`librarian/core.py:32`), and `tokenize` carries three fallbacks for documents that cannot produce a 3-word shingle: individual words when there are one or two (`librarian/core.py:165` to `librarian/core.py:168`), character trigrams when there are no words but at least three characters (`librarian/core.py:171`), and the text itself as a single shingle otherwise (`librarian/core.py:174`). How often any of them fires on the corpus that was scanned: never.

- Files in the archived scan with fewer than three tokens after normalization: **0** of 31,634 (computed).
- Smallest indexed file by token count: 4 tokens (`clawhub-archive/skills/1227323804/sensitive-check-skill/SKILL.md`) (computed).

The filter is what prevents it, though not by construction. The test counts characters, so a 100-character file of punctuation would still normalize to nothing and take a fallback branch. No file on this corpus does. Walking the pinned corpus the way the scan does, over the same 32 marketplaces, 31,717 `SKILL.md` files are candidates and **82** are dropped by the 100-character test. 15 of those 82 hold fewer than three tokens, and 9 of them are empty files (computed).

What the sub-threshold files contain, 10 of the 15, smallest first:

| marketplace | path | characters | tokens | content |
|:--|:--|---:|---:|:--|
| clawhub-archive | `skills/raff-lima/aaaaaaa/SKILL.md` | 0 | 0 | `(empty file)` |
| clawhub-archive | `skills/snail3d/clawcamera/SKILL.md` | 0 | 0 | `(empty file)` |
| clawhub-archive | `skills/snail3d/clawd/SKILL.md` | 0 | 0 | `(empty file)` |
| clawhub-archive | `skills/snail3d/clawd/skills/office-cam/SKILL.md` | 0 | 0 | `(empty file)` |
| clawhub-archive | `skills/snail3d/clawforgod/SKILL.md` | 0 | 0 | `(empty file)` |
| clawhub-archive | `skills/snail3d/clawforgod/skills/office-cam/SKILL.md` | 0 | 0 | `(empty file)` |
| clawhub-archive | `skills/snail3d/voice-devotional/SKILL.md` | 0 | 0 | `(empty file)` |
| clawhub-archive | `skills/snail3d/voice-devotional/skills/office-cam/SKILL.md` | 0 | 0 | `(empty file)` |
| clawhub-archive | `skills/watchkido/smart-vertical-vegetable-planting-garden-arduino-serial-gateway/SKILL.md` | 0 | 0 | `(empty file)` |
| clawhub-archive | `skills/rdosec/tesrtastasra-asdasd/SKILL.md` | 5 | 1 | `test` |

These are abandoned or placeholder skills. 9 are empty files and the rest hold a word or two of scaffolding such as `test` or `# Test`. They are the documents that would otherwise reach a fallback branch, and the filter removes all of them before the tokenizer sees them. The fallback branches in `tokenize` are therefore dead code on this corpus, and they are dead code for the tool as a whole: all three call sites that feed `tokenize` apply the same 100-character test first (`librarian/cli.py:1486`, `librarian/core.py:235`, `librarian/core.py:475`). The branches survive as defensive code, not because any command reaches them.

**One nuance in the normalization.** It keeps only `[a-z0-9\s-]`, so it erases every non-Latin script. In all, 100 indexed files reduce to fewer than 20 tokens: 43 contain CJK text, 4 are `PaxHeader` tar metadata that the archive carries alongside real skills, and 53 are short Latin-script files, a mix of test fixtures and genuinely brief English skills. The erasure is what drives the shortest cases: all 9 files under 10 tokens are CJK or `PaxHeader`. Of the 100 files, 32 landed in a cluster, grouped on whatever Latin fragments survived. The smallest is `clawhub-archive/skills/1227323804/sensitive-check-skill/SKILL.md`, 100 characters of Chinese instructions that normalize to 4 tokens. Nothing in the paper's results turns on this, since the corpus is overwhelmingly English, but a registry deploying the method on a multilingual corpus would need a Unicode-aware tokenizer, and that belongs in the limitations rather than in a footnote.

**A second filter sat ahead of the size test.** The walk skipped any path whose string contained "backup", case-folded, before it read the file (`librarian/core.py:227`). On the pinned corpus that removes 864 `SKILL.md` files from consideration: 783 in `claude-code-plugins-plus`, 74 in `clawhub-archive`, 5 in `sundial-awesome-openclaw-skills`, 1 in `antigravity-awesome-skills`, 1 in `leoyeai-openclaw-master-skills`. The rule was written to skip vendored backup directories, and it does that, but it matched on the whole path, so it also dropped any skill whose own name contains the word. Section 5 below has an instance that matters. Of the 864, 780 were that intended tree in `claude-code-plugins-plus`, 2 were skills whose own directory is named `backups` or `backup`, and 82 were collateral from the substring match. A later change narrows the test to the scan root's own first path component, so that a marketplace's top-level `backups/` tree is skipped and nothing else is; that change is not in the released revision, and it has no line to cite here. A tool carrying it indexes 84 more files than the scan reported above. The numbers in this document are the released tool's and are unaffected.

One caveat on the replication. The walk over the pinned corpus finds 31,635 files passing the filter against the archived scan's 31,634. The whole difference is 1 file present in the reconstruction and absent from the March scan (`curated/creative-director_merge-conflict/creative-director/SKILL.md`, a directory that exists only in this corpus copy and not in the March scan), with nothing missing in the other direction. Every file in the archived scan resolves under the pinned corpus, so the token counts above cover the whole scan.

## 5. Populations and denominators

The corpus-level populations first, since several of the counts above divide by different ones.

| population | files |
|:--|---:|
| files in the archived scan | 31,634 |
| distinct clustered files | 7,061 |
| cluster memberships | 7,147 |
| distinct unclustered files | 24,573 |
| unclustered memberships (`summary.unclustered_files`) | 24,487 |

The ground-truth denominators next. There are two independent lists in play and the paper moves between them, which is what makes the numbers hard to follow.

| number | what it counts | recomputable from the artifact | source |
|---:|:--|:--|:--|
| 341 | skill slugs in Koi Security's original ClawHavoc report of 2026-02-01, the list the paper's headline recall is measured against | **no**, the slug list is not in the artifact | Section 4.4, "Of the 341 skill slugs in Koi Security's original"; Section 3.4, "We treated the 341 original IOC slugs from the Clawdex database" |
| 337 | of those 341, the slugs that resided in the ClawHub archive | **no**, it needs the 341 list | Section 4.4, "337 resided in the ClawHub archive"; `paper/sources/scans/threshold-sweep-20260314.md:23` |
| 354 | `hightower6eu` skill slugs recorded in `iocs.json`, 353 with a payload and 1 without | yes | `paper/iocs.json` `clawhub_authors.hightower6eu`; Section 4.4, "narrower hightower6eu subset (354 IOC slugs)" |
| 352 | of those 354, the slugs the scan indexed. The other 2 are on disk and were skipped by the walk's "backup" path rule (`librarian/core.py:227`), not missing from the snapshot | yes | computed; Section 4.4, "of the 352 scanned, 351 appeared in clusters" |
| 351 | of those 352, the slugs whose file landed in a cluster | yes | computed; Section 4.4, "of the 352 scanned, 351 appeared in clusters" |

**What `iocs.json` does and does not carry.** It carries the Koi reference as metadata: the title ("ClawHavoc: 341 Malicious Clawed Skills Found by the Bot They Were Targeting"), the URL, the dates, the updated count of 824, and the single account Koi documented (hightower6eu). It does not carry the 341 slugs. The per-skill verdicts sit in Koi's Clawdex database behind a per-skill API (Section 3.4, "We treated the 341 original IOC slugs from the Clawdex database"), so 341 and 337 cannot be recomputed here, and no attempt is made to reconstruct them. What the file does carry is two account lists, the 11 in `clawhub_authors` and the 12 Antiy CERT accounts in the reference metadata, 18 in union, together with the 354 `hightower6eu` slugs, which is the subset the threshold and shingle experiments use because those experiments were scoped to one author (Section 4.4, "narrower hightower6eu subset (354 IOC slugs)").

**The chain from 354 to 351.** Two slugs the paper once described as absent from the corpus are present: they were skipped by the backup-path filter (Section 4.4, "of the 352 scanned, 351 appeared in clusters"). Both (`openclaw-backup-dnkxm`, `openclaw-backup-wrxw0`) sit in the pinned corpus at 16,288 bytes and 16,281 bytes, and the scan never saw them because the March walk's rule (`librarian/core.py:227`) skipped any path containing "backup" and both slug names do. The same rule removes 864 `SKILL.md` files corpus-wide. What effect this has on the published recall figure is a separate question, not tested here; the point for the denominator table is that 2 of the 354 left the count through the tool's path filter rather than through upstream deletion. Of the 352 the scan did index, 351 appear in clusters and one does not: `pdf-1wso5`. That single unclustered slug is the one entry in `skill_slugs_without_payload` for this account, so the one file the clusterer missed is the one file the ground truth records as carrying no payload.

**How each maps to the abstract's within-archive recall claim.** The abstract reports that all 337 Koi-documented malicious skills present in the corpus appeared in a cluster (the abstract, "all 337 Koi-documented malicious skills present in the corpus"), so its denominator is 337, the within-archive subset of Koi's 341. It is not 341 (recall against the full list is 337/341 = 98.8%, `paper/sources/scans/threshold-sweep-20260314.md:23`) and it is not 352 (the `hightower6eu` subset gives 351/352 = 99.7% against the slugs the scan indexed, and 351/354 = 99.2% against the recorded slugs, `paper/sources/scans/threshold-sweep-20260314.md:22`). Three different denominators produce three different figures, all of them correct for their own list. A scoping sentence for the 100 percent figure would say that it is within-archive recall against Koi's 341-slug list on a single template-flood campaign class.

## What is not computed here, and why

- Koi's 341-slug list and the 337 present in the archive. The slug list is not in the artifact. `iocs.json` carries the Koi reference metadata and the account Koi documented, and the individual verdicts live behind the Clawdex per-skill API (Section 3.4, "We treated the 341 original IOC slugs from the Clawdex database"). Both figures are quoted from the paper, not recomputed.
- The published >= 15, >= 5 and all-clusters rows of the precision-and-recall table. Those record the March hand triage whose per-cluster decisions were not written down. The band table above credits the same clusters by account attribution, which is a different and stricter rule, and it is labeled as such rather than presented as a reproduction.
- Anything requiring a new scan, a temporal split, or a paraphrase experiment. Every number here comes from the archived scan, `iocs.json`, and the pinned corpus.

