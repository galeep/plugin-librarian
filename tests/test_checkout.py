#!/usr/bin/env python3
"""Tests for checkout command functionality."""

import json
import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))

from librarian.checkout import find_skill_path, checkout_skill


def test_checkout_single_file():
    """Test checking out a single skill file."""
    # Find a known skill
    skill_path = find_skill_path("anthropic-agent-skills/theme-factory")

    if not skill_path or not skill_path.exists():
        print("Skipping test - theme-factory skill not found")
        return

    print(f"Found skill at: {skill_path}")

    # Checkout to temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "test-checkout"

        result = checkout_skill(skill_path, dest, preserve_structure=True)

        assert result.success, f"Checkout failed: {result.message}"
        assert len(result.files_copied) > 0, "No files were copied"
        assert result.target_path == dest
        assert (dest / ".librarian-checkout.json").exists(), "Metadata file not created"

        # Verify metadata
        with open(dest / ".librarian-checkout.json") as fh:
            metadata = json.load(fh)

        assert "_checkout" in metadata
        assert "source" in metadata["_checkout"]
        assert "timestamp" in metadata["_checkout"]
        assert "files_copied" in metadata["_checkout"]
        assert metadata["_checkout"]["files_copied"] == len(result.files_copied)

        print(f"  Checked out {len(result.files_copied)} files")
        print("  Metadata verified")
        print("Test passed: checkout_single_file")


def test_checkout_preserves_frontmatter():
    """Test that frontmatter is extracted during checkout."""
    skill_path = find_skill_path("anthropic-agent-skills/theme-factory")

    if not skill_path or not skill_path.exists():
        print("Skipping test - theme-factory skill not found")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "test-frontmatter"

        result = checkout_skill(skill_path, dest)

        assert result.success
        assert result.metadata is not None

        # Check if any frontmatter was extracted
        non_checkout_keys = [k for k in result.metadata.keys() if k != "_checkout"]
        if non_checkout_keys:
            print(f"  Extracted frontmatter keys: {non_checkout_keys}")

        print("Test passed: checkout_preserves_frontmatter")


def test_checkout_flat_mode():
    """Test checkout with flat file structure."""
    skill_path = find_skill_path("anthropic-agent-skills/theme-factory")

    if not skill_path or not skill_path.exists():
        print("Skipping test - theme-factory skill not found")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "test-flat"

        result = checkout_skill(skill_path, dest, preserve_structure=False)

        assert result.success
        assert len(result.files_copied) > 0

        # In flat mode, all files should be in the root directory (no subdirs)
        import os
        for file_path in result.files_copied:
            assert os.sep not in file_path and "/" not in file_path, f"File not in flat structure: {file_path}"

        print(f"  Copied {len(result.files_copied)} files to flat structure")
        print("Test passed: checkout_flat_mode")


def test_find_skill_by_name():
    """Test finding a skill by just its name."""
    # Try to find theme-factory by name only
    skill_path = find_skill_path("theme-factory")

    if skill_path and skill_path.exists():
        print(f"  Found skill: {skill_path}")
        assert "theme-factory" in str(skill_path).lower()
        print("Test passed: find_skill_by_name")
    else:
        print("Skipping test - theme-factory not found")


def test_find_skill_full_path():
    """Test finding skill with full path specification."""
    skill_path = find_skill_path("anthropic-agent-skills/plugins/theme-factory")

    # This might not exist depending on directory structure
    # Just verify the function doesn't crash
    print(f"  Full path search result: {skill_path}")
    print("Test passed: find_skill_full_path")


def test_checkout_nonexistent_skill():
    """Test that checkout fails gracefully for nonexistent skills."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "test-nonexistent"

        # Try to checkout a nonexistent path
        result = checkout_skill(Path("/nonexistent/path"), dest)

        assert not result.success, "Checkout should have failed"
        assert "does not exist" in result.message.lower()
        print("  Correctly handled nonexistent path")
        print("Test passed: checkout_nonexistent_skill")


if __name__ == "__main__":
    print("Running checkout tests...\n")

    test_checkout_single_file()
    test_checkout_preserves_frontmatter()
    test_checkout_flat_mode()
    test_find_skill_by_name()
    test_find_skill_full_path()
    test_checkout_nonexistent_skill()

    print("\nAll checkout tests passed!")
