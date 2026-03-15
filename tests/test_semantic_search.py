#!/usr/bin/env python3
"""Tests for semantic capability search functionality."""

import json
import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))

from librarian.core import Capability
from librarian.cli import (
    save_capability_index,
    load_capability_index,
)


def test_capability_matching():
    """Test capability matching with various query patterns."""
    # Create test capability
    cap = Capability(
        name="git-helper",
        kind="skill",
        description="Provides Git workflow assistance including commit, push, and branch management",
        marketplace="test-marketplace",
        plugin="test-plugin",
        path="skills/git-helper.md",
        triggers=["git commit", "git push", "create branch"],
    )

    # Test exact name match
    matches, score = cap.matches("git")
    assert matches, "Should match 'git' in name"
    assert score >= 5.0, "Should have decent score for name match"

    # Test exact phrase in description
    matches, score = cap.matches("commit")
    assert matches, "Should match 'commit' in description"
    assert score > 0, "Should have positive score"

    # Test multi-word query
    matches, score = cap.matches("git workflow")
    assert matches, "Should match multiple words"
    assert score > 0, "Should have positive score"

    # Test trigger match
    matches, score = cap.matches("git push")
    assert matches, "Should match trigger phrase"
    assert score > 0, "Should have positive score"

    # Test non-match
    matches, score = cap.matches("database")
    assert not matches, "Should not match unrelated query"
    assert score == 0, "Should have zero score for non-match"

    print("✓ Capability matching works correctly")


def test_ranking_by_relevance():
    """Test that results are ranked by relevance."""
    capabilities = [
        Capability(
            name="git-basics",
            kind="skill",
            description="Basic Git commands",
            marketplace="test",
            plugin="test",
            path="skills/git-basics.md",
        ),
        Capability(
            name="advanced-git",
            kind="skill",
            description="Advanced Git features including rebase, cherry-pick, and bisect",
            marketplace="test",
            plugin="test",
            path="skills/advanced-git.md",
        ),
        Capability(
            name="database-tools",
            kind="skill",
            description="Database management tools",
            marketplace="test",
            plugin="test",
            path="skills/database-tools.md",
        ),
    ]

    # Search for "git"
    results = []
    for cap in capabilities:
        matches, score = cap.matches("git")
        if matches:
            results.append((cap, score))

    results.sort(key=lambda x: x[1], reverse=True)

    # Should find 2 git-related capabilities
    assert len(results) == 2, "Should find both git-related capabilities"

    # Both should have name matches (higher scores)
    assert results[0][0].name in ["git-basics", "advanced-git"]
    assert results[1][0].name in ["git-basics", "advanced-git"]

    # Scores should be positive
    assert all(score > 0 for _, score in results)

    print("✓ Ranking by relevance works correctly")


def test_save_and_load_capability_index():
    """Test saving and loading capability index."""
    # Create test capabilities
    capabilities = [
        Capability(
            name="skill-one",
            kind="skill",
            description="First test skill",
            marketplace="mp1",
            plugin="plugin1",
            path="skills/skill-one.md",
            triggers=["trigger1"],
        ),
        Capability(
            name="agent-two",
            kind="agent",
            description="Second test agent",
            marketplace="mp2",
            plugin="plugin2",
            path="agents/agent-two.md",
            triggers=["trigger2", "trigger3"],
        ),
    ]

    # Save to temporary file
    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = Path(tmpdir) / "test_index.json"

        # Monkey-patch CAPABILITY_INDEX
        import librarian.cli as cli_module
        original_path = cli_module.CAPABILITY_INDEX
        cli_module.CAPABILITY_INDEX = index_path

        try:
            # Save
            save_capability_index(capabilities)
            assert index_path.exists(), "Index file should be created"

            # Verify JSON structure
            with open(index_path) as fh:
                data = json.load(fh)

            assert "capabilities" in data
            assert "metadata" in data
            assert data["metadata"]["total_count"] == 2
            assert data["metadata"]["skills"] == 1
            assert data["metadata"]["agents"] == 1
            assert len(data["capabilities"]) == 2

            # Load
            loaded = load_capability_index()
            assert len(loaded) == 2, "Should load all capabilities"

            # Verify first capability
            cap1 = loaded[0]
            assert cap1.name == "skill-one"
            assert cap1.kind == "skill"
            assert cap1.description == "First test skill"
            assert cap1.marketplace == "mp1"
            assert cap1.plugin == "plugin1"
            assert cap1.path == "skills/skill-one.md"
            assert cap1.triggers == ["trigger1"]

            # Verify second capability
            cap2 = loaded[1]
            assert cap2.name == "agent-two"
            assert cap2.kind == "agent"
            assert cap2.triggers == ["trigger2", "trigger3"]

            print("✓ Save and load capability index works correctly")

        finally:
            # Restore original path
            cli_module.CAPABILITY_INDEX = original_path


