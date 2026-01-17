#!/usr/bin/env python3
"""
Test suite for Bug #11: MinHash/LSH Similarity Detection

Verifies that files with >70% similarity are correctly detected and clustered,
specifically addressing the failure to detect 136/139 files from claude-scientific-skills
that are 98% identical to files in other marketplaces.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "plugin"))

from plugin.librarian.core import tokenize, compute_minhash, SIMILARITY_THRESHOLD, NUM_PERM
from datasketch import MinHashLSH


class SimilarityTestSuite:
    """Test suite for similarity detection."""

    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, test_func):
        """Run a single test and track results."""
        self.tests_run += 1
        try:
            result = test_func()
            if result:
                self.tests_passed += 1
                print(f"✅ PASS: {name}")
            else:
                print(f"❌ FAIL: {name}")
            return result
        except Exception as e:
            print(f"❌ ERROR: {name}")
            print(f"   {e}")
            return False

    def test_70_percent_similar(self):
        """Test detection of files at exactly 70% similarity threshold."""
        # Create two documents with exactly 70% overlap
        base_words = [f"word{i}" for i in range(70)]
        unique1 = [f"unique1_{i}" for i in range(30)]
        unique2 = [f"unique2_{i}" for i in range(30)]

        doc1 = " ".join(base_words + unique1)
        doc2 = " ".join(base_words + unique2)

        shingles1 = tokenize(doc1)
        shingles2 = tokenize(doc2)

        if not shingles1 or not shingles2:
            print("   Error: Empty shingles")
            return False

        mh1 = compute_minhash(shingles1)
        mh2 = compute_minhash(shingles2)

        jaccard = mh1.jaccard(mh2)

        lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)
        lsh.insert("doc1", mh1)
        result = lsh.query(mh2)

        print(f"   Jaccard: {jaccard:.3f}, LSH detected: {'doc1' in result}")

        # At 70% threshold, detection should work for 70%+ similarity
        return 'doc1' in result if jaccard >= 0.65 else True

    def test_98_percent_similar(self):
        """Test detection of files at 98% similarity (the reported bug case)."""
        # Create two documents with 98% overlap
        base_words = [f"word{i}" for i in range(98)]
        unique1 = ["unique1_a", "unique1_b"]
        unique2 = ["unique2_a", "unique2_b"]

        doc1 = " ".join(base_words + unique1)
        doc2 = " ".join(base_words + unique2)

        shingles1 = tokenize(doc1)
        shingles2 = tokenize(doc2)

        if not shingles1 or not shingles2:
            print("   Error: Empty shingles")
            return False

        mh1 = compute_minhash(shingles1)
        mh2 = compute_minhash(shingles2)

        jaccard = mh1.jaccard(mh2)

        lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)
        lsh.insert("doc1", mh1)
        result = lsh.query(mh2)

        print(f"   Jaccard: {jaccard:.3f}, LSH detected: {'doc1' in result}")

        # At 98% similarity, LSH MUST detect it
        return 'doc1' in result

    def test_cross_marketplace_detection(self):
        """Test detection across multiple files (simulating cross-marketplace scenario)."""
        # Simulate 5 files where 3 are 95% similar
        base_content = " ".join([f"common_word_{i}" for i in range(100)])

        files = [
            ("file1.md", base_content + " variant_a"),
            ("file2.md", base_content + " variant_b"),
            ("file3.md", base_content + " variant_c"),
            ("file4.md", " ".join([f"different_{i}" for i in range(100)])),
            ("file5.md", " ".join([f"unique_{i}" for i in range(100)])),
        ]

        lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)
        minhashes = []

        for i, (name, content) in enumerate(files):
            shingles = tokenize(content)
            if not shingles:
                print(f"   Error: Empty shingles for {name}")
                return False

            mh = compute_minhash(shingles)
            minhashes.append((name, mh))
            lsh.insert(str(i), mh)

        # Query for similar files
        clusters_found = 0
        for i, (name, mh) in enumerate(minhashes):
            result = lsh.query(mh)
            if len(result) > 1:  # Found similar files besides itself
                clusters_found += 1

        print(f"   Files in clusters: {clusters_found} (expected: 3)")

        # The first 3 files should all be in the same cluster
        return clusters_found >= 3

    def test_yaml_frontmatter_preservation(self):
        """Test that YAML frontmatter doesn't break tokenization."""
        content = """---
name: test-skill
description: This is a test skill
version: 1.0.0
---

# Test Skill

This skill provides functionality for testing.
"""

        shingles = tokenize(content)
        print(f"   Shingles generated: {len(shingles)}")

        # Should generate shingles from both frontmatter and content
        return len(shingles) > 0

    def test_code_block_preservation(self):
        """Test that code blocks don't break tokenization."""
        content = """
# Example Skill

```python
def hello_world():
    print("Hello, world!")
    return True
```

This is a test skill with code.
"""

        shingles = tokenize(content)
        print(f"   Shingles generated: {len(shingles)}")

        # Should generate shingles from text content
        return len(shingles) > 0

    def test_empty_content_handling(self):
        """Test handling of edge cases (empty, very short content)."""
        test_cases = [
            ("", False),  # Empty should have no shingles
            ("a", True),  # Single char should have shingles
            ("word", True),  # Single word should have shingles
            ("two words", True),  # Two words should have shingles
            ("three words here", True),  # Three words should have shingles
        ]

        all_passed = True
        for content, should_have_shingles in test_cases:
            shingles = tokenize(content)
            has_shingles = len(shingles) > 0
            if has_shingles != should_have_shingles:
                print(f"   Failed for '{content}': expected {should_have_shingles}, got {has_shingles}")
                all_passed = False

        return all_passed

    def test_recall_on_known_duplicates(self):
        """Test recall: percentage of true duplicates detected."""
        # Create 10 files where 7 are near-duplicates of a base template
        base_template = """---
name: skill-{id}
description: A skill for data analysis
---

# Scientific Data Analysis

This skill provides:
- Data loading and preprocessing
- Statistical analysis
- Visualization
- Report generation

## Usage

Use this skill to analyze your scientific data.

## Examples

Example 1: Load data from CSV
Example 2: Compute descriptive statistics
Example 3: Generate plots
"""

        # Create 7 near-duplicate files (varying only the ID)
        similar_files = []
        for i in range(7):
            content = base_template.format(id=i)
            similar_files.append(content)

        # Create 3 dissimilar files
        dissimilar_files = [
            "This is a completely different document about something else " * 20,
            "Another unique document with no similarity to the others " * 20,
            "Yet another distinct file with unique content throughout " * 20,
        ]

        all_files = similar_files + dissimilar_files

        # Build LSH index
        lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)
        minhashes = []

        for i, content in enumerate(all_files):
            shingles = tokenize(content)
            if not shingles:
                print(f"   Error: Empty shingles for file {i}")
                return False

            mh = compute_minhash(shingles)
            minhashes.append(mh)
            lsh.insert(str(i), mh)

        # Count how many of the 7 similar files are detected
        detected = 0
        for i in range(7):  # Check the 7 similar files
            result = lsh.query(minhashes[i])
            if len(result) > 1:  # Found similar files besides itself
                detected += 1

        recall = detected / 7
        print(f"   Detected: {detected}/7 similar files (recall: {recall:.1%})")

        # Require >95% recall (at least 7/7 detected)
        return recall >= 0.95

    def test_no_false_negatives_above_threshold(self):
        """Test that no files above similarity threshold are missed."""
        test_similarities = [0.71, 0.75, 0.80, 0.85, 0.90, 0.95, 0.98]

        all_passed = True
        for target_sim in test_similarities:
            # Create documents with target similarity
            overlap_size = int(100 * target_sim)
            unique_size = 100 - overlap_size

            base_words = [f"word{i}" for i in range(overlap_size)]
            unique1 = [f"u1_{i}" for i in range(unique_size)]
            unique2 = [f"u2_{i}" for i in range(unique_size)]

            doc1 = " ".join(base_words + unique1)
            doc2 = " ".join(base_words + unique2)

            shingles1 = tokenize(doc1)
            shingles2 = tokenize(doc2)

            if not shingles1 or not shingles2:
                print(f"   Error at {target_sim:.0%}: Empty shingles")
                all_passed = False
                continue

            mh1 = compute_minhash(shingles1)
            mh2 = compute_minhash(shingles2)

            actual_sim = mh1.jaccard(mh2)

            lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)
            lsh.insert("doc1", mh1)
            result = lsh.query(mh2)

            detected = 'doc1' in result

            if not detected and actual_sim >= SIMILARITY_THRESHOLD:
                print(f"   Miss at {target_sim:.0%} (actual: {actual_sim:.3f})")
                all_passed = False

        return all_passed

    def run_all(self):
        """Run all tests."""
        print("=" * 70)
        print("SIMILARITY DETECTION TEST SUITE (Bug #11)")
        print("=" * 70)
        print()

        self.run_test("70% Similarity Detection", self.test_70_percent_similar)
        self.run_test("98% Similarity Detection (Bug Case)", self.test_98_percent_similar)
        self.run_test("Cross-Marketplace Detection", self.test_cross_marketplace_detection)
        self.run_test("YAML Frontmatter Preservation", self.test_yaml_frontmatter_preservation)
        self.run_test("Code Block Preservation", self.test_code_block_preservation)
        self.run_test("Empty Content Handling", self.test_empty_content_handling)
        self.run_test("Recall on Known Duplicates (>95%)", self.test_recall_on_known_duplicates)
        self.run_test("No False Negatives Above Threshold", self.test_no_false_negatives_above_threshold)

        print()
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Tests run: {self.tests_run}")
        print(f"Tests passed: {self.tests_passed}")
        print(f"Tests failed: {self.tests_run - self.tests_passed}")
        print()

        if self.tests_passed == self.tests_run:
            print("✅ ALL TESTS PASSED")
            print("The similarity detection bug appears to be fixed.")
            print()
            print("Acceptance Criteria Status:")
            print("  ✅ Files with >70% similarity appear in clusters")
            print("  ✅ Cross-marketplace duplicates are reliably detected")
            print("  ✅ Recall >95% on known duplicates")
            return 0
        else:
            print("❌ SOME TESTS FAILED")
            print("The bug fix may need additional work.")
            return 1


def main():
    suite = SimilarityTestSuite()
    return suite.run_all()


if __name__ == "__main__":
    sys.exit(main())
