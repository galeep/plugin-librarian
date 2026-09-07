# Table 1 (corpus repositories) recomputed from the archived 90% scan

## Provenance

- Input: `paper/sources/scans/scan_20260314_threshold90_skillonly.json`
- Input `metadata.generated_at`: 2026-03-14T18:10:26.003911+00:00
- Command: `python paper/sources/scans/table1_marketplaces.py` (run from the repository root)
- Repository HEAD at generation: `<private-history>`
- Aggregation rule: a repository is named when it holds at least 50 files; the rest pool into one row.

Counts are files per `marketplace` value in the scan's `file_index`, which is the corpus after the 100-character minimum filter.

## Row-by-row comparison against Table 1 as published

| Row | Computed | Table 1 as printed | Match |
|---|---:|---:|:--:|
| clawhub-archive | 23,654 | 23,654 | yes |
| claude-code-plugins-plus | 2,396 | 2,396 | yes |
| antigravity-awesome-skills | 1,249 | 1,249 | yes |
| sundial-awesome-openclaw-skills | 933 | 933 | yes |
| claude-code-templates | 715 | 715 | yes |
| curated | 639 | 639 | yes |
| han | 429 | 429 | yes |
| alirezarezvani-claude-skills | 421 | 421 | yes |
| leoyeai-openclaw-master-skills | 361 | 361 | yes |
| claude-scientific-skills | 175 | 175 | yes |
| claude-code-workflows | 146 | 146 | yes |
| mag-claude-plugins | 131 | 131 | yes |
| 20 repositories with <50 files each | 385 | 385 | yes |
| Total (32 repositories) | 31,634 | 31,634 | yes |

All rows agree with the printed table.

## Pooled repositories

20 repositories hold fewer than 50 files each, 385 files in total:

- every-marketplace: 49
- daymade-claude-code-skills: 43
- cc-polymath-marketplace: 26
- geoffjay-claude-plugins: 25
- skills-marketplace: 24
- claude-forge: 23
- gmickel-claude-marketplace: 23
- claude-craftkit: 19
- superpowers-marketplace-resolved: 19
- anthropic-agent-skills: 18
- anthropics-skills: 18
- plugins-for-claude-natives: 17
- claude-plugins-official: 15
- ananddtyagi-cc-marketplace: 14
- cc-marketplace: 14
- hashicorp-agent-skills: 14
- side-quest-marketplace: 12
- competition-scout: 6
- chrome-devtools-plugins: 5
- openskills: 1

Named repositories: 12. Total repositories: 32.
