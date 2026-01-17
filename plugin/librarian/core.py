"""Core functionality shared across librarian commands."""

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from datasketch import MinHash, MinHashLSH
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    TimeElapsedColumn,
)


# Paths
PLUGINS_DIR = Path.home() / ".claude" / "plugins"
INSTALLED_PLUGINS_JSON = PLUGINS_DIR / "installed_plugins.json"
MARKETPLACES_DIR = PLUGINS_DIR / "marketplaces"

# MinHash parameters
SIMILARITY_THRESHOLD = 0.7
NUM_PERM = 128
SHINGLE_SIZE = 3


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
    def filename(self) -> str:
        return Path(self.relative_path).name

    @property
    def is_official(self) -> bool:
        return self.marketplace.startswith(("anthropic", "claude-plugins-official"))


@dataclass
class Location:
    """A specific file location in the ecosystem."""
    marketplace: str
    plugin: str
    path: str
    is_official: bool

    @property
    def filename(self) -> str:
        return Path(self.path).name

    @property
    def full_key(self) -> str:
        return f"{self.marketplace}/{self.plugin}/{self.path}"


@dataclass
class ClusterInfo:
    """Summary of a similarity cluster."""
    cluster_id: int
    cluster_type: str
    size: int
    avg_similarity: float
    has_official: bool
    marketplaces: list[str]
    locations: list[Location]


@dataclass
class InstalledPlugin:
    """A currently installed plugin."""
    name: str
    marketplace: str
    install_path: Path
    version: str


@dataclass
class Capability:
    """A skill or agent capability."""
    name: str
    kind: str
    description: str
    marketplace: str
    plugin: str
    path: str
    triggers: list[str] = field(default_factory=list)

    @property
    def full_path(self) -> str:
        return f"{self.marketplace}/{self.plugin}/{self.path}"

    def matches(self, query: str) -> tuple[bool, float]:
        query_lower = query.lower()
        query_words = set(query_lower.split())
        score = 0.0

        name_lower = self.name.lower()
        if query_lower in name_lower:
            score += 10.0
        elif any(w in name_lower for w in query_words):
            score += 5.0

        desc_lower = self.description.lower()
        if query_lower in desc_lower:
            score += 5.0
        else:
            matching_words = sum(1 for w in query_words if w in desc_lower)
            score += matching_words * 2.0

        for trigger in self.triggers:
            trigger_lower = trigger.lower()
            if query_lower in trigger_lower:
                score += 3.0
            elif any(w in trigger_lower for w in query_words):
                score += 1.0

        return score > 0, score


def tokenize(text: str) -> set[str]:
    """Convert text to set of shingles.

    Uses word-level shingles (n-grams) for content similarity detection.
    For very short documents, falls back to character-level shingles.

    Args:
        text: Input text to tokenize

    Returns:
        Set of shingles (word n-grams or character n-grams for short text)
    """
    # Normalize: lowercase and collapse whitespace
    text = text.lower()
    text = re.sub(r'\s+', ' ', text).strip()

    # DESIGN RATIONALE: Keep dashes and alphanumerics
    # Markdown files have frontmatter (key: value), code blocks, headers (#, ##)
    # Removing ALL punctuation was too aggressive and caused empty shingle sets
    # Now we keep dashes (important for YAML keys, multi-word terms)
    text = re.sub(r'[^a-z0-9\s\-]', '', text)

    # Split and filter empty strings
    words = [w for w in text.split() if w]

    # Handle short documents with fallback to character-level shingles
    if len(words) < SHINGLE_SIZE:
        if words:
            # Return individual words for very short docs
            return set(words)
        elif len(text) >= SHINGLE_SIZE:
            # Fallback: character-level shingles for docs with no words
            return set(text[i:i+SHINGLE_SIZE] for i in range(len(text) - SHINGLE_SIZE + 1))
        else:
            # Last resort: return the text itself as a single shingle
            return {text} if text else set()

    # Generate word-level shingles (n-grams)
    shingles = set()
    for i in range(len(words) - SHINGLE_SIZE + 1):
        shingle = ' '.join(words[i:i + SHINGLE_SIZE])
        shingles.add(shingle)

    return shingles


def compute_minhash(shingles: set[str]) -> MinHash:
    """Compute MinHash signature for shingles."""
    m = MinHash(num_perm=NUM_PERM)
    for s in shingles:
        m.update(s.encode('utf-8'))
    return m


def load_installed_plugins() -> list[InstalledPlugin]:
    """Load list of currently installed plugins."""
    if not INSTALLED_PLUGINS_JSON.exists():
        return []

    with open(INSTALLED_PLUGINS_JSON) as fh:
        data = json.load(fh)

    plugins = []
    for plugin_key, installs in data.get("plugins", {}).items():
        if "@" in plugin_key:
            name, marketplace = plugin_key.rsplit("@", 1)
        else:
            name = plugin_key
            marketplace = "unknown"

        for install in installs:
            install_path = Path(install.get("installPath", ""))
            if install_path.exists():
                plugins.append(InstalledPlugin(
                    name=name,
                    marketplace=marketplace,
                    install_path=install_path,
                    version=install.get("version", ""),
                ))

    return plugins


