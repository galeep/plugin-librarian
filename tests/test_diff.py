#!/usr/bin/env python3
"""Tests for diff functionality."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))

from librarian.core import FileInfo, tokenize, compute_minhash
from librarian.diff import (
    normalize_for_diff,
    compute_file_diff,
    format_diff_for_terminal,
)


def test_normalize_for_diff():
    """Test that normalization removes whitespace differences."""
    text1 = "def foo():\n    return 42\n\n"
    text2 = "def foo():\n\treturn 42\n\n"

    lines1 = normalize_for_diff(text1)
    lines2 = normalize_for_diff(text2)

    # Both should normalize to same content
    assert lines1 == lines2
    print("✓ Normalization removes whitespace differences")


def test_normalize_preserves_structure():
    """Test that normalization preserves line structure."""
    text = "# Header\n\nContent here\n  Indented"

    lines = normalize_for_diff(text)

    # Should preserve blank lines and content
    assert len(lines) == 4
    assert lines[0] == "# Header"
    assert lines[1] == ""  # Blank line preserved
    assert lines[2] == "Content here"
    assert lines[3].strip() == "Indented"
    print("✓ Normalization preserves line structure")


def test_compute_file_diff_basic():
    """Test basic diff computation."""
    file1 = FileInfo(
        marketplace="test-mp",
        plugin="test-plugin",
        relative_path="file1.md",
        full_path="/tmp/file1.md",
        content="# Header\n\nSome content\n",
    )

    file2 = FileInfo(
        marketplace="test-mp",
        plugin="test-plugin",
        relative_path="file2.md",
        full_path="/tmp/file2.md",
        content="# Header\n\nDifferent content\n",
    )

    # Compute minhash for similarity
    file1.minhash = compute_minhash(tokenize(file1.content))
    file2.minhash = compute_minhash(tokenize(file2.content))

    diff = compute_file_diff(file1, file2)

    # Check structure
    assert diff.file1_location == "test-mp/test-plugin/file1.md"
    assert diff.file2_location == "test-mp/test-plugin/file2.md"
    assert 0.0 <= diff.similarity <= 1.0
    assert isinstance(diff.unified_diff, list)
    assert isinstance(diff.semantic_changes, list)
    assert isinstance(diff.stats, dict)

    print("✓ Basic diff computation works")


def test_semantic_changes_detection():
    """Test that semantic changes are detected."""
    file1 = FileInfo(
        marketplace="test",
        plugin="test",
        relative_path="old.md",
        full_path="/tmp/old.md",
        content="def foo():\n    pass\n\nclass Bar:\n    pass\n",
    )

    file2 = FileInfo(
        marketplace="test",
        plugin="test",
        relative_path="new.md",
        full_path="/tmp/new.md",
        content="def foo():\n    pass\n\ndef baz():\n    pass\n",
    )

    diff = compute_file_diff(file1, file2)

    # Should detect function added and class removed
    change_types = {c["type"] for c in diff.semantic_changes}
    assert "function_added" in change_types or "function_removed" in change_types

    # Check stats
    assert "functions_added" in diff.stats
    assert "functions_removed" in diff.stats

    print("✓ Semantic changes detection works")


def test_diff_stats():
    """Test that diff stats are computed correctly."""
    file1 = FileInfo(
        marketplace="test",
        plugin="test",
        relative_path="a.md",
        full_path="/tmp/a.md",
        content="Line 1\nLine 2\nLine 3\n",
    )

    file2 = FileInfo(
        marketplace="test",
        plugin="test",
        relative_path="b.md",
        full_path="/tmp/b.md",
        content="Line 1\nModified Line 2\nLine 3\nLine 4\n",
    )

    diff = compute_file_diff(file1, file2)

    assert diff.stats["total_lines_file1"] == 3
    assert diff.stats["total_lines_file2"] == 4
    assert diff.stats["diff_lines"] >= 0

    print("✓ Diff stats computation works")


def test_format_diff_for_terminal():
    """Test that terminal formatting produces output."""
    file1 = FileInfo(
        marketplace="test",
        plugin="test",
        relative_path="a.md",
        full_path="/tmp/a.md",
        content="Original content\n",
    )

    file2 = FileInfo(
        marketplace="test",
        plugin="test",
        relative_path="b.md",
        full_path="/tmp/b.md",
        content="Modified content\n",
    )

    file1.minhash = compute_minhash(tokenize(file1.content))
    file2.minhash = compute_minhash(tokenize(file2.content))

    diff = compute_file_diff(file1, file2)
    output = format_diff_for_terminal(diff)

    # Should contain basic elements
    assert "File Comparison" in output
    assert "test/test/a.md" in output
    assert "Similarity" in output

    print("✓ Terminal formatting works")


def test_to_dict_json_output():
    """Test that FileDiff can be converted to JSON-serializable dict."""
    file1 = FileInfo(
        marketplace="test",
        plugin="test",
        relative_path="a.md",
        full_path="/tmp/a.md",
        content="Content A\n",
    )

    file2 = FileInfo(
        marketplace="test",
        plugin="test",
        relative_path="b.md",
        full_path="/tmp/b.md",
        content="Content B\n",
    )

    diff = compute_file_diff(file1, file2)
    result = diff.to_dict()

    # Check JSON structure
    assert "file1" in result
    assert "file2" in result
    assert "similarity" in result
    assert "stats" in result
    assert "semantic_changes" in result
    assert "unified_diff" in result

    print("✓ JSON output structure is correct")


if __name__ == "__main__":
    print("Running diff tests...\n")

    test_normalize_for_diff()
    test_normalize_preserves_structure()
    test_compute_file_diff_basic()
    test_semantic_changes_detection()
    test_diff_stats()
    test_format_diff_for_terminal()
    test_to_dict_json_output()

    print("\n✓ All diff tests passed!")
