# What the backup-path filter excluded from the clustering

Corpus root: `$LIBRARIAN_CORPUS`
Repository HEAD: `<private-history>`
Input scan: `scan_20260314_threshold90_skillonly.json` (31634 indexed files).
Command: `python paper/sources/scans/backup_slug_check.py` from the repository root, with LIBRARIAN_CORPUS set.
Generated: 2026-09-07 03:33:22Z.

What the backup-path filter excluded from the clustering. It supports the filter description in Section 3.2 (Dataset Construction), the recall chain of Section 4.4 (IOC Validation) from the 354 recorded slugs down to the 351 that clustered, and the note in Section 6 (Limitations) that the filter skipped two hightower6eu skills which, once scanned, cluster only with each other.

What it measures: for every `SKILL.md` the filter excluded from `clawhub-archive`, whether the archived index returns any LSH candidate for it at threshold 0.9, and whether the cluster count and the hightower6eu recall move when the 2 skipped hightower6eu skills are scanned alongside the archived files.

Settings, matching the paper: MinHash with 128 permutations at the datasketch default seed, 3-word shingles from `librarian.core.tokenize`, LSH threshold 0.9. `load_files`, `signatures` and `greedy` are imported from `order_permutation.py` unchanged, so the archived clustering is reproduced rather than re-implemented.

Signatures: 31708 of 31708 (31634 archived + 74 backup-path files from `clawhub-archive`). Skipped 0 missing, 0 shorter than 100 characters, 0 with no shingles.
Archived-only baseline: 2622 clusters (archived scan summary records 2622).

## The two hightower6eu skills the filter skipped

### `clawhub-archive/skills/hightower6eu/openclaw-backup-dnkxm/SKILL.md`

No archived file is returned by the LSH at threshold 0.9: this file is a candidate for nothing in the archived index.

In the rerun greedy loop this file joins cluster #2622 of the augmented run, size 2. Members: `clawhub-archive/skills/hightower6eu/openclaw-backup-dnkxm/SKILL.md` (appended); `clawhub-archive/skills/hightower6eu/openclaw-backup-wrxw0/SKILL.md` (appended).

**Every member of this cluster is one of the appended files.** The cluster exists only because the two filtered files match each other; no archived file is near either of them at this threshold.

### `clawhub-archive/skills/hightower6eu/openclaw-backup-wrxw0/SKILL.md`

No archived file is returned by the LSH at threshold 0.9: this file is a candidate for nothing in the archived index.

In the rerun greedy loop this file joins cluster #2622 of the augmented run, size 2. Members: `clawhub-archive/skills/hightower6eu/openclaw-backup-dnkxm/SKILL.md` (appended); `clawhub-archive/skills/hightower6eu/openclaw-backup-wrxw0/SKILL.md` (appended).

**Every member of this cluster is one of the appended files.** The cluster exists only because the two filtered files match each other; no archived file is near either of them at this threshold.

## Cluster count and hightower6eu recall

Baseline (archived file list, sorted order): **2622 clusters**, 7147 files clustered as a sum of cluster sizes.
With the two files appended: **2623 clusters**, 7149 files clustered as a sum of cluster sizes.

Section 4.4 reports the recall as 351 of the 352 scanned, 99.7%, and 99.2% against the full 354. That is the figure for the corpus as scanned. The 2 skipped slugs are present on disk in `clawhub-archive`; the filter excluded them.

Had the filter not applied, the same rule, which counts a slug as recalled when it appears in a similarity cluster whatever the cluster's other members are, gives **353 of 354** (99.7%). The percentage is 99.7% on either denominator.

The pair's similarity is not a MinHash artifact. Their exact 3-word-shingle Jaccard, computed directly from the two shingle sets rather than estimated, is **0.9913** (1365 shingles shared of 1377 in the union; each file has 1371 and 1371 shingles).

## The other 72 ClawHub backup-path files (query only, no greedy rerun)

Of 72 files, **3** return at least one archived neighbor at threshold 0.9, and **1** of those have at least one neighbor in an account this study documented (the 18-account `study` ground truth from `file_level_precision.py`, applied with its `account_of`).

Both counts are LSH candidacy at threshold 0.9, not verified isolation. LSH is a probabilistic filter that can miss pairs just under the threshold, so an empty row means no candidate was retrieved, not that no similar file exists; a full pairwise comparison would be needed to say the latter. A row with a neighbor, by contrast, is a positive finding: that file was a cluster member the filter removed. Rows are the marketplace-relative path under `clawhub-archive`.

