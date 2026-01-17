"""Diff functionality for comparing similar files."""

import difflib
import re
from dataclasses import dataclass

from .core import FileInfo, tokenize, compute_minhash


def normalize_for_diff(text: str) -> list[str]:
    """Normalize text for semantic comparison by removing formatting noise.

    DESIGN RATIONALE: Focus on semantic differences, not whitespace/formatting.
    - Preserves line structure for readable diffs
    - Strips trailing whitespace
    - Normalizes indentation to single spaces
    - Keeps blank lines for context

    Args:
        text: Input text to normalize

    Returns:
        List of normalized lines
    """
    lines = text.splitlines()
    normalized = []

    for line in lines:
        # Strip trailing whitespace
        line = line.rstrip()

        # Normalize leading whitespace to single spaces
        # Count leading spaces/tabs
        stripped = line.lstrip()
        if not stripped:
            # Keep blank lines as empty strings
            normalized.append("")
        else:
            # Replace leading whitespace with normalized indent
            indent_count = len(line) - len(stripped)
            # Convert tabs to spaces (4 spaces per tab) for consistent comparison
            normalized_indent = " " * (indent_count // 4)
            normalized.append(normalized_indent + stripped)

    return normalized


@dataclass
class FileDiff:
    """Represents a diff between two files."""
    file1_location: str
    file2_location: str
    similarity: float
    unified_diff: list[str]
    semantic_changes: list[dict]
    stats: dict

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        return {
            "file1": self.file1_location,
            "file2": self.file2_location,
            "similarity": self.similarity,
            "stats": self.stats,
            "semantic_changes": self.semantic_changes,
            "unified_diff": self.unified_diff,
        }


def compute_file_diff(
    file1: FileInfo,
    file2: FileInfo,
    context_lines: int = 3,
) -> FileDiff:
    """Compute detailed diff between two files.

    Args:
        file1: First file to compare
        file2: Second file to compare
        context_lines: Number of context lines for unified diff

    Returns:
        FileDiff with unified diff and semantic analysis
    """
    # Compute similarity if not already done
    similarity = 0.0
    if file1.minhash and file2.minhash:
        similarity = file1.minhash.jaccard(file2.minhash)

    # Normalize both files for semantic comparison
    lines1 = normalize_for_diff(file1.content)
    lines2 = normalize_for_diff(file2.content)

    # Generate unified diff
    unified_diff = list(difflib.unified_diff(
        lines1,
        lines2,
        fromfile=file1.location,
        tofile=file2.location,
        lineterm="",
        n=context_lines,
    ))

    # Analyze semantic changes
    semantic_changes = []

    # Track function/class definitions
    func_pattern = re.compile(r'^\s*(?:def|class|function|const|let|var)\s+(\w+)')

    funcs1 = set()
    funcs2 = set()

    for line in lines1:
        match = func_pattern.search(line)
        if match:
            funcs1.add(match.group(1))

    for line in lines2:
        match = func_pattern.search(line)
        if match:
            funcs2.add(match.group(1))

    # Functions added
    for func in sorted(funcs2 - funcs1):
        semantic_changes.append({
            "type": "function_added",
            "name": func,
        })

    # Functions removed
    for func in sorted(funcs1 - funcs2):
        semantic_changes.append({
            "type": "function_removed",
            "name": func,
        })

    # Compute stats
    stats = {
        "total_lines_file1": len(lines1),
        "total_lines_file2": len(lines2),
        "diff_lines": len([line for line in unified_diff if line.startswith(('+', '-'))]),
        "functions_added": len(funcs2 - funcs1),
        "functions_removed": len(funcs1 - funcs2),
    }

    return FileDiff(
        file1_location=file1.location,
        file2_location=file2.location,
        similarity=similarity,
        unified_diff=unified_diff,
        semantic_changes=semantic_changes,
        stats=stats,
    )


def format_diff_for_terminal(diff: FileDiff) -> str:
    """Format diff with color codes for terminal display.

    Args:
        diff: FileDiff to format

    Returns:
        Colored string for terminal output
    """
    # ANSI color codes
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    lines = []

    # Header
    lines.append(f"{BOLD}{CYAN}{'=' * 80}{RESET}")
    lines.append(f"{BOLD}File Comparison{RESET}")
    lines.append(f"{CYAN}{'=' * 80}{RESET}")
    lines.append(f"{BOLD}File 1:{RESET} {diff.file1_location}")
    lines.append(f"{BOLD}File 2:{RESET} {diff.file2_location}")
    lines.append(f"{BOLD}Similarity:{RESET} {diff.similarity * 100:.1f}%")
    lines.append("")

    # Stats
    lines.append(f"{BOLD}Statistics:{RESET}")
    lines.append(f"  Lines in file 1: {diff.stats['total_lines_file1']}")
    lines.append(f"  Lines in file 2: {diff.stats['total_lines_file2']}")
    lines.append(f"  Diff lines: {diff.stats['diff_lines']}")
    lines.append("")

    # Semantic changes
    if diff.semantic_changes:
        lines.append(f"{BOLD}Semantic Changes:{RESET}")
        for change in diff.semantic_changes:
            if change["type"] == "function_added":
                lines.append(f"  {GREEN}+ Function added:{RESET} {change['name']}")
            elif change["type"] == "function_removed":
                lines.append(f"  {RED}- Function removed:{RESET} {change['name']}")
        lines.append("")

    # Unified diff
    if diff.unified_diff:
        lines.append(f"{BOLD}Unified Diff:{RESET}")
        for line in diff.unified_diff:
            if line.startswith('+++') or line.startswith('---'):
                lines.append(f"{BOLD}{line}{RESET}")
            elif line.startswith('+'):
                lines.append(f"{GREEN}{line}{RESET}")
            elif line.startswith('-'):
                lines.append(f"{RED}{line}{RESET}")
            elif line.startswith('@@'):
                lines.append(f"{CYAN}{line}{RESET}")
            else:
                lines.append(line)

    return "\n".join(lines)
