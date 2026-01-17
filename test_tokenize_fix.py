#!/usr/bin/env python3
"""
Test the improved tokenize function to verify it fixes the similarity detection bug.
"""

import sys
from pathlib import Path

# Add plugin directory to path
sys.path.insert(0, str(Path(__file__).parent / "plugin"))

from plugin.librarian.core import tokenize, compute_minhash, SHINGLE_SIZE
from datasketch import MinHash, MinHashLSH


def test_yaml_frontmatter():
    """Test that YAML frontmatter doesn't cause empty shingles."""
    content = """---
name: test-skill
description: This is a test skill
triggers: ["test", "skill"]
---

# Test Skill

This is the main content of the skill.
"""

    shingles = tokenize(content)
    print("Test 1: YAML Frontmatter")
    print(f"  Content length: {len(content)}")
    print(f"  Shingles: {len(shingles)}")
    print(f"  Sample: {list(shingles)[:3]}")
    print(f"  Result: {'✅ PASS' if shingles else '❌ FAIL - empty shingles!'}")
    print()
    return bool(shingles)


def test_code_blocks():
    """Test that code blocks don't cause empty shingles."""
    content = """
# Example

Here's some code:

```python
def hello():
    print("world")
```

And some text.
"""

    shingles = tokenize(content)
    print("Test 2: Code Blocks")
    print(f"  Content length: {len(content)}")
    print(f"  Shingles: {len(shingles)}")
    print(f"  Sample: {list(shingles)[:3]}")
    print(f"  Result: {'✅ PASS' if shingles else '❌ FAIL - empty shingles!'}")
    print()
    return bool(shingles)


def test_punctuation_heavy():
    """Test content with heavy punctuation."""
    content = """
!!! WARNING !!!

This is a test:
- Item 1
- Item 2
- Item 3

See: https://example.com/path?query=value&other=thing

## Section

More content here.
"""

    shingles = tokenize(content)
    print("Test 3: Punctuation Heavy")
    print(f"  Content length: {len(content)}")
    print(f"  Shingles: {len(shingles)}")
    print(f"  Sample: {list(shingles)[:3]}")
    print(f"  Result: {'✅ PASS' if shingles else '❌ FAIL - empty shingles!'}")
    print()
    return bool(shingles)


def test_short_content():
    """Test very short content."""
    test_cases = [
        ("Empty", ""),
        ("Single word", "word"),
        ("Two words", "two words"),
        ("Three words", "three word test"),
        ("Just punctuation", "!!!@@@###"),
    ]

    print("Test 4: Short Content")
    all_passed = True
    for name, content in test_cases:
        shingles = tokenize(content)
        # Empty string expected to have empty shingles
        expected_empty = (content == "" or content.strip() == "")
        passed = (bool(shingles) != expected_empty)
        if len(content) > 0 and content.strip():
            # Non-empty content should produce shingles
            passed = bool(shingles)
        else:
            # Empty content should produce empty shingles
            passed = not bool(shingles)

        print(f"  {name}: {len(shingles)} shingles - {'✅' if passed else '❌'}")
        if not passed:
            all_passed = False

    print()
    return all_passed


def test_similarity_detection():
    """Test end-to-end similarity detection with improved tokenize."""
    print("Test 5: Similarity Detection (98% similar)")

    # Create two highly similar documents
    base = """---
name: scientific-skill
description: A skill for scientific computing
---

# Scientific Skill

This skill provides capabilities for:
- Data analysis
- Statistical computing
- Visualization
- Numerical methods

## Usage

Use this skill to analyze scientific data.

## Examples

Example 1: Load data
Example 2: Compute statistics
Example 3: Generate plots
"""

    doc1 = base + "\n\nExtra section A"
    doc2 = base + "\n\nExtra section B"

    # Tokenize
    shingles1 = tokenize(doc1)
    shingles2 = tokenize(doc2)

    if not shingles1 or not shingles2:
        print("  ❌ FAIL: Empty shingles")
        return False

    # Compute MinHash
    mh1 = compute_minhash(shingles1)
    mh2 = compute_minhash(shingles2)

    # Calculate Jaccard
    jaccard = mh1.jaccard(mh2)

    # Test LSH
    lsh = MinHashLSH(threshold=0.7, num_perm=128)
    lsh.insert("doc1", mh1)
    result = lsh.query(mh2)

    print(f"  Jaccard similarity: {jaccard:.3f}")
    print(f"  LSH found: {'doc1' in result}")
    print(f"  Result: {'✅ PASS' if 'doc1' in result else '❌ FAIL'}")
    print()

    return 'doc1' in result


def test_realistic_skill_files():
    """Test with realistic skill file content."""
    print("Test 6: Realistic Skill Files")

    # Simulate files from claude-scientific-skills
    skills = [
        """---
name: data-analysis
description: Analyze scientific datasets
---

# Data Analysis Skill

Provides data analysis capabilities including:
- Loading datasets from various formats
- Statistical analysis and hypothesis testing
- Data cleaning and preprocessing
- Visualization and reporting

## Usage

Run this skill to analyze your data.
""",
        """---
name: data-analysis
description: Analyze scientific datasets
---

# Data Analysis Skill

Provides data analysis capabilities including:
- Loading datasets from various formats
- Statistical analysis and hypothesis testing
- Data cleaning and preprocessing
- Visualization and reporting

## Usage

Use this skill for analyzing your data.
""",
    ]

    # These should be detected as similar (only minor differences)
    shingles_list = []
    for i, content in enumerate(skills):
        shingles = tokenize(content)
        if not shingles:
            print(f"  ❌ FAIL: Skill {i} produced empty shingles")
            return False
        shingles_list.append(shingles)

    # Calculate overlap
    overlap = len(shingles_list[0] & shingles_list[1])
    union = len(shingles_list[0] | shingles_list[1])
    jaccard = overlap / union if union > 0 else 0

    # Compute MinHash
    mh1 = compute_minhash(shingles_list[0])
    mh2 = compute_minhash(shingles_list[1])
    mh_jaccard = mh1.jaccard(mh2)

    # Test LSH
    lsh = MinHashLSH(threshold=0.7, num_perm=128)
    lsh.insert("skill1", mh1)
    result = lsh.query(mh2)

    print(f"  Set Jaccard: {jaccard:.3f}")
    print(f"  MinHash Jaccard: {mh_jaccard:.3f}")
    print(f"  LSH detected: {'skill1' in result}")
    print(f"  Result: {'✅ PASS' if 'skill1' in result and mh_jaccard >= 0.7 else '❌ FAIL'}")
    print()

    return 'skill1' in result and mh_jaccard >= 0.7


def main():
    print("=" * 70)
    print("TOKENIZE FIX VERIFICATION TEST")
    print("=" * 70)
    print()

    tests = [
        test_yaml_frontmatter,
        test_code_blocks,
        test_punctuation_heavy,
        test_short_content,
        test_similarity_detection,
        test_realistic_skill_files,
    ]

    results = []
    for test in tests:
        try:
            passed = test()
            results.append((test.__name__, passed))
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append((test.__name__, False))

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    print()
    print(f"Total: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("✅ All tests passed! The tokenize fix should resolve the bug.")
    else:
        print("❌ Some tests failed. Additional fixes may be needed.")

    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
