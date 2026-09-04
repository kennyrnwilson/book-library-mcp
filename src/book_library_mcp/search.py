"""Ripgrep wrapper for full-text search across the book library."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Fallback locations checked when `rg` isn't on PATH. Covers GUI-launched
# processes (Claude Desktop, launchd plists) where /opt/homebrew/bin is
# typically absent from PATH on Apple Silicon Macs.
_RG_FALLBACK_PATHS = (
    "/opt/homebrew/bin/rg",
    "/usr/local/bin/rg",
)


def _resolve_rg() -> str | None:
    rg = shutil.which("rg")
    if rg:
        return rg
    for candidate in _RG_FALLBACK_PATHS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


@dataclass(frozen=True)
class SearchHit:
    """One ripgrep match."""

    slug: str
    relative_path: str  # path within the book directory
    line_number: int
    line: str


def search_library(library_root: Path, query: str, max_results: int = 50) -> list[SearchHit]:
    """Run ripgrep across library_root for `query`, return up to max_results hits.

    Searches markdown and txt files only.
    """
    if not query.strip():
        return []
    rg = _resolve_rg()
    if rg is None:
        raise RuntimeError("ripgrep (`rg`) not found on PATH or in /opt/homebrew/bin, /usr/local/bin")

    cmd = [
        rg,
        "--no-heading",
        "--line-number",
        "--max-count",
        str(max_results),
        "--type-add",
        "doc:*.md",
        "--type-add",
        "doc:*.txt",
        "--type",
        "doc",
        "--",
        query,
        str(library_root),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    # rg exits 1 when there are no matches — that's not an error for us.
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"ripgrep failed: {proc.stderr.strip()}")

    hits: list[SearchHit] = []
    for raw in proc.stdout.splitlines():
        # format: <abs-path>:<line-number>:<line>
        try:
            path_str, line_no_str, line = raw.split(":", 2)
        except ValueError:
            continue
        abs_path = Path(path_str)
        try:
            rel = abs_path.relative_to(library_root)
        except ValueError:
            continue
        slug = rel.parts[0]
        relative_path = str(Path(*rel.parts[1:]))
        hits.append(
            SearchHit(
                slug=slug,
                relative_path=relative_path,
                line_number=int(line_no_str),
                line=line,
            )
        )
        if len(hits) >= max_results:
            break
    return hits
