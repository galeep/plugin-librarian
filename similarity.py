#!/usr/bin/env python3
"""
Plugin Librarian: Similarity detection using MinHash/LSH.

Finds clusters of near-duplicate files across the plugin ecosystem,
identifying shallow adaptations and their likely canonical sources.
"""

import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from datasketch import MinHash, MinHashLSH


MARKETPLACES_DIR = Path.home() / ".claude" / "plugins" / "marketplaces"

# Similarity threshold (0.0 to 1.0)
# 0.7 = 70% similar content
SIMILARITY_THRESHOLD = 0.7

# Number of permutations for MinHash (higher = more accurate, slower)
NUM_PERM = 128

# Shingle size (n-gram length for tokenization)
SHINGLE_SIZE = 3

# Scaffold detection thresholds (inferred from data, not assumed)
SCAFFOLD_MIN_COPIES = 5  # Cluster must have at least this many files
SCAFFOLD_MIN_SIMILARITY = 0.98  # Must be near-identical (not just similar)


@dataclass
class FileInfo:
    """Information about a content file."""
    marketplace: str
    plugin: str
    relative_path: str
    full_path: str
    content: str = ""
    minhash: MinHash = field(default=None, repr=False)

    @property
    def location(self) -> str:
        return f"{self.marketplace}/{self.plugin}/{self.relative_path}"

    @property
    def is_official(self) -> bool:
        """Observable fact: from an Anthropic-maintained source."""
        return self.marketplace.startswith(("anthropic", "claude-plugins-official"))


@dataclass
class SimilarityCluster:
    """A group of similar files."""
    files: list[FileInfo] = field(default_factory=list)
    avg_similarity: float = 0.0

    @property
    def is_internal(self) -> bool:
        """True if all files are from the same marketplace."""
        return len(self.marketplaces) == 1

    @property
    def is_scaffold(self) -> bool:
        """Inferred from data: high-copy, near-identical, internal cluster."""
        return (
            self.is_internal
            and len(self.files) >= SCAFFOLD_MIN_COPIES
            and self.avg_similarity >= SCAFFOLD_MIN_SIMILARITY
        )

    @property
    def marketplaces(self) -> set[str]:
        """Set of marketplaces this cluster spans."""
        return set(f.marketplace for f in self.files)

    @property
    def has_official(self) -> bool:
        """True if cluster contains files from official sources."""
        return any(f.is_official for f in self.files)

    @property
    def cluster_type(self) -> str:
        """Classify the cluster based on observed behavior."""
        if self.is_scaffold:
            return "scaffold"
        elif self.is_internal:
            return "internal"
        else:
            return "cross-marketplace"


def tokenize(text: str) -> set[str]:
    """Convert text to set of shingles (n-grams)."""
    # Normalize: lowercase, collapse whitespace, remove punctuation
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)

    # Generate shingles
    words = text.split()
    if len(words) < SHINGLE_SIZE:
        return set(words)

    shingles = set()
    for i in range(len(words) - SHINGLE_SIZE + 1):
        shingle = ' '.join(words[i:i + SHINGLE_SIZE])
        shingles.add(shingle)

    return shingles


def compute_minhash(shingles: set[str]) -> MinHash:
    """Compute MinHash signature for a set of shingles."""
    m = MinHash(num_perm=NUM_PERM)
    for s in shingles:
        m.update(s.encode('utf-8'))
    return m


def find_content_files() -> list[FileInfo]:
    """Find all content files across marketplaces."""
    files = []

    for mp in sorted(MARKETPLACES_DIR.iterdir()):
        if not mp.is_dir() or mp.name.startswith("."):
            continue

        for md_file in mp.rglob("*.md"):
            # Skip backups
            if "backup" in str(md_file).lower():
                continue

            # Determine plugin name from path
            rel_to_mp = md_file.relative_to(mp)
            parts = rel_to_mp.parts

            # Try to identify plugin directory
            plugin = "root"
            if "plugins" in parts:
                idx = parts.index("plugins")
                if idx + 1 < len(parts):
                    plugin = parts[idx + 1]
            elif len(parts) > 1:
                plugin = parts[0]

            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
                # Skip very small files (likely placeholders)
                if len(content) < 100:
                    continue

                files.append(FileInfo(
                    marketplace=mp.name,
                    plugin=plugin,
                    relative_path=str(rel_to_mp),
                    full_path=str(md_file),
                    content=content,
                ))
            except Exception as e:
                print(f"Warning: Could not read {md_file}: {e}", file=sys.stderr)

    return files


def build_lsh_index(files: list[FileInfo]) -> MinHashLSH:
    """Build LSH index from files."""
    lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)

    for i, f in enumerate(files):
        shingles = tokenize(f.content)
        if not shingles:
            continue
        f.minhash = compute_minhash(shingles)
        lsh.insert(str(i), f.minhash)

    return lsh


