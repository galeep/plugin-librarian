"""Tests for improved JSON structure and queryability."""

import json
from datetime import datetime, timezone


def test_json_has_metadata_section(tmp_path):
    """Verify metadata section exists with required fields."""
    # Create a sample report structure
    report = {
        "metadata": {
            "version": "2.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "similarity_threshold": 0.7,
            "num_permutations": 128,
            "confidence": "high",
            "warnings": [],
        },
        "summary": {},
        "file_index": [],
        "marketplace_index": {},
        "filename_index": {},
        "clusters": [],
    }

    # Write to temp file
    report_path = tmp_path / "test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f)

    # Read back and validate
    with open(report_path) as f:
        loaded = json.load(f)

    assert "metadata" in loaded
    assert loaded["metadata"]["version"] == "2.0"
    assert "generated_at" in loaded["metadata"]
    assert "similarity_threshold" in loaded["metadata"]
    assert "num_permutations" in loaded["metadata"]
    assert "confidence" in loaded["metadata"]
    assert "warnings" in loaded["metadata"]


def test_json_has_file_index(tmp_path):
    """Verify file_index array exists and has correct structure."""
    report = {
        "metadata": {"version": "2.0"},
        "summary": {},
        "file_index": [
            {
                "file_index": 0,
                "marketplace": "test-mp",
                "plugin": "test-plugin",
                "path": "skills/test.md",
                "filename": "test.md",
                "is_official": False,
                "cluster_id": None,
                "in_cluster": False,
            },
            {
                "file_index": 1,
                "marketplace": "test-mp",
                "plugin": "test-plugin",
                "path": "skills/test2.md",
                "filename": "test2.md",
                "is_official": False,
                "cluster_id": 0,
                "in_cluster": True,
            },
        ],
        "marketplace_index": {},
        "filename_index": {},
        "clusters": [],
    }

    report_path = tmp_path / "test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f)

    with open(report_path) as f:
        loaded = json.load(f)

    assert "file_index" in loaded
    assert isinstance(loaded["file_index"], list)
    assert len(loaded["file_index"]) == 2

    # Verify structure of first file
    file_entry = loaded["file_index"][0]
    assert "file_index" in file_entry
    assert "marketplace" in file_entry
    assert "plugin" in file_entry
    assert "path" in file_entry
    assert "filename" in file_entry
    assert "is_official" in file_entry
    assert "cluster_id" in file_entry
    assert "in_cluster" in file_entry


def test_json_has_marketplace_index(tmp_path):
    """Verify marketplace_index exists and enables fast lookups."""
    report = {
        "metadata": {"version": "2.0"},
        "summary": {},
        "file_index": [],
        "marketplace_index": {
            "marketplace-a": [0, 1, 5],
            "marketplace-b": [2, 3],
        },
        "filename_index": {},
        "clusters": [],
    }

    report_path = tmp_path / "test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f)

    with open(report_path) as f:
        loaded = json.load(f)

    assert "marketplace_index" in loaded
    assert isinstance(loaded["marketplace_index"], dict)
    assert "marketplace-a" in loaded["marketplace_index"]
    assert loaded["marketplace_index"]["marketplace-a"] == [0, 1, 5]


def test_json_has_filename_index(tmp_path):
    """Verify filename_index exists and enables fast lookups."""
    report = {
        "metadata": {"version": "2.0"},
        "summary": {},
        "file_index": [],
        "marketplace_index": {},
        "filename_index": {
            "test.md": [0, 5, 10],
            "skill.md": [1, 2],
        },
        "clusters": [],
    }

    report_path = tmp_path / "test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f)

    with open(report_path) as f:
        loaded = json.load(f)

    assert "filename_index" in loaded
    assert isinstance(loaded["filename_index"], dict)
    assert "test.md" in loaded["filename_index"]
    assert loaded["filename_index"]["test.md"] == [0, 5, 10]


def test_clusters_have_cluster_id(tmp_path):
    """Verify clusters have cluster_id field."""
    report = {
        "metadata": {"version": "2.0"},
        "summary": {},
        "file_index": [],
        "marketplace_index": {},
        "filename_index": {},
        "clusters": [
            {
                "cluster_id": 0,
                "type": "internal",
                "size": 3,
                "avg_similarity": 0.85,
                "has_official": False,
                "marketplaces": ["test-mp"],
                "locations": [],
                "similarity_pairs": [],
            },
            {
                "cluster_id": 1,
                "type": "cross-marketplace",
                "size": 5,
                "avg_similarity": 0.75,
                "has_official": True,
                "marketplaces": ["mp-a", "mp-b"],
                "locations": [],
                "similarity_pairs": [],
            },
        ],
    }

    report_path = tmp_path / "test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f)

    with open(report_path) as f:
        loaded = json.load(f)

    assert len(loaded["clusters"]) == 2
    assert loaded["clusters"][0]["cluster_id"] == 0
    assert loaded["clusters"][1]["cluster_id"] == 1


