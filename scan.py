#!/usr/bin/env python3
"""
Plugin Librarian: Scan and deduplicate Claude Code plugins across marketplaces.

Hashes plugin content files, groups duplicates, identifies near-matches,
and outputs a structured catalog of unique plugins.
"""

import hashlib
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional


# Content files that define a plugin's behavior
CONTENT_PATTERNS = [
    "skills/**/SKILL.md",
    "skills/**/*.md",
    "commands/*.md",
    "agents/*.md",
    "scripts/*",
]

# Files to read for metadata (not hashed for dedup)
METADATA_FILES = [
    ".claude-plugin/plugin.json",
    "README.md",
    "LICENSE",
]

MARKETPLACES_DIR = Path.home() / ".claude" / "plugins" / "marketplaces"


@dataclass
class PluginFile:
    """A single file within a plugin."""
    relative_path: str
    content_hash: str
    size: int
    normalized_hash: str = ""  # Hash after normalizing whitespace


@dataclass
class Plugin:
    """A plugin instance from a specific marketplace."""
    name: str
    marketplace: str
    path: str
    files: list[PluginFile] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    content_hash: str = ""  # Combined hash of all content files
    normalized_hash: str = ""  # Combined hash after normalizing (for near-dupe detection)

    def compute_content_hash(self) -> str:
        """Compute combined hashes of all content files."""
        if not self.files:
            return ""
        # Sort by path for consistent ordering
        sorted_hashes = sorted(f"{f.relative_path}:{f.content_hash}" for f in self.files)
        combined = "\n".join(sorted_hashes)
        self.content_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]

        # Also compute normalized hash
        sorted_norm = sorted(f"{f.relative_path}:{f.normalized_hash}" for f in self.files)
        combined_norm = "\n".join(sorted_norm)
        self.normalized_hash = hashlib.sha256(combined_norm.encode()).hexdigest()[:16]

        return self.content_hash


@dataclass
class DuplicateGroup:
    """A group of plugins with identical content."""
    content_hash: str
    plugins: list[Plugin] = field(default_factory=list)
    canonical: Optional[Plugin] = None

    def select_canonical(self) -> Plugin:
        """Select the canonical plugin from this group."""
        if len(self.plugins) == 1:
            self.canonical = self.plugins[0]
            return self.canonical

        # Scoring criteria: prefer official marketplaces, more complete, better docs
        def score(plugin: Plugin) -> tuple:
            marketplace_priority = {
                "claude-plugins-official": 100,
                "anthropic": 90,
            }
            mp_score = marketplace_priority.get(plugin.marketplace, 50)
            file_count = len(plugin.files)
            has_readme = 1 if plugin.metadata.get("has_readme") else 0
            has_license = 1 if plugin.metadata.get("has_license") else 0
            return (mp_score, file_count, has_readme, has_license)

        self.canonical = max(self.plugins, key=score)
        return self.canonical


def normalize_content(content: str) -> str:
    """Normalize content for comparison (ignore whitespace, formatting)."""
    import re
    # Collapse all whitespace to single spaces
    normalized = re.sub(r'\s+', ' ', content)
    # Remove common formatting variations
    normalized = normalized.strip().lower()
    return normalized