def scan_directory_for_content(directory: Path, label: str = "") -> list[FileInfo]:
    """Scan a directory for content files with MinHash signatures."""
    import sys
    files = []

    for md_file in directory.rglob("*.md"):
        if "backup" in str(md_file).lower():
            continue

        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            if len(content) < 100:
                continue

            rel_path = md_file.relative_to(directory)

            file_info = FileInfo(
                marketplace=label,
                plugin=directory.name,
                relative_path=str(rel_path),
                full_path=str(md_file),
                content=content,
            )

            shingles = tokenize(content)
            if shingles:
                file_info.minhash = compute_minhash(shingles)
                files.append(file_info)

        except Exception as err:
            print(f"Warning: Could not read {md_file}: {err}", file=sys.stderr)

    return files


def find_marketplace_path(name: str) -> Optional[Path]:
    """Find a marketplace directory by name."""
    direct = MARKETPLACES_DIR / name
    if direct.exists():
        return direct

    for mp in MARKETPLACES_DIR.iterdir():
        if mp.name.lower() == name.lower():
            return mp

    return None


def find_plugin_in_marketplace(marketplace: Path, plugin_name: str) -> Optional[Path]:
    """Find a plugin within a marketplace."""
    direct = marketplace / plugin_name
    if direct.exists():
        return direct

    plugins_dir = marketplace / "plugins"
    if plugins_dir.exists():
        direct = plugins_dir / plugin_name
        if direct.exists():
            return direct

        for category in plugins_dir.iterdir():
            if category.is_dir():
                plugin_path = category / plugin_name
                if plugin_path.exists():
                    return plugin_path

    return None


def load_baseline_files(spec: str) -> list[FileInfo]:
    """Load files from a baseline specification.

    Args:
        spec: One of:
            - "installed" - currently installed plugins
            - "marketplace" - entire marketplace
            - "marketplace/plugin" - specific plugin

    Returns:
        List of FileInfo with MinHash signatures computed.

    Raises:
        ValueError: If spec is empty, or marketplace or plugin not found.
    """
    if not spec or not spec.strip():
        raise ValueError("Baseline spec cannot be empty")

    if spec == "installed":
        plugins = load_installed_plugins()
        files = []
        for plugin in plugins:
            label = f"{plugin.name}@{plugin.marketplace}"
            files.extend(scan_directory_for_content(plugin.install_path, label))
        return files

    parts = spec.split("/", 1)
    marketplace_name = parts[0]
    plugin_name = parts[1] if len(parts) > 1 else None

    marketplace_path = find_marketplace_path(marketplace_name)
    if not marketplace_path:
        raise ValueError(f"Marketplace not found: {marketplace_name}")

    if plugin_name:
        plugin_path = find_plugin_in_marketplace(marketplace_path, plugin_name)
        if not plugin_path:
            raise ValueError(f"Plugin not found: {plugin_name} in {marketplace_name}")
        return scan_directory_for_content(plugin_path, marketplace_name)
    else:
        return scan_directory_for_content(marketplace_path, marketplace_name)


@dataclass
class SanityCheckResult:
    """Result of sanity checks on comparison results."""
    confidence: str
    warnings: list[str]

    def to_dict(self) -> dict:
        return {
            "confidence": self.confidence,
            "warnings": self.warnings,
        }


def check_similarity_sanity(
    total_files: int,
    novel_count: int,
    redundant_count: int,
    total_clusters: int = 0,
) -> SanityCheckResult:
    """Perform sanity checks on similarity analysis results.

    Args:
        total_files: Total number of files analyzed
        novel_count: Number of novel (non-similar) files
        redundant_count: Number of redundant (>90% similar) files
        total_clusters: Total number of clusters in ecosystem (for scan results)

    Returns:
        SanityCheckResult with confidence level and warnings
    """
    warnings = []
    confidence = "high"

    if total_files == 0:
        warnings.append("No files were analyzed")
        confidence = "none"
        return SanityCheckResult(confidence=confidence, warnings=warnings)

    redundant_ratio = redundant_count / total_files
    novel_ratio = novel_count / total_files

    # Check for 0% cluster membership in large ecosystems
    if total_clusters > 1000 and redundant_count == 0:
        warnings.append(
            f"0% cluster membership detected with {total_clusters} clusters in ecosystem. "
            "This is statistically improbable and may indicate an indexing issue."
        )
        confidence = "low"

    # Check for extreme ratios in larger datasets
    if total_files > 500:
        if redundant_ratio < 0.05:
            warnings.append(
                f"Very low similarity ratio ({redundant_ratio*100:.1f}%) for {total_files} files. "
                "This may indicate a mismatch between target and baseline, or an indexing issue."
            )
            if confidence == "high":
                confidence = "medium"

        if redundant_ratio > 0.95:
            warnings.append(
                f"Very high similarity ratio ({redundant_ratio*100:.1f}%) for {total_files} files. "
                "Nearly all content appears redundant, which may indicate an indexing issue."
            )
            if confidence == "high":
                confidence = "medium"

    # Check for suspiciously even splits
    if total_files > 100:
        if 0.48 <= novel_ratio <= 0.52 and 0.48 <= redundant_ratio <= 0.52:
            warnings.append(
                "Results show near-perfect 50/50 split between novel and redundant files. "
                "This pattern may indicate random classification rather than meaningful similarity."
            )
            if confidence == "high":
                confidence = "medium"

    return SanityCheckResult(confidence=confidence, warnings=warnings)


