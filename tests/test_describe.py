#!/usr/bin/env python3
"""Tests for describe command functionality."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))

from librarian.cli import (
    find_skill_file,
    analyze_skill_content,
    parse_skill_file,
    SkillInfo,
)


def test_analyze_skill_content_tools():
    """Test that tool detection works."""
    content = """
    Use the Bash tool to run commands.
    Then use Read to view files.
    WebFetch for getting URLs.
    """
    result = analyze_skill_content(content)

    assert "Bash" in result["tool_uses"]
    assert "Read" in result["tool_uses"]
    assert "WebFetch" in result["tool_uses"]
    print("Tool detection works")


def test_analyze_skill_content_complexity_low():
    """Test low complexity detection."""
    content = "Short skill with few words.\n" * 10  # ~50 lines, ~50 words
    result = analyze_skill_content(content)

    assert result["complexity_score"] == "low"
    print("Low complexity detection works")


def test_analyze_skill_content_complexity_high():
    """Test high complexity detection."""
    content = "Word " * 2000  # >1500 words
    result = analyze_skill_content(content)

    assert result["complexity_score"] == "high"
    print("High complexity detection works")


def test_analyze_skill_content_triggers():
    """Test trigger phrase extraction."""
    content = """
    Use this skill when you need to format code.
    Triggered by requests for code formatting.
    Use for cleaning up messy files.
    """
    result = analyze_skill_content(content)

    assert len(result["triggers"]) > 0
    print("Trigger extraction works")


def test_skill_info_to_dict():
    """Test SkillInfo serialization."""
    info = SkillInfo(
        name="test-skill",
        kind="skill",
        marketplace="test-mp",
        plugin="test-plugin",
        path="skills/test.md",
        description="A test skill",
        triggers=["when testing"],
        dependencies=["pytest"],
        tool_uses=["Bash", "Read"],
        line_count=50,
        word_count=200,
        complexity_score="low",
        has_frontmatter=True,
        raw_frontmatter={"name": "test-skill"},
    )

    result = info.to_dict()

    assert result["name"] == "test-skill"
    assert result["kind"] == "skill"
    assert result["location"]["marketplace"] == "test-mp"
    assert result["metrics"]["complexity"] == "low"
    assert "Bash" in result["tool_uses"]
    print("SkillInfo serialization works")


def test_analyze_dependencies():
    """Test dependency detection."""
    content = """
    This skill requires Python to run.
    It depends on the yaml library.
    Needs access to the filesystem.
    """
    result = analyze_skill_content(content)

    # Should find at least one dependency
    assert len(result["dependencies"]) > 0
    print(f"Found dependencies: {result['dependencies']}")
    print("Dependency detection works")


if __name__ == "__main__":
    print("Running describe tests...\n")

    test_analyze_skill_content_tools()
    test_analyze_skill_content_complexity_low()
    test_analyze_skill_content_complexity_high()
    test_analyze_skill_content_triggers()
    test_skill_info_to_dict()
    test_analyze_dependencies()

    print("\nAll describe tests passed!")
