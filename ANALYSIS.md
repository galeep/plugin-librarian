# MinHash/LSH Similarity Detection Bug Analysis

## Problem Statement
The MinHash/LSH algorithm at 70% threshold failed to detect 136/139 files from claude-scientific-skills that are 98% identical to files in other marketplaces. The algorithm reported "0 files in similarity clusters" when it should have found 136+.

## Current Implementation Analysis

### Code Locations
- `/Users/gale/work/plugin-librarian/plugin/librarian/core.py` - MinHash/LSH implementation
- `/Users/gale/work/plugin-librarian/plugin/librarian/cli.py` - scan command (lines 548-691)
- `/Users/gale/work/plugin-librarian/similarity.py` - Standalone similarity script

### Parameters
- `SIMILARITY_THRESHOLD = 0.7` (70%)
- `NUM_PERM = 128` (number of MinHash permutations)
- `SHINGLE_SIZE = 3` (3-word shingles)
- Uses `datasketch` library's `MinHashLSH`

### Current Flow
1. Scan all `.md` files >100 characters
2. Tokenize content → shingles
3. Compute MinHash signature for each file
4. Insert into LSH index
5. Query LSH for each file to find similar files
6. Build clusters from query results

## Root Cause Candidates

### 1. Aggressive Tokenization
**Location**: `core.py` lines 129-144

```python
def tokenize(text: str) -> set[str]:
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)  # ← REMOVES ALL PUNCTUATION

    words = text.split()
    if len(words) < SHINGLE_SIZE:
        return set(words)  # ← SHORT DOCUMENTS GET WORD-ONLY SHINGLES

    shingles = set()
    for i in range(len(words) - SHINGLE_SIZE + 1):
        shingle = ' '.join(words[i:i + SHINGLE_SIZE])
        shingles.add(shingle)

    return shingles
```

**Issues**:
- Removes ALL punctuation including dashes, colons, and code syntax
- For skill files with YAML frontmatter, code blocks, and markdown, this strips meaningful content
- Files with < 3 words return individual words, not shingles
- Short documents or documents with few words after processing might return empty sets

### 2. Empty Shingle Sets
**Location**: `cli.py` lines 598-602

```python
for i, f in enumerate(files):
    shingles = tokenize(f.content)
    if shingles:  # ← FILES WITH EMPTY SHINGLES ARE SKIPPED
        f.minhash = compute_minhash(shingles)
        lsh.insert(str(i), f.minhash)
```

**Issue**: If tokenization produces empty shingles (e.g., files with only punctuation/code), the file is never inserted into LSH and can't be found in queries.

### 3. LSH Threshold Sensitivity
**Location**: `cli.py` line 596

```python
lsh = MinHashLSH(threshold=SIMILARITY_THRESHOLD, num_perm=NUM_PERM)
```

**Theory**: The datasketch library automatically calculates bands `b` and rows per band `r` based on threshold. For threshold=0.7, the probability curve might not be optimal for detecting 98% similar files in all cases.

The probability of LSH collision is: `P = 1 - (1 - s^r)^b` where `s` is similarity.

For 70% threshold with NUM_PERM=128, typical values might be:
- b ≈ 20, r ≈ 6 (for example)
- At s=0.70: P ≈ 0.50 (as intended)
- At s=0.98: P ≈ 0.999+ (should work)

However, edge cases or implementation details could cause misses.

### 4. Cluster Detection Logic
**Location**: `cli.py` lines 608-616

```python
for i, f in enumerate(files):
    if i in assigned or f.minhash is None:
        continue

    result = lsh.query(f.minhash)
    similar_indices = [int(r) for r in result]

    if len(similar_indices) > 1:  # ← REQUIRES 2+ FILES
        cluster_files = [files[j] for j in similar_indices if files[j].minhash is not None]
```

**Note**: This logic is correct. LSH.query() returns the queried file plus similar files, so `> 1` means "has at least one similar file besides itself."

## Most Likely Root Cause

**Hypothesis: Aggressive Tokenization + Empty Shingles**

1. Skill files often have YAML frontmatter with dashes, colons
2. Files may have code blocks, markdown syntax
3. Tokenization removes ALL punctuation: `re.sub(r'[^\w\s]', '', text)`
4. After removing punctuation and lowercasing, some files might have very few unique words
5. Files with < 3 words return empty sets or individual words
6. These files never get inserted into LSH
7. Result: "0 files in clusters" for affected files

## Proposed Fix

### Option 1: Less Aggressive Tokenization (RECOMMENDED)
**Preserve meaningful punctuation and structure**:

```python
def tokenize(text: str) -> set[str]:
    # Normalize whitespace but preserve structure
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)

    # Keep alphanumeric, spaces, and dashes (for YAML keys, markdown headers)
    # Remove only truly meaningless punctuation
    text = re.sub(r'[^a-z0-9\s\-]', '', text)

    # Split and filter empty strings
    words = [w for w in text.split() if w]

    # Handle short documents
    if len(words) < SHINGLE_SIZE:
        if words:
            return set(words)
        else:
            # Fallback: use character-level shingles
            return set(text[i:i+SHINGLE_SIZE] for i in range(len(text) - SHINGLE_SIZE + 1))

    # Generate word-level shingles
    shingles = set()
    for i in range(len(words) - SHINGLE_SIZE + 1):
        shingle = ' '.join(words[i:i + SHINGLE_SIZE])
        shingles.add(shingle)

    return shingles
```

### Option 2: Increase NUM_PERM
**Higher permutations = more accurate similarity detection**:

Change `NUM_PERM = 128` to `NUM_PERM = 256`

Tradeoff: 2x memory and compute, but more accurate.

### Option 3: Hybrid Tokenization
**Use both word and character shingles**:

```python
def tokenize(text: str) -> set[str]:
    # Word-level shingles
    word_shingles = tokenize_words(text)

    # If too few words, add character-level shingles
    if len(word_shingles) < 10:
        char_shingles = tokenize_chars(text)
        return word_shingles | char_shingles

    return word_shingles
```

## Recommended Implementation

**Fix 1: Improve tokenization** (core.py)
- Preserve dashes and basic structure
- Add fallback for short documents
- Ensure no file produces empty shingle set

**Fix 2: Add validation** (cli.py)
- Log warning when files have < 10 shingles
- Track files with empty shingles
- Output diagnostic info in summary

**Fix 3: Add test coverage**
- Test suite with known duplicate files
- Verify 98% similar files are detected
- Test edge cases: short files, code-heavy files, frontmatter-only files

## Testing Strategy
1. Create test suite with 139 known duplicate files
2. Run scan and verify 136+ appear in clusters
3. Measure recall on known duplicates (target: >95%)
4. Test edge cases: 70%, 69%, 71% similarity
5. Verify false positive rate is acceptable

## Success Criteria
- Files with >70% similarity appear in clusters
- 136+ of 139 claude-scientific-skills files detected
- Recall >95% on known duplicates
- No regression on existing detections