def test_empty_index_handling():
    """Test handling of missing or empty index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = Path(tmpdir) / "nonexistent_index.json"

        # Monkey-patch CAPABILITY_INDEX
        import librarian.cli as cli_module
        original_path = cli_module.CAPABILITY_INDEX
        cli_module.CAPABILITY_INDEX = index_path

        try:
            # Load from non-existent file
            loaded = load_capability_index()
            assert loaded == [], "Should return empty list for missing index"

            print("✓ Empty index handling works correctly")

        finally:
            cli_module.CAPABILITY_INDEX = original_path


def test_malformed_index_handling():
    """Test handling of malformed index file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = Path(tmpdir) / "malformed_index.json"

        # Create malformed JSON
        with open(index_path, "w") as fh:
            fh.write("{ invalid json")

        # Monkey-patch CAPABILITY_INDEX
        import librarian.cli as cli_module
        original_path = cli_module.CAPABILITY_INDEX
        cli_module.CAPABILITY_INDEX = index_path

        try:
            # Should handle gracefully
            loaded = load_capability_index()
            assert loaded == [], "Should return empty list for malformed index"

            print("✓ Malformed index handling works correctly")

        finally:
            cli_module.CAPABILITY_INDEX = original_path


def test_query_variations():
    """Test various query patterns."""
    cap = Capability(
        name="pdf-tools",
        kind="skill",
        description="Tools for reading, writing, and editing PDF documents",
        marketplace="test",
        plugin="test",
        path="skills/pdf-tools.md",
        triggers=["create pdf", "edit pdf"],
    )

    test_cases = [
        ("pdf", True, "Should match name"),
        ("PDF", True, "Should be case-insensitive"),
        ("pdf tools", True, "Should match name and description"),
        ("reading pdf", True, "Should match description words"),
        ("create pdf", True, "Should match trigger"),
        ("documents", True, "Should match description word"),
        ("database", False, "Should not match unrelated term"),
    ]

    for query, should_match, description in test_cases:
        matches, score = cap.matches(query)
        if should_match:
            assert matches, f"{description}: query='{query}'"
            assert score > 0, f"Should have positive score: query='{query}'"
        else:
            assert not matches or score == 0, f"{description}: query='{query}'"

    print("✓ Query variations work correctly")


def test_score_ordering():
    """Test that scoring accounts for multiple matches."""
    cap = Capability(
        name="spreadsheet",
        kind="skill",
        description="Work with CSV files and Excel documents",
        marketplace="test",
        plugin="test",
        path="skills/spreadsheet.md",
    )

    # Query that matches name only (substring)
    matches1, score1 = cap.matches("spreadsheet")  # 10 (name)
    # Query that matches name only (substring, shorter)
    matches2, score2 = cap.matches("sheet")  # 10 (name substring)
    # Query that matches description only
    matches3, score3 = cap.matches("Excel")  # 5 (desc substring)
    # Query that doesn't match
    matches4, score4 = cap.matches("database")  # 0 (no match)

    # All name matches should score higher than description-only matches
    assert score1 >= score2, "Name matches should have high scores"
    assert score2 > score3, "Name substring match should score higher than description-only match"
    # Description match should beat no match
    assert score3 > score4, "Description match should score higher than no match"
    assert score4 == 0, "No match should have zero score"

    print("✓ Score ordering works correctly")


if __name__ == "__main__":
    print("Running semantic search tests...\n")

    test_capability_matching()
    test_ranking_by_relevance()
    test_save_and_load_capability_index()
    test_empty_index_handling()
    test_malformed_index_handling()
    test_query_variations()
    test_score_ordering()

    print("\n✓ All semantic search tests passed!")