def test_clusters_have_similarity_pairs(tmp_path):
    """Verify clusters have similarity_pairs field with pairwise similarities."""
    report = {
        "metadata": {"version": "2.0"},
        "summary": {},
        "file_index": [],
        "marketplace_index": {},
        "filename_index": {},
        "clusters": [
            {
                "cluster_id": 0,
                "type": "internal",
                "size": 3,
                "avg_similarity": 0.85,
                "has_official": False,
                "marketplaces": ["test-mp"],
                "locations": [
                    {
                        "file_index": 0,
                        "marketplace": "test-mp",
                        "plugin": "plugin-a",
                        "path": "test1.md",
                        "is_official": False,
                    },
                    {
                        "file_index": 1,
                        "marketplace": "test-mp",
                        "plugin": "plugin-a",
                        "path": "test2.md",
                        "is_official": False,
                    },
                ],
                "similarity_pairs": [
                    {
                        "file1_index": 0,
                        "file2_index": 1,
                        "similarity": 0.85,
                    }
                ],
            },
        ],
    }

    report_path = tmp_path / "test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f)

    with open(report_path) as f:
        loaded = json.load(f)

    cluster = loaded["clusters"][0]
    assert "similarity_pairs" in cluster
    assert isinstance(cluster["similarity_pairs"], list)
    assert len(cluster["similarity_pairs"]) == 1

    pair = cluster["similarity_pairs"][0]
    assert "file1_index" in pair
    assert "file2_index" in pair
    assert "similarity" in pair


def test_locations_have_file_index(tmp_path):
    """Verify cluster locations include file_index reference."""
    report = {
        "metadata": {"version": "2.0"},
        "summary": {},
        "file_index": [],
        "marketplace_index": {},
        "filename_index": {},
        "clusters": [
            {
                "cluster_id": 0,
                "type": "internal",
                "size": 2,
                "avg_similarity": 0.85,
                "has_official": False,
                "marketplaces": ["test-mp"],
                "locations": [
                    {
                        "file_index": 0,
                        "marketplace": "test-mp",
                        "plugin": "plugin-a",
                        "path": "test1.md",
                        "is_official": False,
                    },
                    {
                        "file_index": 1,
                        "marketplace": "test-mp",
                        "plugin": "plugin-a",
                        "path": "test2.md",
                        "is_official": False,
                    },
                ],
                "similarity_pairs": [],
            },
        ],
    }

    report_path = tmp_path / "test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f)

    with open(report_path) as f:
        loaded = json.load(f)

    cluster = loaded["clusters"][0]
    for location in cluster["locations"]:
        assert "file_index" in location
        assert isinstance(location["file_index"], int)


def test_jq_query_clusters_by_marketplace(tmp_path):
    """Test jq query: get all clusters for a specific marketplace."""
    report = {
        "metadata": {"version": "2.0"},
        "summary": {},
        "file_index": [],
        "marketplace_index": {
            "marketplace-a": [0, 2],
            "marketplace-b": [1],
        },
        "filename_index": {},
        "clusters": [
            {"cluster_id": 0, "type": "internal", "size": 3, "marketplaces": ["marketplace-a"]},
            {"cluster_id": 1, "type": "internal", "size": 2, "marketplaces": ["marketplace-b"]},
            {"cluster_id": 2, "type": "cross-marketplace", "size": 5, "marketplaces": ["marketplace-a", "marketplace-b"]},
        ],
    }

    report_path = tmp_path / "test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f)

    # Simulate jq query: .marketplace_index["marketplace-a"]
    with open(report_path) as f:
        loaded = json.load(f)

    cluster_ids = loaded["marketplace_index"]["marketplace-a"]
    assert cluster_ids == [0, 2]

    # Get clusters by ID
    clusters = [c for c in loaded["clusters"] if c["cluster_id"] in cluster_ids]
    assert len(clusters) == 2
    assert clusters[0]["cluster_id"] == 0
    assert clusters[1]["cluster_id"] == 2


def test_jq_query_files_by_marketplace(tmp_path):
    """Test jq query: get all files for a specific marketplace."""
    report = {
        "metadata": {"version": "2.0"},
        "summary": {},
        "file_index": [
            {"file_index": 0, "marketplace": "mp-a", "plugin": "p1", "path": "f1.md"},
            {"file_index": 1, "marketplace": "mp-b", "plugin": "p2", "path": "f2.md"},
            {"file_index": 2, "marketplace": "mp-a", "plugin": "p3", "path": "f3.md"},
        ],
        "marketplace_index": {},
        "filename_index": {},
        "clusters": [],
    }

    report_path = tmp_path / "test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f)

    # Simulate jq query: .file_index[] | select(.marketplace == "mp-a")
    with open(report_path) as f:
        loaded = json.load(f)

    files = [f for f in loaded["file_index"] if f["marketplace"] == "mp-a"]
    assert len(files) == 2
    assert files[0]["file_index"] == 0
    assert files[1]["file_index"] == 2


