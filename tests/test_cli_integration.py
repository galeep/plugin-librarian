#!/usr/bin/env python3
"""Integration tests for CLI sanity checks."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))

from librarian import cli
from librarian.core import check_similarity_sanity


def test_scan_output_includes_confidence_and_warnings():
    """Test that scan command includes confidence and warnings in output."""
    # This is a unit test of the logic, not a full CLI integration test
    # We verify the sanity check is called and warnings are displayed

    # Test case 1: Large ecosystem with 0% cluster membership
    result = check_similarity_sanity(
        total_files=1000,
        novel_count=1000,
        redundant_count=0,
        total_clusters=1500,
    )

    assert result.confidence == "low"
    assert len(result.warnings) > 0
    assert "0% cluster membership" in result.warnings[0]
    print("✓ Scan sanity check: large ecosystem warning works")


def test_compare_sanity_checks():
    """Test that compare command performs sanity checks."""
    # Test case 1: Low similarity ratio
    result = check_similarity_sanity(
        total_files=600,
        novel_count=580,
        redundant_count=20,
        total_clusters=100,
    )

    assert result.confidence in ["medium", "low"]
    assert any("low similarity ratio" in w.lower() for w in result.warnings)
    print("✓ Compare sanity check: low similarity ratio warning works")

    # Test case 2: High similarity ratio
    result = check_similarity_sanity(
        total_files=600,
        novel_count=20,
        redundant_count=580,
        total_clusters=100,
    )

    assert result.confidence in ["medium", "low"]
    assert any("high similarity ratio" in w.lower() for w in result.warnings)
    print("✓ Compare sanity check: high similarity ratio warning works")


def test_json_output_structure():
    """Test that JSON output includes required fields."""
    result = check_similarity_sanity(
        total_files=1000,
        novel_count=700,
        redundant_count=300,
        total_clusters=500,
    )

    result_dict = result.to_dict()

    # Verify structure
    assert "confidence" in result_dict
    assert "warnings" in result_dict
    assert isinstance(result_dict["confidence"], str)
    assert isinstance(result_dict["warnings"], list)

    # Verify values
    assert result_dict["confidence"] == "high"
    assert result_dict["warnings"] == []

    print("✓ JSON output structure is correct")


def test_confidence_levels():
    """Test that different scenarios produce appropriate confidence levels."""
    # High confidence: normal results
    result = check_similarity_sanity(
        total_files=1000,
        novel_count=600,
        redundant_count=400,
        total_clusters=500,
    )
    assert result.confidence == "high"

    # Medium confidence: suspicious ratio
    result = check_similarity_sanity(
        total_files=600,
        novel_count=580,
        redundant_count=20,
        total_clusters=100,
    )
    assert result.confidence == "medium"

    # Low confidence: 0% cluster membership in large ecosystem
    result = check_similarity_sanity(
        total_files=1000,
        novel_count=1000,
        redundant_count=0,
        total_clusters=1500,
    )
    assert result.confidence == "low"

    # No confidence: no files
    result = check_similarity_sanity(
        total_files=0,
        novel_count=0,
        redundant_count=0,
        total_clusters=0,
    )
    assert result.confidence == "none"

    print("✓ Confidence levels are correctly assigned")


def test_warning_thresholds():
    """Test that warnings are triggered at correct thresholds."""
    # Just below threshold: no warning
    result = check_similarity_sanity(
        total_files=1000,
        novel_count=1000,
        redundant_count=0,
        total_clusters=999,  # Just below 1000 threshold
    )
    cluster_warnings = [w for w in result.warnings if "cluster membership" in w]
    assert len(cluster_warnings) == 0

    # At threshold: warning
    result = check_similarity_sanity(
        total_files=1000,
        novel_count=1000,
        redundant_count=0,
        total_clusters=1001,  # Above 1000 threshold
    )
    cluster_warnings = [w for w in result.warnings if "cluster membership" in w]
    assert len(cluster_warnings) > 0

    # Small dataset: no ratio warnings
    result = check_similarity_sanity(
        total_files=400,  # Below 500 threshold
        novel_count=380,
        redundant_count=20,  # 5% - would trigger on large dataset
        total_clusters=100,
    )
    ratio_warnings = [w for w in result.warnings if "ratio" in w.lower()]
    assert len(ratio_warnings) == 0

    # Large dataset: ratio warnings
    result = check_similarity_sanity(
        total_files=600,  # Above 500 threshold
        novel_count=580,
        redundant_count=20,  # 3.3%
        total_clusters=100,
    )
    ratio_warnings = [w for w in result.warnings if "ratio" in w.lower()]
    assert len(ratio_warnings) > 0

    print("✓ Warning thresholds work correctly")


if __name__ == "__main__":
    print("Running CLI integration tests...\n")

    test_scan_output_includes_confidence_and_warnings()
    test_compare_sanity_checks()
    test_json_output_structure()
    test_confidence_levels()
    test_warning_thresholds()

    print("\n✓ All integration tests passed!")
