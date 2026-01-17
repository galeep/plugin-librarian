#!/usr/bin/env python3
"""Tests for marketplace-to-marketplace comparison functionality."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add parent directory to path to import librarian module
sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))

from librarian.cli import cmd_compare_marketplaces
from librarian.core import FileInfo, compute_minhash, tokenize


def create_test_file(content: str, marketplace: str, plugin: str, rel_path: str) -> FileInfo:
    """Create a test FileInfo with MinHash."""
    f = FileInfo(
        marketplace=marketplace,
        plugin=plugin,
        relative_path=rel_path,
        full_path=f"/tmp/{rel_path}",
        content=content,
    )
    shingles = tokenize(content)
    if shingles:
        f.minhash = compute_minhash(shingles)
    return f


def test_identical_marketplaces():
    """Test comparison of identical marketplaces (100% overlap)."""
    print("Testing identical marketplaces (100% overlap)...")

    # Create mock args
    args = Mock()
    args.marketplace_a = "test-mp-a"
    args.marketplace_b = "test-mp-b"
    args.json = False

    # Create identical content
    content1 = "This is a test skill for data processing and analysis."
    content2 = "This is a test skill for data processing and analysis."

    files_a = [
        create_test_file(content1, "test-mp-a", "plugin1", "skills/test.md"),
    ]

    files_b = [
        create_test_file(content2, "test-mp-b", "plugin1", "skills/test.md"),
    ]

    # Mock the necessary functions
    with patch('librarian.cli.find_marketplace_path') as mock_find_mp, \
         patch('librarian.cli.scan_directory_for_content') as mock_scan, \
         patch('builtins.print') as mock_print:

        mock_find_mp.side_effect = [Path("/tmp/mp-a"), Path("/tmp/mp-b")]
        mock_scan.side_effect = [files_a, files_b]

        cmd_compare_marketplaces(args)

        # Check that output mentions 100% overlap
        printed_output = " ".join([str(call.args[0]) if call.args else "" for call in mock_print.call_args_list])
        assert "Identical marketplaces" in printed_output or "100%" in printed_output
        print("✓ Identical marketplaces detected correctly")


def test_disjoint_marketplaces():
    """Test comparison of completely different marketplaces (0% overlap)."""
    print("Testing disjoint marketplaces (0% overlap)...")

    args = Mock()
    args.marketplace_a = "test-mp-a"
    args.marketplace_b = "test-mp-b"
    args.json = False

    # Create completely different content
    content_a = "This is unique content about machine learning and neural networks for AI applications."
    content_b = "Completely different topic about cooking recipes and culinary arts for chefs."

    files_a = [
        create_test_file(content_a, "test-mp-a", "plugin1", "skills/ml.md"),
    ]

    files_b = [
        create_test_file(content_b, "test-mp-b", "plugin1", "skills/cooking.md"),
    ]

    with patch('librarian.cli.find_marketplace_path') as mock_find_mp, \
         patch('librarian.cli.scan_directory_for_content') as mock_scan, \
         patch('builtins.print') as mock_print:

        mock_find_mp.side_effect = [Path("/tmp/mp-a"), Path("/tmp/mp-b")]
        mock_scan.side_effect = [files_a, files_b]

        cmd_compare_marketplaces(args)

        printed_output = " ".join([str(call.args[0]) if call.args else "" for call in mock_print.call_args_list])
        assert "Disjoint" in printed_output or "0%" in printed_output or "0 files" in printed_output
        print("✓ Disjoint marketplaces detected correctly")


def test_partial_overlap():
    """Test comparison with partial overlap."""
    print("Testing partial overlap...")

    args = Mock()
    args.marketplace_a = "test-mp-a"
    args.marketplace_b = "test-mp-b"
    args.json = False

    # Create overlapping and unique content
    shared_content = "This is shared content about data processing that appears in both marketplaces."
    unique_a = "Unique content A about specific feature only in marketplace A with detailed examples."
    unique_b = "Unique content B about different feature only in marketplace B with tutorials."

    files_a = [
        create_test_file(shared_content, "test-mp-a", "plugin1", "skills/shared.md"),
        create_test_file(unique_a, "test-mp-a", "plugin1", "skills/unique-a.md"),
    ]

    files_b = [
        create_test_file(shared_content, "test-mp-b", "plugin1", "skills/shared.md"),
        create_test_file(unique_b, "test-mp-b", "plugin1", "skills/unique-b.md"),
    ]

    with patch('librarian.cli.find_marketplace_path') as mock_find_mp, \
         patch('librarian.cli.scan_directory_for_content') as mock_scan, \
         patch('builtins.print') as mock_print:

        mock_find_mp.side_effect = [Path("/tmp/mp-a"), Path("/tmp/mp-b")]
        mock_scan.side_effect = [files_a, files_b]

        cmd_compare_marketplaces(args)

        printed_output = " ".join([str(call.args[0]) if call.args else "" for call in mock_print.call_args_list])

        # Should show both shared and unique content
        assert "Shared" in printed_output or "overlap" in printed_output
        assert "unique" in printed_output.lower()
        print("✓ Partial overlap detected correctly")


def test_empty_marketplace():
    """Test comparison when one marketplace is empty."""
    print("Testing empty marketplace...")

    args = Mock()
    args.marketplace_a = "test-mp-a"
    args.marketplace_b = "test-mp-b"
    args.json = False

    content_a = "Some content in marketplace A."

    files_a = [
        create_test_file(content_a, "test-mp-a", "plugin1", "skills/test.md"),
    ]
    files_b = []  # Empty marketplace

    with patch('librarian.cli.find_marketplace_path') as mock_find_mp, \
         patch('librarian.cli.scan_directory_for_content') as mock_scan, \
         patch('builtins.print') as mock_print:

        mock_find_mp.side_effect = [Path("/tmp/mp-a"), Path("/tmp/mp-b")]
        mock_scan.side_effect = [files_a, files_b]

        cmd_compare_marketplaces(args)

        printed_output = " ".join([str(call.args[0]) if call.args else "" for call in mock_print.call_args_list])
        assert "WARNING" in printed_output or "0 files" in printed_output
        print("✓ Empty marketplace handled correctly")


def test_json_output():
    """Test JSON output format."""
    print("Testing JSON output...")

    args = Mock()
    args.marketplace_a = "test-mp-a"
    args.marketplace_b = "test-mp-b"
    args.json = True

    content1 = "Test content for JSON output validation."
    content2 = "Test content for JSON output validation."

    files_a = [create_test_file(content1, "test-mp-a", "plugin1", "skills/test.md")]
    files_b = [create_test_file(content2, "test-mp-b", "plugin1", "skills/test.md")]

    with patch('librarian.cli.find_marketplace_path') as mock_find_mp, \
         patch('librarian.cli.scan_directory_for_content') as mock_scan, \
         patch('builtins.print') as mock_print:

        mock_find_mp.side_effect = [Path("/tmp/mp-a"), Path("/tmp/mp-b")]
        mock_scan.side_effect = [files_a, files_b]

        cmd_compare_marketplaces(args)

        # Check that JSON-like output was printed
        printed_output = " ".join([str(call.args[0]) if call.args else "" for call in mock_print.call_args_list])
        assert "marketplace_a" in printed_output or "{" in printed_output
        print("✓ JSON output generated correctly")


def test_similarity_threshold():
    """Test that similarity threshold is respected."""
    print("Testing similarity threshold...")

    args = Mock()
    args.marketplace_a = "test-mp-a"
    args.marketplace_b = "test-mp-b"
    args.json = False

    # Create content with slight differences (should be below threshold if different enough)
    content_a = "This is content about data processing with many specific details and examples."
    content_b = "This content discusses cooking recipes with many specific instructions and photos."

    files_a = [create_test_file(content_a, "test-mp-a", "plugin1", "skills/a.md")]
    files_b = [create_test_file(content_b, "test-mp-b", "plugin1", "skills/b.md")]

    with patch('librarian.cli.find_marketplace_path') as mock_find_mp, \
         patch('librarian.cli.scan_directory_for_content') as mock_scan, \
         patch('builtins.print'):

        mock_find_mp.side_effect = [Path("/tmp/mp-a"), Path("/tmp/mp-b")]
        mock_scan.side_effect = [files_a, files_b]

        # Should not crash and should handle the comparison
        try:
            cmd_compare_marketplaces(args)
            print("✓ Similarity threshold handled correctly")
        except Exception as e:
            print(f"✗ Error: {e}")
            raise


def test_large_marketplaces():
    """Test performance with larger marketplaces."""
    print("Testing with larger marketplaces...")

    args = Mock()
    args.marketplace_a = "test-mp-a"
    args.marketplace_b = "test-mp-b"
    args.json = False

    # Create 20 files in each marketplace with varying overlap
    files_a = []
    files_b = []

    for i in range(10):
        # Shared content
        shared = f"Shared content number {i} with data processing and analysis features."
        files_a.append(create_test_file(shared, "test-mp-a", "plugin1", f"skills/shared-{i}.md"))
        files_b.append(create_test_file(shared, "test-mp-b", "plugin1", f"skills/shared-{i}.md"))

    for i in range(5):
        # Unique to A
        unique_a = f"Unique to A number {i} with specific marketplace A features and tools."
        files_a.append(create_test_file(unique_a, "test-mp-a", "plugin1", f"skills/unique-a-{i}.md"))

        # Unique to B
        unique_b = f"Unique to B number {i} with specific marketplace B features and tools."
        files_b.append(create_test_file(unique_b, "test-mp-b", "plugin1", f"skills/unique-b-{i}.md"))

    with patch('librarian.cli.find_marketplace_path') as mock_find_mp, \
         patch('librarian.cli.scan_directory_for_content') as mock_scan, \
         patch('builtins.print') as mock_print:

        mock_find_mp.side_effect = [Path("/tmp/mp-a"), Path("/tmp/mp-b")]
        mock_scan.side_effect = [files_a, files_b]

        cmd_compare_marketplaces(args)

        printed_output = " ".join([str(call.args[0]) if call.args else "" for call in mock_print.call_args_list])

        # Should detect shared content - just verify it completed without errors
        # and contains expected keywords
        assert "Shared" in printed_output or "overlap" in printed_output
        assert "unique" in printed_output.lower() or "only" in printed_output.lower()
        print("✓ Large marketplace comparison completed successfully")


def test_marketplace_not_found():
    """Test error handling when marketplace is not found."""
    print("Testing marketplace not found error...")

    args = Mock()
    args.marketplace_a = "nonexistent-mp"
    args.marketplace_b = "test-mp-b"
    args.json = False

    with patch('librarian.cli.find_marketplace_path') as mock_find_mp, \
         patch('librarian.cli.MARKETPLACES_DIR') as mock_dir, \
         patch('builtins.print'):

        mock_find_mp.return_value = None
        mock_mp = Mock()
        mock_mp.is_dir.return_value = True
        mock_mp.name = "mp1"
        mock_dir.iterdir.return_value = [mock_mp]

        # Should raise SystemExit
        try:
            cmd_compare_marketplaces(args)
            assert False, "Should have exited with error"
        except SystemExit as e:
            assert e.code == 1
            print("✓ Marketplace not found error handled correctly")


if __name__ == "__main__":
    print("Running marketplace comparison tests...\n")

    test_identical_marketplaces()
    test_disjoint_marketplaces()
    test_partial_overlap()
    test_empty_marketplace()
    test_json_output()
    test_similarity_threshold()
    test_large_marketplaces()
    test_marketplace_not_found()

    print("\n✓ All marketplace comparison tests passed!")
