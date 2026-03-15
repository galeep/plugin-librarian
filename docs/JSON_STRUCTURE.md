# Similarity Report JSON Structure

## Overview

The `similarity_report.json` file uses a structured format optimized for programmatic access and jq queries. Version 2.0 introduces indices for fast lookups and explicit cluster membership tracking.

## Schema

```json
{
  "metadata": {
    "version": "2.0",
    "generated_at": "2025-01-17T12:34:56.789Z",
    "similarity_threshold": 0.7,
    "num_permutations": 128,
    "confidence": "high",
    "warnings": []
  },
  "summary": {
    "total_files_scanned": 14376,
    "files_in_clusters": 6549,
    "unclustered_files": 7827,
    "unique_clusters": 1742,
    "unique_marketplaces": 16,
    "by_type": {
      "cross-marketplace": {
        "clusters": 794,
        "files": 1654
      },
      "internal": {
        "clusters": 933,
        "files": 4431
      },
      "scaffold": {
        "clusters": 15,
        "files": 464
      }
    }
  },
  "file_index": [
    {
      "file_index": 0,
      "marketplace": "marketplace-name",
      "plugin": "plugin-name",
      "path": "skills/example.md",
      "filename": "example.md",
      "is_official": false,
      "cluster_id": 42,
      "in_cluster": true
    }
  ],
  "marketplace_index": {
    "marketplace-name": [0, 1, 5, 10]
  },
  "filename_index": {
    "example.md": [0, 5, 10]
  },
  "clusters": [
    {
      "cluster_id": 0,
      "type": "cross-marketplace",
      "size": 5,
      "avg_similarity": 0.85,
      "has_official": true,
      "marketplaces": ["marketplace-a", "marketplace-b"],
      "locations": [
        {
          "file_index": 0,
          "marketplace": "marketplace-a",
          "plugin": "plugin-1",
          "path": "skills/skill.md",
          "is_official": false
        }
      ],
      "similarity_pairs": [
        {
          "file1_index": 0,
          "file2_index": 1,
          "similarity": 0.87
        }
      ]
    }
  ]
}
```

## Field Descriptions

### metadata

Top-level metadata about the scan.

- `version`: JSON schema version (currently "2.0")
- `generated_at`: ISO 8601 timestamp of when the scan completed
- `similarity_threshold`: MinHash similarity threshold used (0.0-1.0)
- `num_permutations`: Number of hash permutations used for MinHash
- `confidence`: Confidence level of results ("high", "medium", "low", "none")
- `warnings`: Array of warning messages from sanity checks

### summary

High-level statistics about the scan results.

- `total_files_scanned`: Total number of files analyzed
- `files_in_clusters`: Number of files that belong to similarity clusters
- `unclustered_files`: Number of unique files (not in any cluster)
- `unique_clusters`: Total number of clusters found
- `unique_marketplaces`: Number of distinct marketplaces scanned
- `by_type`: Breakdown by cluster type (cross-marketplace, internal, scaffold)

### file_index

Array of all scanned files with their cluster membership. Enables O(1) file lookups.

- `file_index`: Unique index for this file (used in other arrays)
- `marketplace`: Marketplace containing the file
- `plugin`: Plugin containing the file
- `path`: Relative path within the marketplace
- `filename`: Base filename (for quick filtering)
- `is_official`: Whether this is from an official Anthropic marketplace
- `cluster_id`: ID of cluster this file belongs to (null if unclustered)
- `in_cluster`: Boolean flag for quick filtering

### marketplace_index

Dictionary mapping marketplace names to arrays of cluster IDs. Enables fast marketplace filtering.

```json
{
  "marketplace-name": [0, 1, 5, 10]
}
```

### filename_index

Dictionary mapping filenames to arrays of cluster IDs. Enables fast filename lookups.

```json
{
  "skill.md": [0, 5, 10, 42]
}
```

### clusters

Array of similarity clusters with detailed information.

- `cluster_id`: Unique cluster identifier
- `type`: Cluster type ("cross-marketplace", "internal", "scaffold")
- `size`: Number of files in this cluster
- `avg_similarity`: Average pairwise similarity (0.0-1.0)
- `has_official`: Whether cluster contains any official files
- `marketplaces`: Array of marketplace names in this cluster
- `locations`: Array of file locations in this cluster
- `similarity_pairs`: Pairwise similarity matrix for files in cluster

## Common jq Queries

### Get all files from a specific marketplace

```bash
jq '.file_index[] | select(.marketplace == "marketplace-name")' similarity_report.json
```

### Get clusters for a specific marketplace

```bash
jq '.marketplace_index["marketplace-name"] as $ids | .clusters[] | select(.cluster_id as $c | $ids | index($c))' similarity_report.json
```

### Find all clusters containing a specific filename

```bash
jq '.filename_index["skill.md"] as $ids | .clusters[] | select(.cluster_id as $c | $ids | index($c))' similarity_report.json
```

### Get top 10 most similar file pairs

```bash
jq '[.clusters[].similarity_pairs[]] | sort_by(.similarity) | reverse | .[0:10]' similarity_report.json
```

### Count files per marketplace

```bash
jq '.file_index | group_by(.marketplace) | map({marketplace: .[0].marketplace, count: length})' similarity_report.json
```

### Get all cross-marketplace clusters

```bash
jq '.clusters[] | select(.type == "cross-marketplace")' similarity_report.json
```

### Find unclustered files

```bash
jq '.file_index[] | select(.in_cluster == false)' similarity_report.json
```

### Get cluster size distribution

```bash
jq '[.clusters[].size] | group_by(.) | map({size: .[0], count: length}) | sort_by(.size)' similarity_report.json
```

### Find all official files

```bash
jq '.file_index[] | select(.is_official == true)' similarity_report.json
```

### Get clusters with official content

```bash
jq '.clusters[] | select(.has_official == true)' similarity_report.json
```

### Get all files in a specific cluster

```bash
jq '.clusters[] | select(.cluster_id == 42) | .locations[]' similarity_report.json
```

### Calculate total duplicated content

```bash
jq '.summary.files_in_clusters / .summary.total_files_scanned * 100' similarity_report.json
```

## Backward Compatibility

The LocationIndex class in `cli.py` maintains backward compatibility with the old JSON format (pre-v2.0). Old reports lacking `metadata`, `file_index`, etc. can still be loaded, though without the performance benefits of pre-built indices.

## Migration from v1.0

No migration is required. Simply run `librarian scan` again to generate a new v2.0 report. The new format includes all information from v1.0 plus additional indices and metadata.

Key differences from v1.0:
- Added `metadata` top-level section
- Added `file_index` array for O(1) file lookups
- Added `marketplace_index` dictionary for fast marketplace filtering
- Added `filename_index` dictionary for fast filename lookups
- Added `cluster_id` to each cluster
- Added `file_index` reference to each location
- Added `similarity_pairs` array to each cluster
- Added `unclustered_files` count to summary
- Changed timestamp from implicit to explicit in metadata

## Performance

The new structure provides significant performance improvements for common queries:

- File lookup by marketplace: O(1) with `file_index`
- Cluster lookup by marketplace: O(1) with `marketplace_index`
- Cluster lookup by filename: O(1) with `filename_index`
- File cluster membership: O(1) lookup via `cluster_id` field

Without indices, these operations would require O(n) scans of the entire clusters array.