def find_clusters(files: list[FileInfo], lsh: MinHashLSH) -> list[SimilarityCluster]:
    """Find clusters of similar files."""
    # Track which files have been assigned to clusters
    assigned = set()
    clusters = []

    for i, f in enumerate(files):
        if i in assigned or f.minhash is None:
            continue

        # Query LSH for similar files
        result = lsh.query(f.minhash)
        similar_indices = [int(r) for r in result]

        if len(similar_indices) > 1:
            cluster_files = [files[j] for j in similar_indices if files[j].minhash is not None]

            # Compute average pairwise similarity
            similarities = []
            for j, f1 in enumerate(cluster_files):
                for f2 in cluster_files[j+1:]:
                    sim = f1.minhash.jaccard(f2.minhash)
                    similarities.append(sim)

            avg_sim = sum(similarities) / len(similarities) if similarities else 0

            cluster = SimilarityCluster(
                files=cluster_files,
                avg_similarity=avg_sim,
            )
            clusters.append(cluster)

            assigned.update(similar_indices)

    # Sort by cluster size (largest first)
    clusters.sort(key=lambda c: len(c.files), reverse=True)

    return clusters


def categorize_clusters(clusters: list[SimilarityCluster]) -> dict:
    """Categorize clusters by type."""
    by_type = defaultdict(list)
    for c in clusters:
        by_type[c.cluster_type].append(c)
    return dict(by_type)


def main():
    print(f"Scanning marketplaces in {MARKETPLACES_DIR}...")
    print(f"Similarity threshold: {SIMILARITY_THRESHOLD * 100:.0f}%")
    print()

    # Find all content files
    files = find_content_files()
    print(f"Found {len(files)} content files (>100 chars)")

    # Build LSH index
    print("Building MinHash signatures...")
    lsh = build_lsh_index(files)

    # Find clusters
    print("Finding similarity clusters...")
    clusters = find_clusters(files, lsh)

    # Filter to clusters with 2+ files
    clusters = [c for c in clusters if len(c.files) >= 2]

    print(f"\nFound {len(clusters)} clusters of similar files")

    # Categorize by type
    by_type = categorize_clusters(clusters)

    # Print results
    print(f"\n{'=' * 60}")
    print("SIMILARITY ANALYSIS COMPLETE")
    print(f"{'=' * 60}")

    total_files_in_clusters = sum(len(c.files) for c in clusters)
    print(f"Total files in clusters: {total_files_in_clusters}")
    print(f"Total clusters: {len(clusters)}")

    print(f"\nCluster breakdown by type:")
    for ctype in ["cross-marketplace", "internal", "scaffold"]:
        type_clusters = by_type.get(ctype, [])
        type_files = sum(len(c.files) for c in type_clusters)
        print(f"  {ctype}: {len(type_clusters)} clusters, {type_files} files")

    # Cross-marketplace clusters are the interesting ones
    cross_mp = by_type.get("cross-marketplace", [])
    if cross_mp:
        print(f"\nCross-marketplace clusters (real similarity):")
        for cluster in cross_mp[:15]:
            mps = sorted(cluster.marketplaces)
            sample_file = cluster.files[0]
            print(f"\n  {len(cluster.files)} files, {cluster.avg_similarity*100:.0f}% similar")
            print(f"  File: {Path(sample_file.relative_path).name}")
            print(f"  Marketplaces: {', '.join(mps)}")
            if cluster.has_official:
                print(f"  [contains official source]")

    # Scaffold clusters
    scaffold = by_type.get("scaffold", [])
    if scaffold:
        print(f"\nScaffold clusters (internal templates, {len(scaffold)} clusters):")
        for cluster in scaffold[:5]:
            mp = list(cluster.marketplaces)[0]
            sample_file = cluster.files[0]
            print(f"  {mp}: {len(cluster.files)} copies of {Path(sample_file.relative_path).name}")

    # Save detailed results
    output = {
        "summary": {
            "total_files_scanned": len(files),
            "files_in_clusters": total_files_in_clusters,
            "unique_clusters": len(clusters),
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "by_type": {
                ctype: {
                    "clusters": len(by_type.get(ctype, [])),
                    "files": sum(len(c.files) for c in by_type.get(ctype, [])),
                }
                for ctype in ["cross-marketplace", "internal", "scaffold"]
            },
        },
        "clusters": [
            {
                "type": c.cluster_type,
                "size": len(c.files),
                "avg_similarity": round(c.avg_similarity, 3),
                "has_official": c.has_official,
                "marketplaces": sorted(c.marketplaces),
                "locations": [
                    {
                        "marketplace": f.marketplace,
                        "plugin": f.plugin,
                        "path": f.relative_path,
                        "is_official": f.is_official,
                    }
                    for f in c.files
                ],
            }
            for c in clusters
        ],
    }

    output_path = Path(__file__).parent / "similarity_report.json"
    with open(output_path, "w") as fh:
        json.dump(output, fh, indent=2)
    print(f"\nDetailed report: {output_path}")


if __name__ == "__main__":
    main()
