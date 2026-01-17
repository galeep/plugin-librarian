#!/usr/bin/env python3
"""Plugin Librarian CLI: Navigate the Claude Code plugin ecosystem."""

import argparse
import fnmatch
import json
import re
import sys
import textwrap
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import yaml
from datasketch import MinHashLSH

from .core import (
    MARKETPLACES_DIR,
    SIMILARITY_THRESHOLD,
    NUM_PERM,
    Location,
    ClusterInfo,
    Capability,
    load_installed_plugins,
    load_baseline_files,
    scan_directory_for_content,
    find_marketplace_path,
    find_plugin_in_marketplace,
    check_similarity_sanity,
)
from .cmd_checkout import cmd_checkout


# ============================================================================
# Skill analysis dataclass
# ============================================================================

@dataclass
class SkillInfo:
    """Parsed skill metadata and analysis."""
    name: str
    kind: str  # skill or agent
    marketplace: str
    plugin: str
    path: str
    description: str
    triggers: list[str]
    dependencies: list[str]
    tool_uses: list[str]
    line_count: int
    word_count: int
    complexity_score: str  # low, medium, high
    has_frontmatter: bool
    raw_frontmatter: dict

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "location": {
                "marketplace": self.marketplace,
                "plugin": self.plugin,
                "path": self.path,
            },
            "description": self.description,
            "triggers": self.triggers,
            "dependencies": self.dependencies,
            "tool_uses": self.tool_uses,
            "metrics": {
                "line_count": self.line_count,
                "word_count": self.word_count,
                "complexity": self.complexity_score,
            },
            "has_frontmatter": self.has_frontmatter,
            "frontmatter": self.raw_frontmatter,
        }


# Data directory for generated indexes
DATA_DIR = Path.home() / ".librarian"
SIMILARITY_REPORT = DATA_DIR / "similarity_report.json"


def ensure_data_dir():
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# WHERE command: Find locations of similar files
# ============================================================================

class LocationIndex:
    """Inverted index for file location queries."""

    def __init__(self):
        self.by_filename = defaultdict(list)
        self.by_marketplace = defaultdict(list)
        self.clusters = {}
        self.total_files = 0
        self.total_clusters = 0

    def build_from_report(self, report_path: Path) -> None:
        with open(report_path) as fh:
            report = json.load(fh)

        self.total_files = report["summary"]["total_files_scanned"]

        for idx, cluster_data in enumerate(report["clusters"]):
            locations = [
                Location(
                    marketplace=loc["marketplace"],
                    plugin=loc["plugin"],
                    path=loc["path"],
                    is_official=loc["is_official"],
                )
                for loc in cluster_data["locations"]
            ]

            cluster = ClusterInfo(
                cluster_id=idx,
                cluster_type=cluster_data["type"],
                size=cluster_data["size"],
                avg_similarity=cluster_data["avg_similarity"],
                has_official=cluster_data["has_official"],
                marketplaces=cluster_data["marketplaces"],
                locations=locations,
            )

            self.clusters[idx] = cluster

            for loc in locations:
                self.by_filename[loc.filename].append(idx)

            for mp in cluster_data["marketplaces"]:
                self.by_marketplace[mp].append(idx)

        self.total_clusters = len(self.clusters)

        for filename in self.by_filename:
            self.by_filename[filename] = list(set(self.by_filename[filename]))
        for mp in self.by_marketplace:
            self.by_marketplace[mp] = list(set(self.by_marketplace[mp]))

    def where(self, query: str) -> list[tuple[ClusterInfo, list[Location]]]:
        results = []
        query_name = Path(query).name

        # Try exact filename
        cluster_ids = self.by_filename.get(query_name, [])
        if cluster_ids:
            for cid in cluster_ids:
                cluster = self.clusters[cid]
                matching = [loc for loc in cluster.locations if loc.filename == query_name]
                results.append((cluster, matching))
            return results

        # Try pattern match
        for filename, cids in self.by_filename.items():
            if fnmatch.fnmatch(filename, query) or fnmatch.fnmatch(filename, f"*{query}*"):
                for cid in cids:
                    if cid not in [r[0].cluster_id for r in results]:
                        cluster = self.clusters[cid]
                        matching = [loc for loc in cluster.locations
                                   if fnmatch.fnmatch(loc.filename, query) or query.lower() in loc.filename.lower()]
                        if matching:
                            results.append((cluster, matching))

        return results


def cmd_where(args):
    """Find where similar content exists."""
    if not SIMILARITY_REPORT.exists():
        print(f"Error: Index not found. Run 'librarian scan' first.")
        print(f"Expected: {SIMILARITY_REPORT}")
        sys.exit(1)

    index = LocationIndex()
    index.build_from_report(SIMILARITY_REPORT)

    results = index.where(args.query)

    if not results:
        print(f"No similar files found for: {args.query}")
        return

    total_locations = sum(len(locs) for _, locs in results)
    print(f"Found {total_locations} locations across {len(results)} clusters:\n")

    for cluster, locations in results:
        official = " [has official]" if cluster.has_official else ""
        print(f"Cluster #{cluster.cluster_id}: {cluster.size} files, "
              f"{cluster.avg_similarity*100:.0f}% similar, "
              f"type={cluster.cluster_type}{official}")
        print(f"  Marketplaces: {', '.join(cluster.marketplaces)}")
        print(f"  Locations:")
        for loc in locations:
            off = " [official]" if loc.is_official else ""
            print(f"    {loc.marketplace}/{loc.plugin}/{loc.path}{off}")
        print()


