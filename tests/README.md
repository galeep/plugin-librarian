# Librarian Tests

This directory contains tests for the Plugin Librarian tool.

## Test Files

### test_sanity_checks.py
Unit tests for the sanity check functionality added to detect statistically improbable results.

**Tests cover:**
- 0% cluster membership warning in large ecosystems (>1000 clusters)
- Low similarity ratio warnings (<5%) for large datasets (>500 files)
- High similarity ratio warnings (>95%) for large datasets
- Suspicious 50/50 splits
- Correct confidence level assignment (high, medium, low, none)
- Edge cases (zero files, small datasets)
- JSON serialization via to_dict()

**Run with:**
```bash
source ../.venv/bin/activate
python test_sanity_checks.py
```

### test_cli_integration.py
Integration tests verifying that CLI commands properly use sanity checks.

**Tests cover:**
- Scan command includes confidence and warnings
- Compare command performs sanity checks
- JSON output structure includes required fields
- Different scenarios produce appropriate confidence levels
- Warning thresholds are correctly applied

**Run with:**
```bash
source ../.venv/bin/activate
python test_cli_integration.py
```

## Running All Tests

```bash
source ../.venv/bin/activate
python test_sanity_checks.py && python test_cli_integration.py
```

## What Was Added (Task 2)

The sanity check functionality was added to address the issue where statistically improbable results (like 0% overlap for a large marketplace) were presented confidently without warnings.

**Key changes:**
1. Added `check_similarity_sanity()` function in `core.py`
2. Added `SanityCheckResult` dataclass to hold confidence and warnings
3. Integrated sanity checks into `cmd_scan()` and `cmd_compare()`
4. Added confidence and warnings to JSON output in both commands
5. Added `--json` flag to compare command for structured output
6. Warnings display in CLI output when confidence is not high

**Thresholds:**
- Cluster membership check: triggers when >1000 clusters exist and 0% membership
- Ratio checks: trigger for datasets >500 files with <5% or >95% similarity
- 50/50 split detection: triggers for datasets >100 files