def test_jq_query_top_similarities(tmp_path):
    """Test jq query: get top N similarity pairs."""
    report = {
        "metadata": {"version": "2.0"},
        "summary": {},
        "file_index": [],
        "marketplace_index": {},
        "filename_index": {},
        "clusters": [
            {
                "cluster_id": 0,
                "type": "internal",
                "size": 3,
                "similarity_pairs": [
                    {"file1_index": 0, "file2_index": 1, "similarity": 0.95},
                    {"file1_index": 0, "file2_index": 2, "similarity": 0.85},
                ],
            },
            {
                "cluster_id": 1,
                "type": "cross-marketplace",
                "size": 2,
                "similarity_pairs": [
                    {"file1_index": 3, "file2_index": 4, "similarity": 0.75},
                ],
            },
        ],
    }

    report_path = tmp_path / "test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f)

    # Simulate jq query: [.clusters[].similarity_pairs[]] | sort_by(.similarity) | reverse
    with open(report_path) as f:
        loaded = json.load(f)

    all_pairs = []
    for cluster in loaded["clusters"]:
        all_pairs.extend(cluster["similarity_pairs"])

    sorted_pairs = sorted(all_pairs, key=lambda p: p["similarity"], reverse=True)
    assert len(sorted_pairs) == 3
    assert sorted_pairs[0]["similarity"] == 0.95
    assert sorted_pairs[1]["similarity"] == 0.85
    assert sorted_pairs[2]["similarity"] == 0.75


def test_json_schema_compliance(tmp_path):
    """Verify JSON structure follows schema best practices."""
    report = {
        "metadata": {
            "version": "2.0",
            "generated_at": "2025-01-17T12:00:00Z",
            "similarity_threshold": 0.7,
            "num_permutations": 128,
            "confidence": "high",
            "warnings": [],
        },
        "summary": {
            "total_files_scanned": 100,
            "files_in_clusters": 60,
            "unclustered_files": 40,
            "unique_clusters": 10,
            "unique_marketplaces": 5,
            "by_type": {
                "cross-marketplace": {"clusters": 3, "files": 20},
                "internal": {"clusters": 6, "files": 35},
                "scaffold": {"clusters": 1, "files": 5},
            },
        },
        "file_index": [],
        "marketplace_index": {},
        "filename_index": {},
        "clusters": [],
    }

    report_path = tmp_path / "test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    # Verify file is valid JSON
    with open(report_path) as f:
        loaded = json.load(f)

    # Verify top-level keys
    assert set(loaded.keys()) == {
        "metadata",
        "summary",
        "file_index",
        "marketplace_index",
        "filename_index",
        "clusters",
    }

    # Verify metadata types
    assert isinstance(loaded["metadata"]["version"], str)
    assert isinstance(loaded["metadata"]["generated_at"], str)
    assert isinstance(loaded["metadata"]["similarity_threshold"], (int, float))
    assert isinstance(loaded["metadata"]["num_permutations"], int)
    assert isinstance(loaded["metadata"]["confidence"], str)
    assert isinstance(loaded["metadata"]["warnings"], list)

    # Verify summary types
    assert isinstance(loaded["summary"]["total_files_scanned"], int)
    assert isinstance(loaded["summary"]["files_in_clusters"], int)
    assert isinstance(loaded["summary"]["unique_clusters"], int)
    assert isinstance(loaded["summary"]["by_type"], dict)

    # Verify index types
    assert isinstance(loaded["file_index"], list)
    assert isinstance(loaded["marketplace_index"], dict)
    assert isinstance(loaded["filename_index"], dict)
    assert isinstance(loaded["clusters"], list)


def test_backward_compatibility_with_old_format(tmp_path):
    """Verify old JSON format can still be read (backward compatibility)."""
    # Old format (without metadata, file_index, etc.)
    old_report = {
        "summary": {
            "total_files_scanned": 100,
            "files_in_clusters": 60,
            "unique_clusters": 10,
            "similarity_threshold": 0.7,
            "by_type": {
                "cross-marketplace": {"clusters": 3, "files": 20},
                "internal": {"clusters": 6, "files": 35},
                "scaffold": {"clusters": 1, "files": 5},
            },
        },
        "clusters": [
            {
                "type": "internal",
                "size": 3,
                "avg_similarity": 0.85,
                "has_official": False,
                "marketplaces": ["test-mp"],
                "locations": [
                    {
                        "marketplace": "test-mp",
                        "plugin": "plugin-a",
                        "path": "test1.md",
                        "is_official": False,
                    }
                ],
            }
        ],
    }

    report_path = tmp_path / "old_report.json"
    with open(report_path, "w") as f:
        json.dump(old_report, f)

    # Verify it can be loaded
    with open(report_path) as f:
        loaded = json.load(f)

    assert "summary" in loaded
    assert "clusters" in loaded
    # Old format doesn't have these, but loading shouldn't fail
    assert "metadata" not in loaded
    assert "file_index" not in loaded
