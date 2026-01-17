#!/usr/bin/env python3
"""
Debug script to identify why MinHashLSH is not finding similar files.

Tests the LSH band configuration and probability for 70% threshold.
"""

from datasketch import MinHash, MinHashLSH
import math

# Current parameters
SIMILARITY_THRESHOLD = 0.7
NUM_PERM = 128
SHINGLE_SIZE = 3


def test_lsh_probability():
    """
    Test the probability that LSH will detect files at different similarity levels.

    For LSH with threshold t, the probability of collision depends on:
    - Number of bands (b)
    - Rows per band (r)
    - b * r = num_perm

    The probability curve is S-shaped around threshold t.
    At similarity = t, probability should be ~50%.
    """
    print("=" * 70)
    print("LSH Probability Analysis")
    print("=" * 70)
    print(f"Parameters: threshold={SIMILARITY_THRESHOLD}, num_perm={NUM_PERM}")
    print()

    # MinHashLSH automatically calculates optimal b and r
    lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)

    # Access internal parameters
    b = lsh.b  # number of bands
    r = lsh.r  # rows per band

    print(f"LSH Configuration:")
    print(f"  Bands (b): {b}")
    print(f"  Rows per band (r): {r}")
    print(f"  b * r = {b * r} (should equal {NUM_PERM})")
    print()

    # Calculate probability of collision at various similarity levels
    print("Probability of detection at different similarity levels:")
    print(f"{'Similarity':<15} {'Probability':<15} {'Expected Detection'}")
    print("-" * 50)

    for sim in [0.50, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.98]:
        # Probability that at least one band matches
        # P(collision) = 1 - (1 - sim^r)^b
        prob = 1 - (1 - sim**r)**b
        detection = "YES" if prob > 0.5 else "MAYBE" if prob > 0.1 else "NO"
        print(f"{sim:<15.2f} {prob:<15.3f} {detection}")

    print()
    return b, r


def test_identical_files():
    """Test that LSH can find identical files."""
    print("=" * 70)
    print("Test 1: Identical Files")
    print("=" * 70)

    text = "This is a test document with enough content to create meaningful shingles."

    # Create two identical MinHash signatures
    m1 = MinHash(num_perm=NUM_PERM)
    m2 = MinHash(num_perm=NUM_PERM)

    for word in text.split():
        m1.update(word.encode('utf-8'))
        m2.update(word.encode('utf-8'))

    similarity = m1.jaccard(m2)
    print(f"Jaccard similarity: {similarity:.3f}")

    # Insert into LSH
    lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)
    lsh.insert("doc1", m1)

    # Query
    result = lsh.query(m2)
    print(f"Query result: {list(result)}")
    print(f"Found: {'YES' if 'doc1' in result else 'NO'}")
    print()


def test_70_percent_similar():
    """Test files that are 70% similar."""
    print("=" * 70)
    print("Test 2: 70% Similar Files")
    print("=" * 70)

    # Create two documents with 70% overlap
    base_words = ["word" + str(i) for i in range(100)]
    doc1_words = base_words[:70] + ["unique1_" + str(i) for i in range(30)]
    doc2_words = base_words[:70] + ["unique2_" + str(i) for i in range(30)]

    m1 = MinHash(num_perm=NUM_PERM)
    m2 = MinHash(num_perm=NUM_PERM)

    for word in doc1_words:
        m1.update(word.encode('utf-8'))

    for word in doc2_words:
        m2.update(word.encode('utf-8'))

    similarity = m1.jaccard(m2)
    print(f"Jaccard similarity: {similarity:.3f}")

    # Insert into LSH
    lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)
    lsh.insert("doc1", m1)

    # Query
    result = lsh.query(m2)
    print(f"Query result: {list(result)}")
    print(f"Found: {'YES' if 'doc1' in result else 'NO'}")
    print()


def test_98_percent_similar():
    """Test files that are 98% similar (the reported failure case)."""
    print("=" * 70)
    print("Test 3: 98% Similar Files (Failure Case)")
    print("=" * 70)

    # Create two documents with 98% overlap
    base_words = ["word" + str(i) for i in range(100)]
    doc1_words = base_words[:98] + ["unique1_a", "unique1_b"]
    doc2_words = base_words[:98] + ["unique2_a", "unique2_b"]

    m1 = MinHash(num_perm=NUM_PERM)
    m2 = MinHash(num_perm=NUM_PERM)

    for word in doc1_words:
        m1.update(word.encode('utf-8'))

    for word in doc2_words:
        m2.update(word.encode('utf-8'))

    similarity = m1.jaccard(m2)
    print(f"Jaccard similarity: {similarity:.3f}")

    # Insert into LSH
    lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)
    lsh.insert("doc1", m1)

    # Query
    result = lsh.query(m2)
    print(f"Query result: {list(result)}")
    print(f"Found: {'YES' if 'doc1' in result else 'NO'}")
    print()


def test_shingling():
    """Test the tokenization/shingling function."""
    print("=" * 70)
    print("Test 4: Shingling Function")
    print("=" * 70)

    from plugin.librarian.core import tokenize

    text1 = """This is a test document with enough content to create meaningful shingles.
    It has multiple lines and various punctuation marks!
    """

    text2 = """This is a test document with enough content to create meaningful shingles.
    It has multiple lines and slightly different punctuation.
    """

    shingles1 = tokenize(text1)
    shingles2 = tokenize(text2)

    print(f"Text 1 shingles: {len(shingles1)}")
    print(f"Text 2 shingles: {len(shingles2)}")

    if shingles1 and shingles2:
        overlap = len(shingles1 & shingles2)
        union = len(shingles1 | shingles2)
        jaccard = overlap / union if union > 0 else 0
        print(f"Overlap: {overlap}")
        print(f"Union: {union}")
        print(f"Jaccard similarity: {jaccard:.3f}")

        print(f"\nSample shingles from text 1 (first 5):")
        for s in list(shingles1)[:5]:
            print(f"  '{s}'")
    else:
        print("ERROR: Empty shingle set!")
    print()


def main():
    print("\n")
    print("MinHash/LSH Debugging Tool")
    print("Investigating why 98% similar files are not being detected")
    print("\n")

    # Run all tests
    b, r = test_lsh_probability()
    test_identical_files()
    test_70_percent_similar()
    test_98_percent_similar()
    test_shingling()

    print("=" * 70)
    print("ANALYSIS")
    print("=" * 70)
    print()
    print("The LSH parameters should detect files with 98% similarity.")
    print("If the tests above show 'NO' for 98% similar files, the issue is:")
    print()
    print("1. Band/Row configuration is wrong for the threshold")
    print("2. Shingling is creating different sets for similar content")
    print("3. Files are being inserted but not queried correctly")
    print()
    print(f"With b={b}, r={r}:")
    print(f"  - At 70% similarity, detection probability should be ~50%")
    print(f"  - At 98% similarity, detection probability should be >99%")
    print()


if __name__ == "__main__":
    main()
