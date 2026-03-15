#!/usr/bin/env python3
"""Tests for marketplace-level similarity analysis."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))

from librarian.cli import cmd_marketplace_level


def create_mock_report(marketplaces_data):
    """Create a mock similarity report with given marketplace data.

    Args:
        marketplaces_data: dict of marketplace_name -> list of cluster_ids

    Returns:
        Report dict suitable for testing
    """
    # Build file index
    file_index = []
    file_idx = 0
    mp_file_map = {}
    for mp, cluster_ids in marketplaces_data.items():
        mp_file_map[mp] = []
        # Add some files for this marketplace
        for i in range(len(cluster_ids) + 2):  # More files than clusters
            file_index.append({
                "file_index": file_idx,
                "marketplace": mp,
                "plugin": "test-plugin",
                "path": f"skills/test-{i}.md",
                "filename": f"test-{i}.md",
                "is_official": False,
                "cluster_id": cluster_ids[i] if i < len(cluster_ids) else None,
                "in_cluster": i < len(cluster_ids),
            })
            mp_file_map[mp].append(file_idx)
            file_idx += 1

    # Build marketplace index
    marketplace_index = marketplaces_data.copy()

    # Build clusters
    all_cluster_ids = set()
    for ids in marketplaces_data.values():
        all_cluster_ids.update(ids)

    clusters = []
    for cid in sorted(all_cluster_ids):
        # Find which marketplaces have this cluster
        mps = [mp for mp, ids in marketplaces_data.items() if cid in ids]
        clusters.append({
            "cluster_id": cid,
            "type": "cross-marketplace" if len(mps) > 1 else "internal",
            "size": len(mps),
            "avg_similarity": 0.85,
            "has_official": False,
            "marketplaces": mps,
            "locations": [
                {"file_index": i, "marketplace": mp, "plugin": "test", "path": f"test.md", "is_official": False}
                for i, mp in enumerate(mps)
            ],
            "similarity_pairs": [],
        })

    return {
        "metadata": {"version": "2.0"},
        "summary": {
            "total_files_scanned": len(file_index),
            "files_in_clusters": sum(len(ids) for ids in marketplaces_data.values()),
            "unique_clusters": len(clusters),
        },
        "file_index": file_index,
        "marketplace_index": marketplace_index,
        "filename_index": {},
        "clusters": clusters,
    }


def run_with_mock_report(report, args):
    """Run cmd_marketplace_level with a mock report, handling temp file cleanup.

    Returns:
        List of print call arguments
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = Path(tmpdir) / "report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f)

        with patch('librarian.cli.SIMILARITY_REPORT', report_path):
            with patch('builtins.print') as mock_print:
                cmd_marketplace_level(args)
                return mock_print.call_args_list


def test_identical_marketplaces():
    """Test marketplaces with identical cluster membership (100% Jaccard)."""
    print("Testing identical marketplaces...")

    # Both marketplaces have the same clusters
    report = create_mock_report({
        "mp-a": [0, 1, 2],
        "mp-b": [0, 1, 2],
    })

    args = Mock()
    args.json = True
    args.heatmap = False

    call_list = run_with_mock_report(report, args)

    # Get the JSON output (last print call)
    output = call_list[-1][0][0]
    result = json.loads(output)

    # Check that mp-a and mp-b have 100% similarity
    assert result["similarity_matrix"]["mp-a"]["mp-b"] == 1.0
    assert result["similarity_matrix"]["mp-b"]["mp-a"] == 1.0
    print("[PASS] Identical marketplaces have 100% similarity")


