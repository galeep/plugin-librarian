#!/usr/bin/env python3
"""
Test to reproduce the similarity detection failure.

Based on the bug report: 136/139 files from claude-scientific-skills
that are 98% identical to files in other marketplaces were not detected.
"""

import sys
from pathlib import Path
from datasketch import MinHash, MinHashLSH

# Add plugin directory to path
sys.path.insert(0, str(Path(__file__).parent / "plugin"))

from plugin.librarian.core import (
    tokenize,
    compute_minhash,
    SIMILARITY_THRESHOLD,
    NUM_PERM,
)


def test_tokenize_on_real_content():
    """Test tokenize on actual skill file content."""
    # Simulate a typical skill file with frontmatter and markdown
    skill_content = """---
name: test-skill
description: This is a test skill
---

# Test Skill

This skill does something useful.

## Usage

Run this skill to accomplish a task.

```python
def example():
    print("Hello world")
```

## Examples

- Example 1
- Example 2
"""

    shingles = tokenize(skill_content)
    print(f"Test 1: Tokenize typical skill file")
    print(f"  Content length: {len(skill_content)}")
    print(f"  Shingles generated: {len(shingles)}")
    print(f"  Sample shingles: {list(shingles)[:5]}")
    print()

    if not shingles:
        print("  ❌ FAIL: Empty shingle set!")
        return False

    return True


def test_similar_files_detection():
    """Test that LSH can detect 98% similar files."""
    print("Test 2: Detect 98% similar files")

    # Create two highly similar documents
    base_content = "\n".join([f"line {i} with content" for i in range(100)])
    doc1_content = base_content + "\n\nextra line 1\nextra line 2"
    doc2_content = base_content + "\n\ndifferent line 1\ndifferent line 2"

    # Tokenize
    shingles1 = tokenize(doc1_content)
    shingles2 = tokenize(doc2_content)

    print(f"  Doc1 shingles: {len(shingles1)}")
    print(f"  Doc2 shingles: {len(shingles2)}")

    if not shingles1 or not shingles2:
        print("  ❌ FAIL: Empty shingle sets!")
        return False

    # Compute MinHash
    mh1 = compute_minhash(shingles1)
    mh2 = compute_minhash(shingles2)

    # Calculate Jaccard similarity
    jaccard_sim = mh1.jaccard(mh2)
    print(f"  Jaccard similarity: {jaccard_sim:.3f}")

    # Test LSH
    lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)
    lsh.insert("doc1", mh1)

    result = lsh.query(mh2)
    found = "doc1" in result

    print(f"  LSH query result: {list(result)}")
    print(f"  Found in LSH: {'✅ YES' if found else '❌ NO'}")

    if jaccard_sim >= SIMILARITY_THRESHOLD and not found:
        print(f"  ❌ FAIL: {jaccard_sim:.0%} similar but not detected by LSH!")
        return False

    print()
    return True


def test_empty_shingles_scenario():
    """Test what happens when content produces empty shingles."""
    print("Test 3: Empty shingles scenario")

    # Content that might produce empty/minimal shingles
    test_cases = [
        ("Empty string", ""),
        ("Short string", "hi"),
        ("Just punctuation", "!@#$%^&*()"),
        ("Just whitespace", "   \n\n\t  "),
        ("Single word", "word"),
        ("Two words", "two words"),
    ]

    failed = False
    for name, content in test_cases:
        shingles = tokenize(content)
        print(f"  {name}: {len(shingles)} shingles")
        if len(content) < 100:  # These are expected to have few shingles
            continue
        if not shingles and len(content) >= 100:
            print(f"    ⚠️  WARNING: Substantial content but no shingles!")
            failed = True

    print()
    return not failed


def test_lsh_configuration():
    """Test LSH band/row configuration."""
    print("Test 4: LSH Configuration")

    lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)

    # Access internal parameters
    b = lsh.b  # bands
    r = lsh.r  # rows per band

    print(f"  Threshold: {SIMILARITY_THRESHOLD}")
    print(f"  Num permutations: {NUM_PERM}")
    print(f"  Bands: {b}")
    print(f"  Rows per band: {r}")
    print(f"  b × r = {b * r}")

    # Calculate probability of detection at threshold
    prob_at_threshold = 1 - (1 - SIMILARITY_THRESHOLD**r) ** b
    prob_at_98 = 1 - (1 - 0.98**r) ** b

    print(f"  Probability of detection at {SIMILARITY_THRESHOLD:.0%}: {prob_at_threshold:.2%}")
    print(f"  Probability of detection at 98%: {prob_at_98:.2%}")

    if prob_at_98 < 0.95:
        print(f"  ⚠️  WARNING: Low probability ({prob_at_98:.0%}) at 98% similarity!")
        print(f"     This could cause the reported bug.")

    print()
    return True


def test_cross_file_detection():
    """Simulate the actual bug scenario: multiple files, some similar."""
    print("Test 5: Cross-file detection (bug reproduction)")

    # Simulate 10 files, where 3 are 98% similar
    files = []

    # Base content for similar files
    base = "\n".join([f"common content line {i}" for i in range(50)])

    # Create 3 files that are 98% similar
    files.append(("file0.md", base + "\n\nvariant A"))
    files.append(("file1.md", base + "\n\nvariant B"))
    files.append(("file2.md", base + "\n\nvariant C"))

    # Create 7 dissimilar files
    for i in range(3, 10):
        unique_content = "\n".join([f"unique content {i} line {j}" for j in range(50)])
        files.append((f"file{i}.md", unique_content))

    print(f"  Created {len(files)} test files")
    print(f"  Expected: files 0-2 should cluster (98% similar)")

    # Build LSH index
    lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)
    minhashes = []

    for i, (name, content) in enumerate(files):
        shingles = tokenize(content)
        if not shingles:
            print(f"    ⚠️  {name}: Empty shingles!")
            minhashes.append(None)
            continue

        mh = compute_minhash(shingles)
        minhashes.append(mh)
        lsh.insert(str(i), mh)

    # Query and check clustering
    clusters_found = 0
    for i, (name, content) in enumerate(files):
        if minhashes[i] is None:
            continue

        result = lsh.query(minhashes[i])
        similar_count = len(result)

        if similar_count > 1:  # Found a cluster
            clusters_found += 1
            print(f"    {name}: found {similar_count} similar files (indices: {list(result)})")

    print(f"  Files in clusters: {clusters_found}")

    # For the 3 similar files, each should find the other 2 (plus itself = 3 total)
    expected_in_cluster = 3
    if clusters_found < expected_in_cluster:
        print(f"  ❌ FAIL: Expected {expected_in_cluster} files in cluster, found {clusters_found}")
        return False

    print(f"  ✅ PASS: Cluster detection working")
    print()
    return True


def main():
    print("=" * 70)
    print("SIMILARITY DETECTION BUG REPRODUCTION TEST")
    print("=" * 70)
    print()

    tests = [
        test_tokenize_on_real_content,
        test_similar_files_detection,
        test_empty_shingles_scenario,
        test_lsh_configuration,
        test_cross_file_detection,
    ]

    results = []
    for test in tests:
        try:
            passed = test()
            results.append((test.__name__, passed))
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            results.append((test.__name__, False))

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)
    print()
    if all_passed:
        print("All tests passed. The bug may be fixed or requires different test.")
    else:
        print("Some tests failed. Bug confirmed or test needs adjustment.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