def hash_file(path: Path) -> tuple[str, int, str]:
    """Hash a file and return (hash, size, normalized_hash)."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        # Also compute normalized hash for near-duplicate detection
        normalized = normalize_content(content)
        normalized_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return content_hash, len(content), normalized_hash
    except Exception as err:
        print(f"  Warning: Could not read {path}: {err}", file=sys.stderr)
        return "", 0, ""


def find_content_files(plugin_path: Path) -> list[PluginFile]:
    """Find all content files in a plugin directory."""
    files = []

    for pattern in CONTENT_PATTERNS:
        for match in plugin_path.glob(pattern):
            if match.is_file():
                content_hash, size, normalized_hash = hash_file(match)
                if content_hash:
                    files.append(PluginFile(
                        relative_path=str(match.relative_to(plugin_path)),
                        content_hash=content_hash,
                        size=size,
                        normalized_hash=normalized_hash,
                    ))

    return files


def load_plugin_metadata(plugin_path: Path) -> dict:
    """Load metadata from plugin.json and check for README/LICENSE."""
    metadata = {
        "has_readme": (plugin_path / "README.md").exists(),
        "has_license": (plugin_path / "LICENSE").exists(),
    }

    plugin_json = plugin_path / ".claude-plugin" / "plugin.json"
    if plugin_json.exists():
        try:
            with open(plugin_json) as fh:
                data = json.load(fh)
                metadata["description"] = data.get("description", "")
                metadata["version"] = data.get("version", "")
                metadata["author"] = data.get("author", "")
        except Exception:
            pass

    return metadata


def looks_like_plugin(path: Path) -> bool:
    """Check if a directory looks like a plugin (has content directories)."""
    if (path / ".claude-plugin").exists():
        return True
    # Also count as plugin if it has skills/, commands/, or agents/
    content_dirs = ["skills", "commands", "agents"]
    return any((path / d).is_dir() for d in content_dirs)


def scan_marketplace(marketplace_path: Path) -> list[Plugin]:
    """Scan a marketplace directory for plugins."""
    plugins = []
    marketplace_name = marketplace_path.name

    # Look for plugins in common locations
    plugin_dirs = []

    # Direct plugins (marketplace/plugin-name/)
    for item in marketplace_path.iterdir():
        if item.is_dir() and looks_like_plugin(item):
            plugin_dirs.append(item)

    # Nested in plugins/ directory
    plugins_subdir = marketplace_path / "plugins"
    if plugins_subdir.exists():
        for category in plugins_subdir.iterdir():
            if category.is_dir():
                # Could be category/plugin or directly plugin
                if looks_like_plugin(category):
                    plugin_dirs.append(category)
                else:
                    for item in category.iterdir():
                        if item.is_dir() and looks_like_plugin(item):
                            plugin_dirs.append(item)

    for plugin_path in plugin_dirs:
        # Skip backup directories
        if "backup" in plugin_path.parts or "backups" in plugin_path.parts:
            continue

        files = find_content_files(plugin_path)
        if not files:
            continue

        plugin = Plugin(
            name=plugin_path.name,
            marketplace=marketplace_name,
            path=str(plugin_path),
            files=files,
            metadata=load_plugin_metadata(plugin_path),
        )
        plugin.compute_content_hash()
        plugins.append(plugin)

    return plugins


def compute_similarity(content_a: str, content_b: str) -> float:
    """Compute similarity ratio between two strings."""
    return SequenceMatcher(None, content_a, content_b).ratio()


def find_near_duplicates(
    groups: list[DuplicateGroup],
    threshold: float = 0.90
) -> list[tuple[Plugin, Plugin, float]]:
    """Find plugins that are near-duplicates (similar but not identical).

    SPIKE: Disabled for initial scan. O(n^2) comparison is slow.
    """
    # TODO: Re-enable with sampling or faster algorithm
    return []


def scan_all_marketplaces() -> dict:
    """Scan all marketplaces and build the catalog."""
    if not MARKETPLACES_DIR.exists():
        print(f"Marketplaces directory not found: {MARKETPLACES_DIR}", file=sys.stderr)
        return {}

    all_plugins = []

    print(f"Scanning marketplaces in {MARKETPLACES_DIR}...")

    for marketplace_path in sorted(MARKETPLACES_DIR.iterdir()):
        if not marketplace_path.is_dir():
            continue
        if marketplace_path.name.startswith("."):
            continue

        print(f"  {marketplace_path.name}...", end=" ", flush=True)
        plugins = scan_marketplace(marketplace_path)
        print(f"{len(plugins)} plugins")
        all_plugins.extend(plugins)

    print(f"\nTotal: {len(all_plugins)} plugin instances scanned")

    # Group by exact content hash
    hash_groups: dict[str, list[Plugin]] = defaultdict(list)
    for plugin in all_plugins:
        if plugin.content_hash:
            hash_groups[plugin.content_hash].append(plugin)

    # Build duplicate groups and select canonicals
    groups = []
    for content_hash, plugins in hash_groups.items():
        group = DuplicateGroup(content_hash=content_hash, plugins=plugins)
        group.select_canonical()
        groups.append(group)

    # Sort by number of duplicates (most duplicated first)
    groups.sort(key=lambda g: len(g.plugins), reverse=True)

    # Group by NORMALIZED hash to find formatting variants
    print("\nFinding formatting variants (same content, different whitespace)...")
    norm_groups: dict[str, list[Plugin]] = defaultdict(list)
    for plugin in all_plugins:
        if plugin.normalized_hash:
            norm_groups[plugin.normalized_hash].append(plugin)

    # Count formatting variants (plugins with same normalized hash but different exact hash)
    formatting_variants = []
    for norm_hash, plugins in norm_groups.items():
        if len(plugins) > 1:
            # Check if they have different exact hashes
            exact_hashes = set(p.content_hash for p in plugins)
            if len(exact_hashes) > 1:
                formatting_variants.append((norm_hash, plugins))

    print(f"Found {len(formatting_variants)} groups of formatting variants")

    # Old near-duplicate detection (disabled)
    near_dupes = []

    # Build output catalog
    unique_count = len(groups)
    duplicate_count = sum(len(g.plugins) - 1 for g in groups)

    # Count plugins that are formatting variants
    variant_plugin_count = sum(len(plugins) for _, plugins in formatting_variants)

    catalog = {
        "summary": {
            "total_scanned": len(all_plugins),
            "unique_plugins": unique_count,
            "exact_duplicates": duplicate_count,
            "formatting_variant_groups": len(formatting_variants),
            "formatting_variant_plugins": variant_plugin_count,
            "deduplication_ratio": f"{(1 - unique_count / len(all_plugins)) * 100:.1f}%" if all_plugins else "0%",
        },
        "unique_plugins": [],
        "formatting_variants": [],
    }

    for group in groups:
        canonical = group.canonical
        entry = {
            "name": canonical.name,
            "marketplace": canonical.marketplace,
            "content_hash": group.content_hash,
            "description": canonical.metadata.get("description", ""),
            "duplicate_count": len(group.plugins) - 1,
            "duplicates_in": [
                {"name": p.name, "marketplace": p.marketplace}
                for p in group.plugins if p != canonical
            ],
        }
        catalog["unique_plugins"].append(entry)

    for norm_hash, plugins in formatting_variants:
        catalog["formatting_variants"].append({
            "normalized_hash": norm_hash,
            "plugins": [
                {"name": p.name, "marketplace": p.marketplace, "content_hash": p.content_hash}
                for p in plugins
            ],
        })

    return catalog


def main():
    catalog = scan_all_marketplaces()

    if not catalog:
        sys.exit(1)

    # Print summary
    summary = catalog["summary"]
    print(f"\n{'=' * 50}")
    print("PLUGIN LIBRARIAN SCAN COMPLETE")
    print(f"{'=' * 50}")
    print(f"Total plugin instances:    {summary['total_scanned']}")
    print(f"Unique (by exact hash):    {summary['unique_plugins']}")
    print(f"Exact duplicates:          {summary['exact_duplicates']}")
    print(f"Formatting variant groups: {summary['formatting_variant_groups']}")
    print(f"Formatting variant plugins:{summary['formatting_variant_plugins']}")
    print(f"Deduplication ratio:       {summary['deduplication_ratio']}")

    # Show most duplicated
    if catalog["unique_plugins"]:
        exact_dupes = [e for e in catalog["unique_plugins"] if e["duplicate_count"] > 0]
        if exact_dupes:
            print(f"\nExact duplicates:")
            for entry in exact_dupes[:10]:
                print(f"  {entry['name']}: {entry['duplicate_count'] + 1} copies")

    # Show formatting variants
    if catalog["formatting_variants"]:
        print(f"\nFormatting variants (same content, different whitespace):")
        for variant in catalog["formatting_variants"][:10]:
            names = [f"{p['name']}@{p['marketplace']}" for p in variant["plugins"]]
            print(f"  {', '.join(names)}")

    # Write catalog to file
    output_path = Path(__file__).parent / "catalog.json"
    with open(output_path, "w") as fh:
        json.dump(catalog, fh, indent=2)
    print(f"\nCatalog written to: {output_path}")


if __name__ == "__main__":
    main()