def test_disjoint_marketplaces():
    """Test marketplaces with no shared clusters (0% Jaccard)."""
    print("Testing disjoint marketplaces...")

    # Different clusters for each marketplace
    report = create_mock_report({
        "mp-a": [0, 1, 2],
        "mp-b": [3, 4, 5],
    })

    args = Mock()
    args.json = True
    args.heatmap = False

    call_list = run_with_mock_report(report, args)
    output = call_list[-1][0][0]
    result = json.loads(output)

    # Check that mp-a and mp-b have 0% similarity
    assert result["similarity_matrix"]["mp-a"]["mp-b"] == 0.0
    assert result["similarity_matrix"]["mp-b"]["mp-a"] == 0.0
    print("[PASS] Disjoint marketplaces have 0% similarity")


def test_partial_overlap():
    """Test marketplaces with partial cluster overlap."""
    print("Testing partial overlap...")

    # Shared clusters 1, 2; mp-a has 0, mp-b has 3
    report = create_mock_report({
        "mp-a": [0, 1, 2],      # 3 clusters
        "mp-b": [1, 2, 3],      # 3 clusters, 2 shared
    })

    args = Mock()
    args.json = True
    args.heatmap = False

    call_list = run_with_mock_report(report, args)
    output = call_list[-1][0][0]
    result = json.loads(output)

    # Jaccard = |intersection| / |union| = 2 / 4 = 0.5
    assert result["similarity_matrix"]["mp-a"]["mp-b"] == 0.5
    print("[PASS] Partial overlap calculates correct Jaccard similarity")


def test_matrix_symmetry():
    """Test that similarity matrix is symmetric."""
    print("Testing matrix symmetry...")

    report = create_mock_report({
        "mp-a": [0, 1, 2],
        "mp-b": [1, 2, 3],
        "mp-c": [2, 3, 4],
    })

    args = Mock()
    args.json = True
    args.heatmap = False

    call_list = run_with_mock_report(report, args)
    output = call_list[-1][0][0]
    result = json.loads(output)

    matrix = result["similarity_matrix"]
    marketplaces = result["marketplaces"]

    # Check symmetry: matrix[a][b] == matrix[b][a]
    for mp_a in marketplaces:
        for mp_b in marketplaces:
            assert matrix[mp_a][mp_b] == matrix[mp_b][mp_a], \
                f"Matrix not symmetric: [{mp_a}][{mp_b}] != [{mp_b}][{mp_a}]"

    print("[PASS] Similarity matrix is symmetric")


def test_diagonal_is_one():
    """Test that diagonal elements are 1.0 (self-similarity)."""
    print("Testing diagonal is 1.0...")

    report = create_mock_report({
        "mp-a": [0, 1],
        "mp-b": [2, 3],
    })

    args = Mock()
    args.json = True
    args.heatmap = False

    call_list = run_with_mock_report(report, args)
    output = call_list[-1][0][0]
    result = json.loads(output)

    matrix = result["similarity_matrix"]

    # Check diagonal
    for mp in result["marketplaces"]:
        assert matrix[mp][mp] == 1.0, f"Diagonal not 1.0 for {mp}"

    print("[PASS] Diagonal elements are 1.0")


def test_text_output():
    """Test text output format."""
    print("Testing text output...")

    report = create_mock_report({
        "mp-a": [0, 1, 2],
        "mp-b": [1, 2, 3],
    })

    args = Mock()
    args.json = False
    args.heatmap = False

    call_list = run_with_mock_report(report, args)
    output = " ".join(str(call.args[0]) if call.args else "" for call in call_list)

    # Check expected content
    assert "MARKETPLACE SIMILARITY MATRIX" in output
    assert "Marketplace Statistics" in output
    assert "mp-a" in output
    assert "mp-b" in output

    print("[PASS] Text output contains expected content")


def test_heatmap_output():
    """Test heatmap visualization."""
    print("Testing heatmap output...")

    report = create_mock_report({
        "mp-a": [0, 1, 2],
        "mp-b": [0, 1, 2],  # 100% overlap
        "mp-c": [3, 4, 5],  # 0% overlap with a, b
    })

    args = Mock()
    args.json = False
    args.heatmap = True

    call_list = run_with_mock_report(report, args)
    output = " ".join(str(call.args[0]) if call.args else "" for call in call_list)

    # Check heatmap legend
    assert "Legend" in output
    assert "██" in output or "Heatmap" in output

    print("[PASS] Heatmap output generated")


