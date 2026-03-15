#!/usr/bin/env python3
"""Tests for progress bar functionality."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))

from librarian.core import create_progress_bar
from rich.progress import Progress


def test_create_progress_bar():
    """Test that progress bar can be created."""
    progress = create_progress_bar()
    assert isinstance(progress, Progress)
    print("✓ Progress bar creation works")


def test_progress_bar_context_manager():
    """Test that progress bar works as context manager."""
    with create_progress_bar() as progress:
        task = progress.add_task("Test task", total=10)
        for i in range(10):
            progress.advance(task)
    print("✓ Progress bar context manager works")


def test_progress_bar_display():
    """Test that progress bar displays correctly (visual test)."""
    import time

    print("\nVisual test of progress bar:")
    with create_progress_bar() as progress:
        task1 = progress.add_task("Processing files", total=50)
        task2 = progress.add_task("Building index", total=30)

        for i in range(50):
            progress.advance(task1)
            if i < 30:
                progress.advance(task2)
            time.sleep(0.01)  # Small delay to see animation

    print("✓ Progress bar display test complete")


if __name__ == "__main__":
    print("Running progress bar tests...\n")

    test_create_progress_bar()
    test_progress_bar_context_manager()
    test_progress_bar_display()

    print("\n✓ All progress bar tests passed!")
