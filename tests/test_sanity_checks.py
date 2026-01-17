#!/usr/bin/env python3
"""Tests for sanity check functionality."""

import sys
from pathlib import Path

# Add parent directory to path to import librarian module
sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))

from librarian.core import check_similarity_sanity


def test_zero_percent_cluster_membership_large_ecosystem():
    """Test that 0% cluster membership triggers warning in large ecosystems."""
    result = check_similarity_sanity(
        total_files=1000,
        novel_count=1000,
        redundant_count=0,
        total_clusters=1500,
    )

    assert result.confidence == "low"
    assert len(result.warnings) > 0
    assert "0% cluster membership" in result.warnings[0]
    assert "1500 clusters" in result.warnings[0]
    print("✓ Test passed: 0% cluster membership warning triggered")


def test_zero_percent_small_ecosystem_no_warning():
    """Test that 0% cluster membership doesn't trigger warning in small ecosystems."""
    result = check_similarity_sanity(
        total_files=100,
        novel_count=100,
        redundant_count=0,
        total_clusters=500,  # Below 1000 threshold
    )

    # Should not trigger the cluster membership warning
    cluster_warnings = [w for w in result.warnings if "cluster membership" in w]
    assert len(cluster_warnings) == 0
    print("✓ Test passed: No warning for small ecosystem")


def test_very_low_similarity_ratio():
    """Test that <5% similarity ratio triggers warning for large datasets."""
    result = check_similarity_sanity(
        total_files=600,
        novel_count=580,
        redundant_count=20,  # 3.3%
        total_clusters=0,
    )

    assert result.confidence in ["medium", "low"]
    assert len(result.warnings) > 0
    low_sim_warnings = [w for w in result.warnings if "low similarity ratio" in w.lower()]
    assert len(low_sim_warnings) > 0
    print("✓ Test passed: Low similarity ratio warning triggered")


def test_very_high_similarity_ratio():
    """Test that >95% similarity ratio triggers warning for large datasets."""
    result = check_similarity_sanity(
        total_files=600,
        novel_count=20,
        redundant_count=580,  # 96.7%
        total_clusters=0,
    )

    assert result.confidence in ["medium", "low"]
    assert len(result.warnings) > 0
    high_sim_warnings = [w for w in result.warnings if "high similarity ratio" in w.lower()]
    assert len(high_sim_warnings) > 0
    print("✓ Test passed: High similarity ratio warning triggered")


def test_extreme_ratios_small_dataset_no_warning():
    """Test that extreme ratios don't trigger warnings for small datasets."""
    result = check_similarity_sanity(
        total_files=200,  # Below 500 threshold
        novel_count=190,
        redundant_count=10,  # 5% - would trigger on large dataset
        total_clusters=0,
    )

    # Should not trigger the ratio warnings
    ratio_warnings = [w for w in result.warnings if "ratio" in w.lower()]
    assert len(ratio_warnings) == 0
    assert result.confidence == "high"
    print("✓ Test passed: No warning for extreme ratios on small dataset")


def test_normal_results_high_confidence():
    """Test that normal results get high confidence."""
    result = check_similarity_sanity(
        total_files=1000,
        novel_count=700,
        redundant_count=300,  # 30%
        total_clusters=500,
    )

    assert result.confidence == "high"
    assert len(result.warnings) == 0
    print("✓ Test passed: Normal results have high confidence")


def test_suspicious_fifty_fifty_split():
    """Test that 50/50 split triggers warning."""
    result = check_similarity_sanity(
        total_files=200,
        novel_count=100,
        redundant_count=100,  # Exactly 50/50
        total_clusters=0,
    )

    assert result.confidence in ["medium", "low"]
    fifty_warnings = [w for w in result.warnings if "50/50" in w]
    assert len(fifty_warnings) > 0
    print("✓ Test passed: 50/50 split warning triggered")


def test_zero_files_analyzed():
    """Test handling of zero files."""
    result = check_similarity_sanity(
        total_files=0,
        novel_count=0,
        redundant_count=0,
        total_clusters=0,
    )

    assert result.confidence == "none"
    assert "No files were analyzed" in result.warnings
    print("✓ Test passed: Zero files handled correctly")


def test_multiple_warnings():
    """Test that multiple warnings can be triggered simultaneously."""
    result = check_similarity_sanity(
        total_files=1000,
        novel_count=1000,
        redundant_count=0,
        total_clusters=2000,  # Large ecosystem with 0% redundancy
    )

    # Should trigger cluster membership warning
    assert len(result.warnings) >= 1
    assert result.confidence == "low"
    print("✓ Test passed: Multiple warnings can be triggered")


def test_to_dict():
    """Test that SanityCheckResult.to_dict() works correctly."""
    result = check_similarity_sanity(
        total_files=500,
        novel_count=450,
        redundant_count=50,
        total_clusters=100,
    )

    result_dict = result.to_dict()
    assert "confidence" in result_dict
    assert "warnings" in result_dict
    assert isinstance(result_dict["warnings"], list)
    assert result_dict["confidence"] == result.confidence
    print("✓ Test passed: to_dict() serializes correctly")


if __name__ == "__main__":
    print("Running sanity check tests...\n")

    test_zero_percent_cluster_membership_large_ecosystem()
    test_zero_percent_small_ecosystem_no_warning()
    test_very_low_similarity_ratio()
    test_very_high_similarity_ratio()
    test_extreme_ratios_small_dataset_no_warning()
    test_normal_results_high_confidence()
    test_suspicious_fifty_fifty_split()
    test_zero_files_analyzed()
    test_multiple_warnings()
    test_to_dict()

    print("\n✓ All tests passed!")
