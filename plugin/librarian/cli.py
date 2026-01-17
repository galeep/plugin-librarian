#!/usr/bin/env python3
"""Plugin Librarian CLI: Navigate the Claude Code plugin ecosystem."""

import argparse
import fnmatch
import json
import re
import sys
from collections import defaultdict
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

    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan(args)
    elif args.command == "where":
        cmd_where(args)
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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
