"""Checkout functionality for copying skills/agents to local directories."""

import json
import re
import shutil
import yaml
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .core import find_marketplace_path, find_plugin_in_marketplace, MARKETPLACES_DIR


@dataclass
class CheckoutResult:
    """Result of a checkout operation."""
    success: bool
    target_path: Path
    files_copied: list[str]
    metadata: dict
    message: str


def find_skill_path(skill_spec: str) -> Optional[Path]:
    """Find a skill/agent path from a specification.

    Args:
        skill_spec: One of:
            - marketplace/plugin/skill_name
            - marketplace/skill_name (searches skills/ and agents/ directories)
            - skill_name (searches all marketplaces)

    Returns:
        Path to the skill directory or file, or None if not found
    """
    parts = skill_spec.split("/")

    if len(parts) >= 3:
        # Full path: marketplace/plugin/skill_name
        marketplace_name, plugin_name, skill_name = parts[0], parts[1], "/".join(parts[2:])
        marketplace_path = find_marketplace_path(marketplace_name)
        if not marketplace_path:
            return None

        plugin_path = find_plugin_in_marketplace(marketplace_path, plugin_name)
        if not plugin_path:
            return None

        # Look for skill in skills/ or agents/ directory
        for subdir in ["skills", "agents"]:
            skill_path = plugin_path / subdir / skill_name
            if skill_path.exists():
                return skill_path
            # Try as .md file
            skill_file = plugin_path / subdir / f"{skill_name}.md"
            if skill_file.exists():
                return skill_file

        return None

    elif len(parts) == 2:
        # marketplace/skill_name - search in marketplace root
        marketplace_name, skill_name = parts
        marketplace_path = find_marketplace_path(marketplace_name)
        if not marketplace_path:
            return None

        # Search in skills/ and agents/ directories
        for subdir in ["skills", "agents"]:
            skills_dir = marketplace_path / subdir
            if skills_dir.exists():
                # Look for directory
                skill_path = skills_dir / skill_name
                if skill_path.exists():
                    return skill_path
                # Look for file
                skill_file = skills_dir / f"{skill_name}.md"
                if skill_file.exists():
                    return skill_file

        return None

    else:
        # Single name - search all marketplaces
        skill_name = parts[0]
        if not MARKETPLACES_DIR.exists():
            return None
        for mp in sorted(MARKETPLACES_DIR.iterdir()):
            if not mp.is_dir() or mp.name.startswith("."):
                continue

            for subdir in ["skills", "agents"]:
                skills_dir = mp / subdir
                if skills_dir.exists():
                    skill_path = skills_dir / skill_name
                    if skill_path.exists():
                        return skill_path
                    skill_file = skills_dir / f"{skill_name}.md"
                    if skill_file.exists():
                        return skill_file

        return None


def checkout_skill(
    skill_path: Path,
    destination: Path,
    preserve_structure: bool = True
) -> CheckoutResult:
    """Checkout (copy) a skill or agent to a local directory.

    Args:
        skill_path: Path to the skill/agent in marketplace
        destination: Where to copy the skill
        preserve_structure: If True, preserve directory structure from marketplace

    Returns:
        CheckoutResult with status and details
    """
    if not skill_path.exists():
        return CheckoutResult(
            success=False,
            target_path=destination,
            files_copied=[],
            metadata={},
            message=f"Source path does not exist: {skill_path}"
        )

    files_copied = []
    metadata = {}

    try:
        # Create destination directory
        destination.mkdir(parents=True, exist_ok=True)

        if skill_path.is_file():
            # Single file checkout
            target_file = destination / skill_path.name
            # Validate target stays within destination
            try:
                target_file.resolve().relative_to(destination.resolve())
            except ValueError:
                return CheckoutResult(
                    success=False,
                    target_path=destination,
                    files_copied=[],
                    metadata={},
                    message=f"Invalid target path: would escape destination directory"
                )
            shutil.copy2(skill_path, target_file)
            files_copied.append(str(target_file.relative_to(destination)))

            # Extract metadata if it's a markdown file
            if skill_path.suffix == ".md":
                content = skill_path.read_text(encoding="utf-8", errors="replace")
                if content.startswith("---"):
                    end_match = re.search(r"\n---\s*\n", content[3:])
                    if end_match:
                        try:
                            metadata = yaml.safe_load(content[3:3 + end_match.start()]) or {}
                        except yaml.YAMLError:
                            pass
        else:
            # Directory checkout
            for item in skill_path.rglob("*"):
                if not item.is_file():
                    continue
                # Check for hidden files/dirs relative to skill_path only
                rel_path = item.relative_to(skill_path)
                if any(part.startswith(".") for part in rel_path.parts):
                    continue

                if preserve_structure:
                    target_file = destination / rel_path
                    # Validate path stays within destination (prevent traversal)
                    try:
                        target_file.resolve().relative_to(destination.resolve())
                    except ValueError:
                        continue  # Skip files that would escape destination
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                else:
                    target_file = destination / item.name
                    # Validate path stays within destination (prevent traversal)
                    try:
                        target_file.resolve().relative_to(destination.resolve())
                    except ValueError:
                        continue  # Skip files that would escape destination
                    # In flat mode, track seen names to warn about overwrites
                    if target_file.exists():
                        # File already copied, skip duplicate
                        continue

                shutil.copy2(item, target_file)
                files_copied.append(str(target_file.relative_to(destination)))

            # Try to extract metadata from SKILL.md or main file
            skill_md = skill_path / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text(encoding="utf-8", errors="replace")
                if content.startswith("---"):
                    end_match = re.search(r"\n---\s*\n", content[3:])
                    if end_match:
                        try:
                            metadata = yaml.safe_load(content[3:3 + end_match.start()]) or {}
                        except yaml.YAMLError:
                            pass

        # Add checkout metadata
        metadata["_checkout"] = {
            "source": str(skill_path),
            "timestamp": datetime.now().isoformat(),
            "files_copied": len(files_copied),
        }

        # Write metadata file
        metadata_file = destination / ".librarian-checkout.json"
        with open(metadata_file, "w") as fh:
            json.dump(metadata, fh, indent=2)

        return CheckoutResult(
            success=True,
            target_path=destination,
            files_copied=files_copied,
            metadata=metadata,
            message=f"Successfully checked out {len(files_copied)} file(s) to {destination}"
        )

    except Exception as e:
        return CheckoutResult(
            success=False,
            target_path=destination,
            files_copied=files_copied,
            metadata=metadata,
            message=f"Checkout failed: {str(e)}"
        )