# ============================================================================
# COMPARE-MARKETPLACES command: Direct marketplace-to-marketplace comparison
# ============================================================================

def cmd_compare_marketplaces(args):
    """Compare two marketplaces directly showing overlap and unique content."""
    marketplace_a = args.marketplace_a
    marketplace_b = args.marketplace_b

    # Find marketplace paths
    mp_a_path = find_marketplace_path(marketplace_a)
    if not mp_a_path:
        print(f"Marketplace not found: {marketplace_a}")
        available = [m.name for m in MARKETPLACES_DIR.iterdir() if m.is_dir()]
        print(f"Available: {', '.join(sorted(available)[:10])}...")
        sys.exit(1)

    mp_b_path = find_marketplace_path(marketplace_b)
    if not mp_b_path:
        print(f"Marketplace not found: {marketplace_b}")
        available = [m.name for m in MARKETPLACES_DIR.iterdir() if m.is_dir()]
        print(f"Available: {', '.join(sorted(available)[:10])}...")
        sys.exit(1)

    print(f"Comparing marketplaces:")
    print(f"  A: {marketplace_a} ({mp_a_path})")
    print(f"  B: {marketplace_b} ({mp_b_path})")
    print()

    # Scan both marketplaces
    print(f"Scanning marketplace A: {marketplace_a}...")
    files_a = scan_directory_for_content(mp_a_path, marketplace_a)
    print(f"Found {len(files_a)} content files in {marketplace_a}")

    print(f"Scanning marketplace B: {marketplace_b}...")
    files_b = scan_directory_for_content(mp_b_path, marketplace_b)
    print(f"Found {len(files_b)} content files in {marketplace_b}")
    print()

    # Build LSH index for marketplace A
    print("Building LSH index for marketplace A...")
    lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)

    fingerprints_a = {}
    for i, f in enumerate(files_a):
        if f.minhash:
            key = f"a_{i}"
            lsh.insert(key, f.minhash)
            fingerprints_a[key] = f

    # Query with marketplace B to find overlaps
    print("Finding overlaps with marketplace B...")

    shared_b_indices = set()
    shared_a_keys = set()
    overlap_pairs = []

    for j, f_b in enumerate(files_b):
        if f_b.minhash is None:
            continue

        matches = lsh.query(f_b.minhash)

        if matches:
            # Found overlap
            shared_b_indices.add(j)

            # Calculate best match from A
            best_sim = 0.0
            best_match_key = None

            for match_key in matches:
                if match_key in fingerprints_a:
                    f_a = fingerprints_a[match_key]
                    sim = f_b.minhash.jaccard(f_a.minhash)
                    if sim > best_sim:
                        best_sim = sim
                        best_match_key = match_key

            if best_match_key:
                shared_a_keys.add(best_match_key)
                overlap_pairs.append({
                    "file_a": fingerprints_a[best_match_key].relative_path,
                    "file_b": f_b.relative_path,
                    "similarity": round(best_sim, 3),
                })

    # Compute set statistics
    a_only_count = len(files_a) - len(shared_a_keys)
    b_only_count = len(files_b) - len(shared_b_indices)
    shared_count = len(shared_b_indices)

    total_a = len(files_a)
    total_b = len(files_b)

    # Sort overlap pairs by similarity
    overlap_pairs.sort(key=lambda x: x["similarity"], reverse=True)

    # Output Venn diagram statistics
    print(f"{'=' * 60}")
    print(f"MARKETPLACE COMPARISON: {marketplace_a} vs {marketplace_b}")
    print(f"{'=' * 60}")
    print()
    print("Venn Diagram Statistics:")
    print(f"  {marketplace_a} total files:        {total_a}")
    print(f"  {marketplace_b} total files:        {total_b}")
    print()
    print(f"  Shared (overlap):           {shared_count} files")
    print(f"    {marketplace_a} overlap %:        {shared_count/total_a*100:.1f}%" if total_a > 0 else "  A overlap %: N/A")
    print(f"    {marketplace_b} overlap %:        {shared_count/total_b*100:.1f}%" if total_b > 0 else "  B overlap %: N/A")
    print()
    print(f"  {marketplace_a} only (unique):      {a_only_count} files ({a_only_count/total_a*100:.1f}%)" if total_a > 0 else f"  {marketplace_a} only: 0 files")
    print(f"  {marketplace_b} only (unique):      {b_only_count} files ({b_only_count/total_b*100:.1f}%)" if total_b > 0 else f"  {marketplace_b} only: 0 files")
    print()

    # Edge cases
    if total_a == 0 or total_b == 0:
        print("WARNING: One or both marketplaces have no content files.")
    elif shared_count == total_a == total_b:
        print("RESULT: Identical marketplaces (100% overlap)")
    elif shared_count == 0:
        print("RESULT: Disjoint marketplaces (0% overlap)")
    else:
        print(f"RESULT: Partial overlap ({shared_count/max(total_a, total_b)*100:.1f}% of larger marketplace)")

    print()

    # Show top overlaps
    if overlap_pairs:
        top_n = min(10, len(overlap_pairs))
        print(f"Top {top_n} overlapping files (by similarity):")
        for i, pair in enumerate(overlap_pairs[:top_n], 1):
            print(f"  {i}. {pair['similarity']*100:.0f}% similar")
            print(f"     A: {pair['file_a']}")
            print(f"     B: {pair['file_b']}")
        if len(overlap_pairs) > top_n:
            print(f"  ... and {len(overlap_pairs) - top_n} more overlapping files")
    else:
        print("No overlapping files found.")

    print()

    # JSON output if requested
    if getattr(args, 'json', False):
        json_output = {
            "marketplace_a": {
                "name": marketplace_a,
                "total_files": total_a,
                "unique_files": a_only_count,
                "shared_files": len(shared_a_keys),
            },
            "marketplace_b": {
                "name": marketplace_b,
                "total_files": total_b,
                "unique_files": b_only_count,
                "shared_files": shared_count,
            },
            "overlap": {
                "shared_count": shared_count,
                "a_overlap_percentage": round(shared_count/total_a*100, 1) if total_a > 0 else 0,
                "b_overlap_percentage": round(shared_count/total_b*100, 1) if total_b > 0 else 0,
            },
            "top_overlaps": overlap_pairs[:20],
        }
        print(json.dumps(json_output, indent=2))