def test_top_pairs_sorted():
    """Test that top pairs are sorted by similarity."""
    print("Testing top pairs sorting...")

    report = create_mock_report({
        "mp-a": [0, 1, 2, 3],
        "mp-b": [0, 1, 2, 3],  # 100% overlap with a
        "mp-c": [2, 3],        # 50% overlap with a (2/4)
        "mp-d": [5, 6],        # 0% overlap with a
    })

    args = Mock()
    args.json = True
    args.heatmap = False

    call_list = run_with_mock_report(report, args)
    output = call_list[-1][0][0]
    result = json.loads(output)

    top_pairs = result["top_pairs"]

    # Verify sorted descending by similarity
    for i in range(len(top_pairs) - 1):
        assert top_pairs[i]["similarity"] >= top_pairs[i+1]["similarity"], \
            "Top pairs not sorted by similarity"

    # The highest similarity pair should be mp-a/mp-b (100%)
    assert top_pairs[0]["similarity"] == 1.0

    print("[PASS] Top pairs sorted correctly")


def test_no_index_error():
    """Test error handling when no index exists."""
    print("Testing no index error...")

    args = Mock()
    args.json = False
    args.heatmap = False

    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent = Path(tmpdir) / "nonexistent.json"

        with patch('librarian.cli.SIMILARITY_REPORT', nonexistent):
            with patch('builtins.print') as mock_print:
                try:
                    cmd_marketplace_level(args)
                    assert False, "Should have exited"
                except SystemExit as e:
                    assert e.code == 1
                    output = " ".join(str(call.args[0]) if call.args else "" for call in mock_print.call_args_list)
                    assert "Error" in output or "Index not found" in output
                    print("[PASS] Missing index handled correctly")


def test_old_format_fallback():
    """Test fallback for old JSON format (no metadata/indices)."""
    print("Testing old format fallback...")

    # Old format report
    old_report = {
        "summary": {
            "total_files_scanned": 100,
            "unique_clusters": 5,
        },
        "clusters": [
            {
                "type": "cross-marketplace",
                "size": 3,
                "avg_similarity": 0.85,
                "has_official": False,
                "marketplaces": ["mp-a", "mp-b"],
                "locations": [
                    {"marketplace": "mp-a", "plugin": "p1", "path": "test.md", "is_official": False},
                    {"marketplace": "mp-b", "plugin": "p2", "path": "test.md", "is_official": False},
                ],
            },
            {
                "type": "internal",
                "size": 2,
                "avg_similarity": 0.90,
                "has_official": False,
                "marketplaces": ["mp-a"],
                "locations": [
                    {"marketplace": "mp-a", "plugin": "p1", "path": "test2.md", "is_official": False},
                ],
            },
        ],
    }

    args = Mock()
    args.json = True
    args.heatmap = False

    call_list = run_with_mock_report(old_report, args)
    output = call_list[-1][0][0]
    result = json.loads(output)

    # Should have found both marketplaces
    assert "mp-a" in result["marketplaces"]
    assert "mp-b" in result["marketplaces"]

    # mp-a has clusters 0, 1; mp-b has cluster 0
    # Jaccard = 1 / 2 = 0.5
    assert result["similarity_matrix"]["mp-a"]["mp-b"] == 0.5

    print("[PASS] Old format fallback works correctly")


if __name__ == "__main__":
    print("Running marketplace-level tests...\n")

    test_identical_marketplaces()
    test_disjoint_marketplaces()
    test_partial_overlap()
    test_matrix_symmetry()
    test_diagonal_is_one()
    test_text_output()
    test_heatmap_output()
    test_top_pairs_sorted()
    test_no_index_error()
    test_old_format_fallback()

    print("\n[PASS] All marketplace-level tests passed!")
