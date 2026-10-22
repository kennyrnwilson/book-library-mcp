"""Shared pytest fixtures for book-library-mcp tests."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def fixture_library() -> Path:
    """Path to the in-tree mock library."""
    return Path(__file__).parent / "fixtures" / "library"


@pytest.fixture
def temp_library(tmp_path: Path, fixture_library: Path) -> Path:
    """A throwaway copy of the fixture library that tests can mutate."""
    dst = tmp_path / "library"
    shutil.copytree(fixture_library, dst)
    return dst


@pytest.fixture
def temp_git_library(temp_library: Path) -> Path:
    """temp_library as a git repo with a local bare-repo origin, so a save can push."""
    bare = temp_library.parent / "origin.git"

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(temp_library), *args], check=True, capture_output=True)

    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(bare)],
                   check=True, capture_output=True)
    subprocess.run(["git", "init", "--initial-branch=main", str(temp_library)],
                   check=True, capture_output=True)
    git("remote", "add", "origin", str(bare))
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    git("add", "-A")
    git("commit", "-m", "init")
    git("push", "-u", "origin", "main")
    return temp_library