# ============================================================================
# COMPARE command: Compare against installed plugins
# ============================================================================

def cmd_compare(args):
    """Compare target against a baseline (installed plugins or another marketplace/plugin)."""
    parts = args.target.split("/", 1)
    marketplace_name = parts[0]
    plugin_name = parts[1] if len(parts) > 1 else None

    marketplace_path = find_marketplace_path(marketplace_name)
    if not marketplace_path:
        print(f"Marketplace not found: {marketplace_name}")
        available = [m.name for m in MARKETPLACES_DIR.iterdir() if m.is_dir()]
        print(f"Available: {', '.join(sorted(available)[:10])}...")
        sys.exit(1)

    if plugin_name:
        target_path = find_plugin_in_marketplace(marketplace_path, plugin_name)
        if not target_path:
            print(f"Plugin not found: {plugin_name} in {marketplace_name}")
            sys.exit(1)
        target_name = f"{marketplace_name}/{plugin_name}"
    else:
        target_path = marketplace_path
        target_name = marketplace_name

    baseline_spec = getattr(args, 'baseline', 'installed')
    print(f"Building index from baseline: {baseline_spec}...")

    try:
        baseline_files = load_baseline_files(baseline_spec)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if not baseline_files:
        print(f"No files found in baseline: {baseline_spec}")
        sys.exit(1)

    lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)
    for i, f in enumerate(baseline_files):
        if f.minhash:
            lsh.insert(str(i), f.minhash)

    print(f"Indexed {len(baseline_files)} files from {baseline_spec}.\n")

    print(f"Comparing: {target_name}")
    print(f"Path: {target_path}\n")

    # Scan target
    target_files = scan_directory_for_content(target_path, target_name)

    novel = []
    redundant = []
    partial = []

    for tf in target_files:
        if tf.minhash is None:
            continue

        matches = lsh.query(tf.minhash)

        if not matches:
            novel.append({"file": tf.relative_path, "status": "novel"})
        else:
            match_indices = [int(m) for m in matches]
            best_sim = 0.0
            best_match = None

            for idx in match_indices:
                if idx < len(baseline_files):
                    baseline_f = baseline_files[idx]
                    if baseline_f.minhash:
                        sim = tf.minhash.jaccard(baseline_f.minhash)
                        if sim > best_sim:
                            best_sim = sim
                            best_match = baseline_f

            if best_sim >= 0.9:
                redundant.append({
                    "file": tf.relative_path,
                    "similarity": round(best_sim, 2),
                    "similar_to": best_match.location if best_match else "unknown",
                })
            elif best_sim >= SIMILARITY_THRESHOLD:
                partial.append({
                    "file": tf.relative_path,
                    "similarity": round(best_sim, 2),
                    "similar_to": best_match.location if best_match else "unknown",
                })
            else:
                novel.append({"file": tf.relative_path, "status": "novel"})

    # Get total clusters from similarity report if it exists
    total_clusters = 0
    if SIMILARITY_REPORT.exists():
        try:
            with open(SIMILARITY_REPORT) as fh:
                report = json.load(fh)
                total_clusters = report.get("summary", {}).get("unique_clusters", 0)
        except (json.JSONDecodeError, KeyError):
            # Report may be missing, malformed, or lack expected fields
            pass

    # Perform sanity checks
    total = len(target_files)
    sanity_result = check_similarity_sanity(
        total_files=total,
        novel_count=len(novel),
        redundant_count=len(redundant),
        total_clusters=total_clusters,
    )

    # Output
    print(f"{'=' * 50}")
    print(f"COMPARISON: {target_name}")
    print(f"vs BASELINE: {baseline_spec}")
    print(f"{'=' * 50}")
    print(f"Files in target:      {total}")
    print(f"Novel (not similar):  {len(novel)} ({len(novel)/total*100:.0f}%)" if total else "Novel: 0")
    print(f"Redundant (>90% sim): {len(redundant)} ({len(redundant)/total*100:.0f}%)" if total else "Redundant: 0")
    print(f"Partial overlap:      {len(partial)}")
    print(f"Confidence:           {sanity_result.confidence}")

    if sanity_result.warnings:
        print(f"\nWARNINGS:")
        for warning in sanity_result.warnings:
            print(f"  ! {warning}")

    if args.verbose:
        if redundant:
            print(f"\nRedundant files:")
            for r in redundant[:10]:
                print(f"  {r['file']}")
                print(f"    {r['similarity']*100:.0f}% similar to {r['similar_to']}")
        if len(redundant) > 10:
            print(f"  ... and {len(redundant) - 10} more")

    print()
    if total > 0:
        ratio = len(redundant) / total
        if ratio > 0.5:
            print(f"High redundancy: >50% already exists in installed plugins.")
        elif ratio > 0.2:
            print(f"Some overlap with installed plugins ({ratio*100:.0f}%).")
        else:
            print(f"Low overlap - mostly novel content.")

    # Add JSON output support
    if getattr(args, 'json', False):
        json_output = {
            "target": target_name,
            "baseline": baseline_spec,
            "summary": {
                "total_files": total,
                "novel": len(novel),
                "redundant": len(redundant),
                "partial": len(partial),
            },
            "confidence": sanity_result.confidence,
            "warnings": sanity_result.warnings,
            "novel_files": novel,
            "redundant_files": redundant,
            "partial_files": partial,
        }
        print("\n" + json.dumps(json_output, indent=2))