# ============================================================================
# Progress utilities for long-running operations
# ============================================================================

def create_progress_bar() -> Progress:
    """Create a standardized progress bar for librarian operations.

    Returns:
        Progress instance configured with spinner, bar, percentage, and time remaining.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        TimeElapsedColumn(),
    )


def scan_directory_for_content_with_progress(
    directory: Path,
    label: str = "",
    progress: Optional[Progress] = None,
    task_id: Optional[int] = None,
) -> list[FileInfo]:
    """Scan a directory for content files with MinHash signatures and optional progress tracking.

    Args:
        directory: Directory to scan
        label: Label for marketplace/plugin name
        progress: Optional Progress instance for tracking
        task_id: Optional task ID if using existing progress bar

    Returns:
        List of FileInfo objects with computed MinHash signatures
    """
    import sys
    files = []

    # First pass: collect all markdown files
    md_files = [
        md_file for md_file in directory.rglob("*.md")
        if "backup" not in str(md_file).lower()
    ]

    if not md_files:
        return files

    # Process files with progress tracking
    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            if len(content) < 100:
                continue

            rel_path = md_file.relative_to(directory)

            file_info = FileInfo(
                marketplace=label,
                plugin=directory.name,
                relative_path=str(rel_path),
                full_path=str(md_file),
                content=content,
            )

            shingles = tokenize(content)
            if shingles:
                file_info.minhash = compute_minhash(shingles)
                files.append(file_info)

        except Exception as err:
            print(f"Warning: Could not read {md_file}: {err}", file=sys.stderr)

        if progress and task_id is not None:
            progress.advance(task_id)

    return files


def load_baseline_files_with_progress(
    spec: str,
    progress: Optional[Progress] = None,
) -> list[FileInfo]:
    """Load files from a baseline specification with progress tracking.

    Args:
        spec: One of:
            - "installed" - currently installed plugins
            - "marketplace" - entire marketplace
            - "marketplace/plugin" - specific plugin
        progress: Optional Progress instance for tracking

    Returns:
        List of FileInfo with MinHash signatures computed.

    Raises:
        ValueError: If spec is empty, or marketplace or plugin not found.
    """
    if not spec or not spec.strip():
        raise ValueError("Baseline spec cannot be empty")

    if spec == "installed":
        plugins = load_installed_plugins()
        if not plugins:
            return []

        files = []

        if progress:
            # Count total files first for accurate progress
            total_files = 0
            for plugin in plugins:
                plugin_files = list(plugin.install_path.rglob("*.md"))
                total_files += len([f for f in plugin_files if "backup" not in str(f).lower()])

            task = progress.add_task(f"Loading baseline: {spec}", total=total_files)

            for plugin in plugins:
                label = f"{plugin.name}@{plugin.marketplace}"
                plugin_files = scan_directory_for_content_with_progress(
                    plugin.install_path, label, progress, task
                )
                files.extend(plugin_files)
        else:
            for plugin in plugins:
                label = f"{plugin.name}@{plugin.marketplace}"
                files.extend(scan_directory_for_content(plugin.install_path, label))

        return files

    parts = spec.split("/", 1)
    marketplace_name = parts[0]
    plugin_name = parts[1] if len(parts) > 1 else None

    marketplace_path = find_marketplace_path(marketplace_name)
    if not marketplace_path:
        raise ValueError(f"Marketplace not found: {marketplace_name}")

    if plugin_name:
        plugin_path = find_plugin_in_marketplace(marketplace_path, plugin_name)
        if not plugin_path:
            raise ValueError(f"Plugin not found: {plugin_name} in {marketplace_name}")
        target_path = plugin_path
    else:
        target_path = marketplace_path

    if progress:
        # Count files
        md_files = list(target_path.rglob("*.md"))
        total_files = len([f for f in md_files if "backup" not in str(f).lower()])
        task = progress.add_task(f"Loading baseline: {spec}", total=total_files)
        return scan_directory_for_content_with_progress(target_path, marketplace_name, progress, task)
    else:
        return scan_directory_for_content(target_path, marketplace_name)
