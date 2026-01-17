"""Core functionality shared across librarian commands."""

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from datasketch import MinHash, MinHashLSH


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
    """Convert text to set of shingles."""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)

    words = text.split()
    if len(words) < SHINGLE_SIZE:
        return set(words)

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
