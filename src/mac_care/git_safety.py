"""
git_safety.py — detect dirty or active git repos under a path.

Used by scan.py and clean.py to protect live developer work before
any cleanup action touches workspace directories.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def find_git_repos(root: Path, max_depth: int = 4) -> list[Path]:
    """Return paths of git repo roots found under *root* up to *max_depth*."""
    repos: list[Path] = []
    if not root.exists():
        return repos

    def _walk(path: Path, depth: int) -> None:
        if depth > max_depth:
            return
        git_dir = path / ".git"
        if git_dir.exists():
            repos.append(path)
            return  # don't recurse into nested repos
        try:
            for child in path.iterdir():
                if child.is_dir() and not child.is_symlink():
                    _walk(child, depth + 1)
        except PermissionError:
            pass

    _walk(root, 0)
    return repos


def is_dirty(repo_path: Path) -> bool:
    """Return True if the repo has any uncommitted changes (staged, unstaged, or untracked)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # If we can't check, treat as dirty to be safe.
        return True


def has_active_worktrees(repo_path: Path) -> bool:
    """Return True if the repo has more than one worktree (i.e. active worktree checkouts)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Each worktree entry starts with "worktree <path>"
        count = sum(1 for line in result.stdout.splitlines() if line.startswith("worktree "))
        return count > 1
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return True  # Treat as active if we can't check.


def unsafe_repos(root: Path) -> list[Path]:
    """Return list of repo paths under *root* that are dirty or have active worktrees."""
    return [
        repo
        for repo in find_git_repos(root)
        if is_dirty(repo) or has_active_worktrees(repo)
    ]
