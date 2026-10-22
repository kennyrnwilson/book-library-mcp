"""Git operations for the book library: pending changes and the explicit save.

The same explicit-save model as knowledge-library-mcp: the write tools only
touch disk, and `save_changes` here is the only path to git history.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SaveResult:
    committed: bool
    pushed: bool
    commit_sha: str = ""
    message: str = ""
    pending: list[dict] = field(default_factory=list)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def list_pending_changes(library_root: Path) -> list[dict]:
    """Return parsed `git status --porcelain` for the library."""
    proc = _run(["git", "status", "--porcelain", "-z"], library_root)
    if proc.returncode != 0:
        raise RuntimeError(f"git status failed: {proc.stderr.strip()}")
    out: list[dict] = []
    for entry in proc.stdout.split("\x00"):
        if len(entry) < 4:
            continue
        out.append({"status": entry[:2], "path": entry[3:]})
    return out


def _autogenerate_message(pending: list[dict]) -> str:
    paths = [p["path"] for p in pending]
    if len(paths) == 1:
        return f"notes: {paths[0]}"
    head = paths[:3]
    extra = len(paths) - len(head)
    suffix = f" (+{extra} more)" if extra > 0 else ""
    return f"notes: {', '.join(head)}{suffix}"


def _on_main(library_root: Path) -> bool:
    proc = _run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], library_root)
    return proc.returncode == 0 and proc.stdout.strip() == "main"


def _ahead_of_origin(library_root: Path) -> int:
    proc = _run(["git", "rev-list", "--count", "origin/main..HEAD"], library_root)
    return int(proc.stdout.strip()) if proc.returncode == 0 else 0


def save_changes(library_root: Path, message: str | None = None) -> SaveResult:
    """Stage all changes, commit, rebase onto origin/main, push.

    Also pushes commits left local by an earlier failed push. No-op only when
    there is nothing to commit or push.
    """
    if not _on_main(library_root):
        raise RuntimeError("save only runs with `main` checked out; nothing was committed")
    pending = list_pending_changes(library_root)
    commit_msg = ""
    if pending:
        add = _run(["git", "add", "-A"], library_root)
        if add.returncode != 0:
            raise RuntimeError(f"git add failed: {add.stderr.strip()}")
        commit_msg = message or _autogenerate_message(pending)
        commit = _run(["git", "commit", "-m", commit_msg], library_root)
        if commit.returncode != 0:
            raise RuntimeError(f"git commit failed: {commit.stderr.strip()}")

    fetch = _run(["git", "fetch", "origin", "main"], library_root)
    if fetch.returncode != 0:
        raise RuntimeError(
            f"git fetch failed (nothing pushed; commits stay local): {fetch.stderr.strip()}"
        )
    if not pending and _ahead_of_origin(library_root) == 0:
        return SaveResult(committed=False, pushed=False)

    rebase = _run(["git", "rebase", "origin/main"], library_root)
    if rebase.returncode != 0:
        _run(["git", "rebase", "--abort"], library_root)
        raise RuntimeError(
            "these changes conflict with newer commits on origin/main; nothing was "
            "pushed and the commits stay local. Resolve the conflict in the "
            f"server's clone, then save again. git said: {rebase.stdout.strip()} "
            f"{rebase.stderr.strip()}".strip()
        )

    sha = _run(["git", "rev-parse", "--short", "HEAD"], library_root).stdout.strip()
    push = _run(["git", "push", "origin", "main"], library_root)
    if push.returncode != 0:
        raise RuntimeError(f"git push failed (commit {sha} stays local): {push.stderr.strip()}")
    return SaveResult(
        committed=bool(pending), pushed=True, commit_sha=sha, message=commit_msg,
        pending=pending,
    )
