"""Shared pytest fixtures for book-library-mcp tests."""

from pathlib import Path

import pytest


@pytest.fixture
def fixture_library() -> Path:
    """Path to the in-tree mock library."""
    return Path(__file__).parent / "fixtures" / "library"