Files whose neighbors reach an account this study documented: `skills/jacobo-create/backup-gog-20260213-121122/SKILL.md` has 11 neighbors at up to est. J 1.0000, reaching `zaycv`: the filter removed a file that would have joined a documented attacker's cluster; the paper's distinct-file counts describe the corpus as scanned and do not include it.

| path | account | neighbors | neighbor accounts in `study` | max est. Jaccard |
|---|---|---:|---:|---:|
| `skills/adelpro/openclaw-backup-automation/SKILL.md` | adelpro | 0 | 0 | - |
| `skills/aiwithabidi/workspace-backup/SKILL.md` | aiwithabidi | 0 | 0 | - |
| `skills/alessandropcostabr/openclaw-backup-safe/SKILL.md` | alessandropcostabr | 0 | 0 | - |
| `skills/alex3alex/openclaw-backup/SKILL.md` | alex3alex | 0 | 0 | - |
| `skills/beyound87/myopenclaw-backup-restore/SKILL.md` | beyound87 | 0 | 0 | - |
| `skills/caigang78/feishu-backup/SKILL.md` | caigang78 | 0 | 0 | - |
| `skills/caigang78/slack-backup/SKILL.md` | caigang78 | 0 | 0 | - |
| `skills/caozeal/webdav-backup/SKILL.md` | caozeal | 0 | 0 | - |
| `skills/cccarv82/openclaw-backup-optimized/SKILL.md` | cccarv82 | 0 | 0 | - |
| `skills/cinience/alicloud-backup-bdrc/SKILL.md` | cinience | 0 | 0 | - |
| `skills/cinience/alicloud-backup-hbr/SKILL.md` | cinience | 0 | 0 | - |
| `skills/cooperun/workspace-git-backup/SKILL.md` | cooperun | 0 | 0 | - |
| `skills/crazyfeng666/dji-backup/SKILL.md` | crazyfeng666 | 0 | 0 | - |
| `skills/danielglh/claw-soul-backup/SKILL.md` | danielglh | 0 | 0 | - |
| `skills/darinrowe/openclaw-backup-restore/SKILL.md` | darinrowe | 0 | 0 | - |
| `skills/dragonhuge/email-backup/SKILL.md` | dragonhuge | 0 | 0 | - |
| `skills/gexsta/skills-backup-claw-shell/SKILL.md` | gexsta | 4 | 0 | 1.0000 |
| `skills/googleworkspace-bot/recipe-backup-sheet-as-csv/SKILL.md` | googleworkspace-bot | 0 | 0 | - |
| `skills/hacksing/safe-backup/SKILL.md` | hacksing | 0 | 0 | - |
| `skills/haohanyang92/openclaw-backup-tool/SKILL.md` | haohanyang92 | 0 | 0 | - |
| `skills/hhse/openclaw-backupgg/SKILL.md` | hhse | 0 | 0 | - |
| `skills/hi-jiajun/openclaw-backup-hiliang/SKILL.md` | hi-jiajun | 0 | 0 | - |
| `skills/ivangdavila/backups/SKILL.md` | ivangdavila | 0 | 0 | - |
| `skills/jacobo-create/backup-gog-20260213-121122/SKILL.md` | jacobo-create | 11 | `zaycv` | 1.0000 |
| `skills/jordanprater/backup/SKILL.md` | jordanprater | 0 | 0 | - |
| `skills/keepchen/stardots-backup/SKILL.md` | keepchen | 0 | 0 | - |
| `skills/konscious0beast/external-ki-integration-backup/SKILL.md` | konscious0beast | 0 | 0 | - |
| `skills/lancelot3777-svg/openclaw-backup-guide/SKILL.md` | lancelot3777-svg | 0 | 0 | - |
| `skills/laserducktales/obsidian-conversation-backup/SKILL.md` | laserducktales | 0 | 0 | - |
| `skills/leoyeai/myclaw-backup/SKILL.md` | leoyeai | 0 | 0 | - |
| `skills/littlejakub/healthy-backup/SKILL.md` | littlejakub | 0 | 0 | - |
| `skills/louzhixian/git-crypt-backup/SKILL.md` | louzhixian | 0 | 0 | - |
| `skills/lxgicstudios/ai-backup-script/SKILL.md` | lxgicstudios | 0 | 0 | - |
| `skills/lxgicstudios/backup-gen/SKILL.md` | lxgicstudios | 0 | 0 | - |
| `skills/lxgicstudios/backup-script-gen/SKILL.md` | lxgicstudios | 0 | 0 | - |
| `skills/marzliak/quick-backup-restore/SKILL.md` | marzliak | 0 | 0 | - |
| `skills/mayueanyou/self-backup/SKILL.md` | mayueanyou | 0 | 0 | - |
| `skills/meowlegemy-sudo/finn-openclaw-backup/SKILL.md` | meowlegemy-sudo | 0 | 0 | - |
| `skills/michael-crazy/clawdog-backup/SKILL.md` | michael-crazy | 0 | 0 | - |
| `skills/moep90/restic-home-backup-safe/SKILL.md` | moep90 | 0 | 0 | - |
| `skills/moep90/restic-home-backup/SKILL.md` | moep90 | 0 | 0 | - |
| `skills/moroiser/openclaw-config-backuper/SKILL.md` | moroiser | 0 | 0 | - |
| `skills/nevereven619/session-archive-backup/SKILL.md` | nevereven619 | 0 | 0 | - |
| `skills/nickchan0412/coding-agent-backup/SKILL.md` | nickchan0412 | 0 | 0 | - |
| `skills/nissan/langfuse-backup/SKILL.md` | nissan | 0 | 0 | - |
| `skills/nissan/proton-drive-backup/SKILL.md` | nissan | 0 | 0 | - |
| `skills/obuchowski/cloud-backup/SKILL.md` | obuchowski | 0 | 0 | - |
| `skills/obuchowski/openclaw-cloud-backup/SKILL.md` | obuchowski | 0 | 0 | - |
| `skills/pacifier00/agent-backup-transfer/SKILL.md` | pacifier00 | 0 | 0 | - |
| `skills/pfrederiksen/synology-backup/SKILL.md` | pfrederiksen | 0 | 0 | - |
| `skills/picaye/backup-manager/SKILL.md` | picaye | 0 | 0 | - |
| `skills/ppopen/openclaw-skill-backup-manager/SKILL.md` | ppopen | 0 | 0 | - |
| `skills/rhanxerox/rhandus-backup-recovery/SKILL.md` | rhanxerox | 0 | 0 | - |
| `skills/rohitg00/k8s-backup/SKILL.md` | rohitg00 | 0 | 0 | - |
| `skills/ryanedick/backup-and-restore/SKILL.md` | ryanedick | 0 | 0 | - |
| `skills/sa9saq/db-backup/SKILL.md` | sa9saq | 0 | 0 | - |
| `skills/sarielwang93/moltbook-backup/SKILL.md` | sarielwang93 | 5 | 0 | 0.9219 |
| `skills/satoshistackalotto/system-integrity-and-backup/SKILL.md` | satoshistackalotto | 0 | 0 | - |
| `skills/sebastian-buitrag0/clawdbot-backup/SKILL.md` | sebastian-buitrag0 | 0 | 0 | - |
| `skills/solidexu/git-backup-publish/SKILL.md` | solidexu | 0 | 0 | - |
| `skills/teamtelnyx/telnyx-storage-backup/SKILL.md` | teamtelnyx | 0 | 0 | - |
| `skills/theshadowrose/openclaw-3tier-backup/SKILL.md` | theshadowrose | 0 | 0 | - |
| `skills/trumppo/fullbackup/SKILL.md` | trumppo | 0 | 0 | - |
| `skills/trumppo/gitbackup/SKILL.md` | trumppo | 0 | 0 | - |
| `skills/vacinc/simple-backup/SKILL.md` | vacinc | 0 | 0 | - |
| `skills/vidarbrekke/claw-backup/SKILL.md` | vidarbrekke | 0 | 0 | - |
| `skills/vince-winkintel/planetscale-cli-skills/pscale-backup/SKILL.md` | vince-winkintel | 0 | 0 | - |
| `skills/vince-winkintel/sql-server-skills/sqlserver-backup/SKILL.md` | vince-winkintel | 0 | 0 | - |
| `skills/walbertus/hsk-skill-github-backup/SKILL.md` | walbertus | 0 | 0 | - |
| `skills/webdevtodayjason/openclaw-self-backup/SKILL.md` | webdevtodayjason | 0 | 0 | - |
| `skills/x-rayluan/soul-backup-skill/SKILL.md` | x-rayluan | 0 | 0 | - |
| `skills/zfanmy/cron-backup/SKILL.md` | zfanmy | 0 | 0 | - |

Runtime: 603 s.