# ============================================================================
# IMPACT command: Quick impact summary
# ============================================================================

def cmd_impact(args):
    """Quick impact summary."""
    parts = args.target.split("/", 1)
    marketplace_name = parts[0]
    plugin_name = parts[1] if len(parts) > 1 else None

    marketplace_path = find_marketplace_path(marketplace_name)
    if not marketplace_path:
        print(f"Marketplace not found: {marketplace_name}")
        sys.exit(1)

    if plugin_name:
        target_path = find_plugin_in_marketplace(marketplace_path, plugin_name)
        if not target_path:
            print(f"Plugin not found: {plugin_name}")
            sys.exit(1)
        target_name = f"{marketplace_name}/{plugin_name}"
    else:
        target_path = marketplace_path
        target_name = marketplace_name

    baseline_spec = getattr(args, 'baseline', 'installed')
    print(f"Analyzing: {target_name} vs {baseline_spec}...")

    try:
        baseline_files = load_baseline_files(baseline_spec)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)
    for i, f in enumerate(baseline_files):
        if f.minhash:
            lsh.insert(str(i), f.minhash)

    target_files = scan_directory_for_content(target_path, target_name)

    novel = 0
    redundant = 0

    for tf in target_files:
        if tf.minhash is None:
            continue
        matches = lsh.query(tf.minhash)
        if not matches:
            novel += 1
        else:
            best_sim = 0.0
            for m in matches:
                idx = int(m)
                if idx < len(baseline_files) and baseline_files[idx].minhash:
                    sim = tf.minhash.jaccard(baseline_files[idx].minhash)
                    best_sim = max(best_sim, sim)
            if best_sim >= 0.9:
                redundant += 1
            else:
                novel += 1

    total = len(target_files)
    print(f"\n{target_name} vs {baseline_spec}: {total} files")
    print(f"  → {novel} new, {redundant} redundant")

    if total > 0:
        if redundant / total > 0.5:
            print(f"  → High overlap with baseline")
        elif novel > redundant:
            print(f"  → Mostly new content")


# ============================================================================
# INSTALLED command: List installed plugins
# ============================================================================

def cmd_installed(args):
    """List installed plugins."""
    plugins = load_installed_plugins()

    if not plugins:
        print("No installed plugins found.")
        return

    print(f"Installed plugins: {len(plugins)}\n")

    by_marketplace = defaultdict(list)
    for p in plugins:
        by_marketplace[p.marketplace].append(p)

    for mp, mp_plugins in sorted(by_marketplace.items()):
        print(f"{mp}:")
        for p in mp_plugins:
            if args.verbose:
                print(f"  {p.name} (v{p.version})")
                print(f"    {p.install_path}")
            else:
                print(f"  {p.name}")
        print()


# ============================================================================
# FIND command: Search by capability
# ============================================================================

def parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from markdown."""
    if not content.startswith("---"):
        return {}
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return {}
    try:
        return yaml.safe_load(content[3:3 + end_match.start()]) or {}
    except yaml.YAMLError:
        return {}


def scan_capabilities(marketplace_path: Path) -> list[Capability]:
    """Scan marketplace for skills and agents."""
    capabilities = []
    marketplace_name = marketplace_path.name

    for md_file in marketplace_path.rglob("*.md"):
        if "backup" in str(md_file).lower():
            continue

        parts = md_file.parts
        if "skills" in parts:
            kind = "skill"
        elif "agents" in parts:
            kind = "agent"
        else:
            continue

        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        if len(content) < 50:
            continue

        frontmatter = parse_frontmatter(content)

        name = md_file.stem
        if name == "SKILL":
            name = md_file.parent.name

        description = frontmatter.get("description", "")
        if isinstance(description, list):
            description = " ".join(description)

        if not description:
            content_body = content
            if content.startswith("---"):
                end_match = re.search(r"\n---\s*\n", content[3:])
                if end_match:
                    content_body = content[3 + end_match.end():]
            for line in content_body.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    description = line[:200]
                    break

        rel_path = md_file.relative_to(marketplace_path)
        plugin = "root"
        if "plugins" in parts:
            idx = parts.index("plugins")
            if idx + 1 < len(parts):
                plugin = parts[idx + 1]
        elif len(rel_path.parts) > 1:
            plugin = rel_path.parts[0]

        capabilities.append(Capability(
            name=name,
            kind=kind,
            description=description,
            marketplace=marketplace_name,
            plugin=plugin,
            path=str(rel_path),
        ))

    return capabilities


def cmd_find(args):
    """Search for capabilities."""
    print(f"Scanning marketplaces...")
    all_caps = []
    for mp in sorted(MARKETPLACES_DIR.iterdir()):
        if not mp.is_dir() or mp.name.startswith("."):
            continue
        caps = scan_capabilities(mp)
        all_caps.extend(caps)

    print(f"Found {len(all_caps)} skills and agents.\n")
    print(f"Searching for: {args.query}\n")

    results = []
    for cap in all_caps:
        matches, score = cap.matches(args.query)
        if matches:
            results.append((cap, score))

    results.sort(key=lambda x: x[1], reverse=True)

    if not results:
        print(f"No capabilities found matching: {args.query}")
        return

    print(f"Found {len(results)} matches:\n")

    by_marketplace = defaultdict(list)
    for cap, score in results[:30]:
        by_marketplace[cap.marketplace].append((cap, score))

    for mp, mp_results in sorted(by_marketplace.items()):
        print(f"{mp}:")
        for cap, score in mp_results:
            icon = "📘" if cap.kind == "skill" else "🤖"
            desc = cap.description[:60] + "..." if len(cap.description) > 60 else cap.description
            print(f"  {icon} {cap.name} ({cap.plugin})")
            if desc:
                print(f"      {desc}")
        print()


# ============================================================================
# STATS command: Show index statistics
# ============================================================================

def cmd_stats(args):
    """Show index statistics."""
    if not SIMILARITY_REPORT.exists():
        print(f"Error: Index not found. Run 'librarian scan' first.")
        sys.exit(1)

    index = LocationIndex()
    index.build_from_report(SIMILARITY_REPORT)

    print(f"Location Index Statistics")
    print(f"{'=' * 40}")
    print(f"Total files scanned:     {index.total_files}")
    print(f"Total clusters indexed:  {index.total_clusters}")
    print(f"Unique filenames:        {len(index.by_filename)}")
    print(f"Marketplaces covered:    {len(index.by_marketplace)}")

    print(f"\nMost common filenames in clusters:")
    filename_counts = [(fn, len(cids)) for fn, cids in index.by_filename.items()]
    filename_counts.sort(key=lambda x: x[1], reverse=True)
    for fn, count in filename_counts[:10]:
        print(f"  {fn}: {count} clusters")

    by_type = defaultdict(int)
    for cluster in index.clusters.values():
        by_type[cluster.cluster_type] += 1

    print(f"\nClusters by type:")
    for ctype, count in sorted(by_type.items()):
        print(f"  {ctype}: {count}")


# ============================================================================
# DESCRIBE command: Skill introspection
# ============================================================================

def find_skill_file(spec: str) -> tuple[Path, str, str] | None:
    """Find a skill file by spec.

    Args:
        spec: One of:
            - skill_name (searches all marketplaces)
            - marketplace/skill_name
            - marketplace/plugin/skill_name
            - full path

    Returns:
        Tuple of (file_path, marketplace, plugin) or None if not found
    """
    # Try as direct path first
    direct_path = Path(spec)
    if direct_path.exists() and direct_path.suffix == ".md":
        # Extract marketplace/plugin from path if possible
        parts = direct_path.parts
        marketplace = "local"
        plugin = "unknown"
        if "marketplaces" in parts:
            idx = parts.index("marketplaces")
            if idx + 1 < len(parts):
                marketplace = parts[idx + 1]
            if "plugins" in parts:
                pidx = parts.index("plugins")
                if pidx + 1 < len(parts):
                    plugin = parts[pidx + 1]
        return direct_path, marketplace, plugin

    parts = spec.split("/")

    if len(parts) == 1:
        # Just skill name - search all marketplaces
        skill_name = parts[0]
        for mp in sorted(MARKETPLACES_DIR.iterdir()):
            if not mp.is_dir() or mp.name.startswith("."):
                continue
            # Look in skills directories
            for skill_file in mp.rglob("*.md"):
                if skill_file.stem.lower() == skill_name.lower():
                    if "skills" in str(skill_file) or "agents" in str(skill_file):
                        rel_parts = skill_file.relative_to(mp).parts
                        plugin = "root"
                        if "plugins" in rel_parts:
                            pidx = rel_parts.index("plugins")
                            if pidx + 1 < len(rel_parts):
                                plugin = rel_parts[pidx + 1]
                        return skill_file, mp.name, plugin
        return None

    elif len(parts) == 2:
        # marketplace/skill_name
        marketplace_name, skill_name = parts
        mp_path = find_marketplace_path(marketplace_name)
        if not mp_path:
            return None
        for skill_file in mp_path.rglob("*.md"):
            if skill_file.stem.lower() == skill_name.lower():
                if "skills" in str(skill_file) or "agents" in str(skill_file):
                    rel_parts = skill_file.relative_to(mp_path).parts
                    plugin = "root"
                    if "plugins" in rel_parts:
                        pidx = rel_parts.index("plugins")
                        if pidx + 1 < len(rel_parts):
                            plugin = rel_parts[pidx + 1]
                    return skill_file, marketplace_name, plugin
        return None

    else:
        # marketplace/plugin/skill_name or longer path
        marketplace_name = parts[0]
        mp_path = find_marketplace_path(marketplace_name)
        if not mp_path:
            return None

        # Try exact path reconstruction
        remaining = "/".join(parts[1:])
        if not remaining.endswith(".md"):
            remaining += ".md"

        # Try various locations
        candidates = [
            mp_path / remaining,
            mp_path / "plugins" / remaining,
            mp_path / "plugins" / parts[1] / "skills" / (parts[-1] + ".md" if not parts[-1].endswith(".md") else parts[-1]),
            mp_path / "plugins" / parts[1] / "agents" / (parts[-1] + ".md" if not parts[-1].endswith(".md") else parts[-1]),
        ]

        for candidate in candidates:
            if candidate.exists():
                plugin = parts[1] if len(parts) > 2 else "root"
                return candidate, marketplace_name, plugin

        # Fallback: search within marketplace/plugin
        if len(parts) >= 2:
            plugin_name = parts[1]
            plugin_path = find_plugin_in_marketplace(mp_path, plugin_name)
            if plugin_path:
                skill_name = parts[-1].replace(".md", "")
                for skill_file in plugin_path.rglob("*.md"):
                    if skill_file.stem.lower() == skill_name.lower():
                        return skill_file, marketplace_name, plugin_name

        return None


def analyze_skill_content(content: str) -> dict:
    """Analyze skill content for complexity indicators.

    Returns dict with:
        - tool_uses: list of tools mentioned
        - dependencies: list of dependencies
        - triggers: list of trigger phrases
        - complexity_score: low/medium/high
    """
    # Tool names to look for (as word boundaries)
    tool_names = [
        'Bash', 'Read', 'Write', 'Edit', 'Glob',
        'Grep', 'Task', 'WebFetch', 'WebSearch',
        'TodoWrite', 'AskUserQuestion', 'MCP', 'mcp-cli',
    ]
    tools_found = []
    for tool_name in tool_names:
        # Build word-boundary pattern for each tool
        pattern = rf'\b{re.escape(tool_name)}\b'
        if re.search(pattern, content, re.IGNORECASE):
            if tool_name not in tools_found:
                tools_found.append(tool_name)

    # Extract trigger phrases from "Use this skill when" patterns
    triggers = []
    trigger_patterns = [
        r'[Uu]se this (?:skill|agent) when[^.]*\.',
        r'[Tt]rigger(?:s|ed)? (?:by|when|with)[^.]*\.',
        r'[Uu]se for[^.]*\.',
    ]
    for pattern in trigger_patterns:
        matches = re.findall(pattern, content)
        triggers.extend(matches[:3])  # Limit to 3 per pattern

    # Look for dependency indicators
    dependencies = []
    dep_patterns = [
        r'[Rr]equires? ([a-zA-Z0-9_-]+)',
        r'[Dd]epends? on ([a-zA-Z0-9_-]+)',
        r'[Nn]eeds? ([a-zA-Z0-9_-]+)',
    ]
    for pattern in dep_patterns:
        matches = re.findall(pattern, content)
        for match in matches[:5]:
            if match.lower() not in ['the', 'a', 'an', 'to', 'be']:
                dependencies.append(match)

    # Calculate complexity score
    line_count = len(content.splitlines())
    word_count = len(content.split())

    complexity = "low"
    if line_count > 200 or word_count > 1500 or len(tools_found) > 5:
        complexity = "high"
    elif line_count > 80 or word_count > 600 or len(tools_found) > 2:
        complexity = "medium"

    return {
        "tool_uses": tools_found,
        "dependencies": list(set(dependencies)),
        "triggers": triggers,
        "complexity_score": complexity,
        "line_count": line_count,
        "word_count": word_count,
    }


def parse_skill_file(file_path: Path, marketplace: str, plugin: str) -> SkillInfo:
    """Parse a skill file and return SkillInfo."""
    content = file_path.read_text(encoding="utf-8", errors="replace")

    # Determine kind from path
    kind = "skill"
    if "agents" in str(file_path):
        kind = "agent"

    # Parse frontmatter
    frontmatter = parse_frontmatter(content)
    has_frontmatter = bool(frontmatter)

    # Extract name
    name = frontmatter.get("name", file_path.stem)

    # Extract description
    description = frontmatter.get("description", "")
    if isinstance(description, list):
        description = " ".join(description)

    if not description:
        # Try to extract from content
        body = content
        if content.startswith("---"):
            end_match = re.search(r"\n---\s*\n", content[3:])
            if end_match:
                body = content[3 + end_match.end():]

        for line in body.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-") and len(line) > 20:
                description = line[:300]
                break

    # Analyze content
    analysis = analyze_skill_content(content)

    # Get triggers from frontmatter if available
    fm_triggers = frontmatter.get("triggers", [])
    if isinstance(fm_triggers, str):
        fm_triggers = [fm_triggers]
    all_triggers = fm_triggers + analysis["triggers"]

    return SkillInfo(
        name=name,
        kind=kind,
        marketplace=marketplace,
        plugin=plugin,
        path=str(file_path.relative_to(MARKETPLACES_DIR)) if str(file_path).startswith(str(MARKETPLACES_DIR)) else str(file_path),
        description=description,
        triggers=all_triggers[:5],  # Limit
        dependencies=analysis["dependencies"],
        tool_uses=analysis["tool_uses"],
        line_count=analysis["line_count"],
        word_count=analysis["word_count"],
        complexity_score=analysis["complexity_score"],
        has_frontmatter=has_frontmatter,
        raw_frontmatter=frontmatter,
    )


def cmd_describe(args):
    """Describe a skill or agent."""
    result = find_skill_file(args.skill_spec)

    if not result:
        print(f"Skill not found: {args.skill_spec}")
        print(f"\nTry:")
        print(f"  librarian describe <skill_name>")
        print(f"  librarian describe <marketplace>/<skill_name>")
        print(f"  librarian describe <marketplace>/<plugin>/<skill_name>")
        sys.exit(1)

    file_path, marketplace, plugin = result
    skill_info = parse_skill_file(file_path, marketplace, plugin)

    if getattr(args, 'json', False):
        print(json.dumps(skill_info.to_dict(), indent=2))
        return

    # Formatted output
    icon = "📘" if skill_info.kind == "skill" else "🤖"
    print(f"\n{icon} {skill_info.name}")
    print(f"{'=' * 50}")
    print(f"Type:        {skill_info.kind}")
    print(f"Location:    {skill_info.marketplace}/{skill_info.plugin}")
    print(f"Path:        {skill_info.path}")
    print(f"Complexity:  {skill_info.complexity_score}")
    print(f"Size:        {skill_info.line_count} lines, {skill_info.word_count} words")

    if skill_info.description:
        print(f"\nDescription:")
        # Word wrap description at word boundaries
        wrapped = textwrap.wrap(skill_info.description, width=70)
        for line in wrapped:
            print(f"  {line}")

    if skill_info.triggers:
        print(f"\nTriggers:")
        for trigger in skill_info.triggers:
            print(f"  - {trigger[:80]}{'...' if len(trigger) > 80 else ''}")

    if skill_info.tool_uses:
        print(f"\nTools used:")
        print(f"  {', '.join(skill_info.tool_uses)}")

    if skill_info.dependencies:
        print(f"\nDependencies:")
        for dep in skill_info.dependencies:
            print(f"  - {dep}")

    if args.verbose and skill_info.raw_frontmatter:
        print(f"\nFrontmatter:")
        for key, value in skill_info.raw_frontmatter.items():
            if key not in ['name', 'description', 'triggers']:
                val_str = str(value)[:60]
                print(f"  {key}: {val_str}{'...' if len(str(value)) > 60 else ''}")

    print()


# ============================================================================
# SCAN command: Build similarity index
# ============================================================================

def cmd_scan(args):
    """Scan marketplaces and build similarity index."""
    from datasketch import MinHash, MinHashLSH
    from .core import tokenize, compute_minhash, FileInfo

    ensure_data_dir()

    print(f"Scanning marketplaces in {MARKETPLACES_DIR}...")
    print(f"Similarity threshold: {SIMILARITY_THRESHOLD * 100:.0f}%\n")

    files = []
    for mp in sorted(MARKETPLACES_DIR.iterdir()):
        if not mp.is_dir() or mp.name.startswith("."):
            continue

        for md_file in mp.rglob("*.md"):
            if "backup" in str(md_file).lower():
                continue

            rel_to_mp = md_file.relative_to(mp)
            parts = rel_to_mp.parts

            plugin = "root"
            if "plugins" in parts:
                idx = parts.index("plugins")
                if idx + 1 < len(parts):
                    plugin = parts[idx + 1]
            elif len(parts) > 1:
                plugin = parts[0]

            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
                if len(content) < 100:
                    continue

                files.append(FileInfo(
                    marketplace=mp.name,
                    plugin=plugin,
                    relative_path=str(rel_to_mp),
                    full_path=str(md_file),
                    content=content,
                ))
            except Exception:
                pass

    print(f"Found {len(files)} content files (>100 chars)")

    print("Building MinHash signatures...")
    lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)

    # Track diagnostic info
    files_indexed = 0
    files_skipped = 0
    empty_shingles = []

    for i, f in enumerate(files):
        shingles = tokenize(f.content)
        if shingles:
            f.minhash = compute_minhash(shingles)
            lsh.insert(str(i), f.minhash)
            files_indexed += 1
        else:
            files_skipped += 1
            empty_shingles.append(f"{f.marketplace}/{f.plugin}/{f.relative_path}")

    print(f"Indexed {files_indexed} files into LSH")
    if files_skipped > 0:
        print(f"Skipped {files_skipped} files with empty shingles")
        if files_skipped <= 10:
            for path in empty_shingles:
                print(f"  - {path}")

    print("Finding similarity clusters...")
    assigned = set()
    clusters = []

    for i, f in enumerate(files):
        if i in assigned or f.minhash is None:
            continue

        result = lsh.query(f.minhash)
        similar_indices = [int(r) for r in result]

        if len(similar_indices) > 1:
            cluster_files = [files[j] for j in similar_indices if files[j].minhash is not None]

            similarities = []
            for j, f1 in enumerate(cluster_files):
                for f2 in cluster_files[j+1:]:
                    sim = f1.minhash.jaccard(f2.minhash)
                    similarities.append(sim)

            avg_sim = sum(similarities) / len(similarities) if similarities else 0

            marketplaces = set(f.marketplace for f in cluster_files)
            is_internal = len(marketplaces) == 1
            is_scaffold = is_internal and len(cluster_files) >= 5 and avg_sim >= 0.98

            if is_scaffold:
                cluster_type = "scaffold"
            elif is_internal:
                cluster_type = "internal"
            else:
                cluster_type = "cross-marketplace"

            clusters.append({
                "type": cluster_type,
                "size": len(cluster_files),
                "avg_similarity": round(avg_sim, 3),
                "has_official": any(f.is_official for f in cluster_files),
                "marketplaces": sorted(marketplaces),
                "locations": [
                    {
                        "marketplace": f.marketplace,
                        "plugin": f.plugin,
                        "path": f.relative_path,
                        "is_official": f.is_official,
                    }
                    for f in cluster_files
                ],
            })

            assigned.update(similar_indices)

    clusters.sort(key=lambda c: c["size"], reverse=True)

    by_type = defaultdict(list)
    for c in clusters:
        by_type[c["type"]].append(c)

    total_in_clusters = sum(c["size"] for c in clusters)
    unclustered = len(files) - total_in_clusters

    # Perform sanity checks on scan results
    sanity_result = check_similarity_sanity(
        total_files=len(files),
        novel_count=unclustered,
        redundant_count=total_in_clusters,
        total_clusters=len(clusters),
    )

    output = {
        "summary": {
            "total_files_scanned": len(files),
            "files_in_clusters": total_in_clusters,
            "unique_clusters": len(clusters),
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "confidence": sanity_result.confidence,
            "warnings": sanity_result.warnings,
            "by_type": {
                ctype: {
                    "clusters": len(by_type.get(ctype, [])),
                    "files": sum(c["size"] for c in by_type.get(ctype, [])),
                }
                for ctype in ["cross-marketplace", "internal", "scaffold"]
            },
        },
        "clusters": clusters,
    }

    with open(SIMILARITY_REPORT, "w") as fh:
        json.dump(output, fh, indent=2)

    print(f"\n{'=' * 50}")
    print("SCAN COMPLETE")
    print(f"{'=' * 50}")
    print(f"Total files: {len(files)}")
    print(f"Files in clusters: {total_in_clusters}")
    print(f"Clusters: {len(clusters)}")
    print(f"Confidence: {sanity_result.confidence}")

    if sanity_result.warnings:
        print(f"\nWARNINGS:")
        for warning in sanity_result.warnings:
            print(f"  ! {warning}")

    print(f"\nReport saved to: {SIMILARITY_REPORT}")


# ============================================================================
# Main entry point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Plugin Librarian: Navigate the Claude Code plugin ecosystem"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # scan
    subparsers.add_parser("scan", help="Scan marketplaces and build similarity index")

    # where
    where_p = subparsers.add_parser("where", help="Find locations of similar files")
    where_p.add_argument("query", help="Filename or pattern")

    # compare-marketplaces
    compare_mp_p = subparsers.add_parser("compare-marketplaces",
                                          help="Compare two marketplaces directly (A vs B)")
    compare_mp_p.add_argument("--marketplace-a", "-a", required=True,
                              help="First marketplace to compare")
    compare_mp_p.add_argument("--marketplace-b", "-b", required=True,
                              help="Second marketplace to compare")
    compare_mp_p.add_argument("--json", action="store_true",
                              help="Output results as JSON")

    # compare
    compare_p = subparsers.add_parser("compare", help="Compare against a baseline")
    compare_p.add_argument("target", help="marketplace or marketplace/plugin")
    compare_p.add_argument("--baseline", "-b", default="installed",
                           help="Baseline: 'installed', marketplace, or marketplace/plugin (default: installed)")
    compare_p.add_argument("-v", "--verbose", action="store_true")
    compare_p.add_argument("--json", action="store_true", help="Output results as JSON")

    # impact
    impact_p = subparsers.add_parser("impact", help="Quick impact summary")
    impact_p.add_argument("target", help="marketplace or marketplace/plugin")
    impact_p.add_argument("--baseline", "-b", default="installed",
                           help="Baseline: 'installed', marketplace, or marketplace/plugin (default: installed)")

    # installed
    installed_p = subparsers.add_parser("installed", help="List installed plugins")
    installed_p.add_argument("-v", "--verbose", action="store_true")

    # find
    find_p = subparsers.add_parser("find", help="Search by capability")
    find_p.add_argument("query", help="Capability to search for")

    # stats
    subparsers.add_parser("stats", help="Show index statistics")

    # checkout
    checkout_p = subparsers.add_parser("checkout", help="Copy a skill/agent to local directory")
    checkout_p.add_argument("skill", help="Skill spec: skill_name, marketplace/skill, or marketplace/plugin/skill")
    checkout_p.add_argument("--dir", "-d", default=None, help="Destination directory (default: current)")
    checkout_p.add_argument("--flat", "-f", action="store_true", help="Flatten directory structure")

    # describe
    describe_p = subparsers.add_parser("describe", help="Describe a skill or agent")
    describe_p.add_argument("skill_spec", help="Skill name, marketplace/skill, or marketplace/plugin/skill")
    describe_p.add_argument("-v", "--verbose", action="store_true", help="Show all frontmatter fields")
    describe_p.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan(args)
    elif args.command == "where":
        cmd_where(args)
    elif args.command == "compare-marketplaces":
        cmd_compare_marketplaces(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "impact":
        cmd_impact(args)
    elif args.command == "installed":
        cmd_installed(args)
    elif args.command == "find":
        cmd_find(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "checkout":
        cmd_checkout(args)
    elif args.command == "describe":
        cmd_describe(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
