from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mac_care.git_safety import find_git_repos, has_active_worktrees, is_dirty, unsafe_repos


# ---------------------------------------------------------------------------
# find_git_repos
# ---------------------------------------------------------------------------

def test_find_git_repos_empty_dir(tmp_path: Path) -> None:
    assert find_git_repos(tmp_path) == []


def test_find_git_repos_finds_repo(tmp_path: Path) -> None:
    repo = tmp_path / "myproject"
    repo.mkdir()
    (repo / ".git").mkdir()
    result = find_git_repos(tmp_path)
    assert result == [repo]


def test_find_git_repos_does_not_recurse_into_nested(tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    outer.mkdir()
    (outer / ".git").mkdir()
    inner = outer / "inner"
    inner.mkdir()
    (inner / ".git").mkdir()  # nested repo — should not appear separately
    result = find_git_repos(tmp_path)
    assert result == [outer]


def test_find_git_repos_respects_max_depth(tmp_path: Path) -> None:
    deep = tmp_path / "a" / "b" / "c" / "d" / "e"
    deep.mkdir(parents=True)
    (deep / ".git").mkdir()
    # max_depth=2 should not reach depth 5
    result = find_git_repos(tmp_path, max_depth=2)
    assert result == []


def test_find_git_repos_nonexistent_root() -> None:
    assert find_git_repos(Path("/nonexistent/path/xyz")) == []


# ---------------------------------------------------------------------------
# is_dirty
# ---------------------------------------------------------------------------

def test_is_dirty_returns_true_when_output(tmp_path: Path) -> None:
    mock_result = MagicMock()
    mock_result.stdout = " M src/foo.py\n"
    with patch("subprocess.run", return_value=mock_result):
        assert is_dirty(tmp_path) is True


def test_is_dirty_returns_false_when_clean(tmp_path: Path) -> None:
    mock_result = MagicMock()
    mock_result.stdout = ""
    with patch("subprocess.run", return_value=mock_result):
        assert is_dirty(tmp_path) is False


def test_is_dirty_treats_timeout_as_dirty(tmp_path: Path) -> None:
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=10)):
        assert is_dirty(tmp_path) is True


def test_is_dirty_treats_missing_git_as_dirty(tmp_path: Path) -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert is_dirty(tmp_path) is True


# ---------------------------------------------------------------------------
# has_active_worktrees
# ---------------------------------------------------------------------------

def test_has_active_worktrees_single(tmp_path: Path) -> None:
    mock_result = MagicMock()
    mock_result.stdout = "worktree /path/to/repo\nHEAD abc123\nbranch refs/heads/main\n"
    with patch("subprocess.run", return_value=mock_result):
        assert has_active_worktrees(tmp_path) is False


def test_has_active_worktrees_multiple(tmp_path: Path) -> None:
    mock_result = MagicMock()
    mock_result.stdout = (
        "worktree /path/to/repo\nHEAD abc\nbranch refs/heads/main\n\n"
        "worktree /path/to/worktree\nHEAD def\nbranch refs/heads/feature\n"
    )
    with patch("subprocess.run", return_value=mock_result):
        assert has_active_worktrees(tmp_path) is True


def test_has_active_worktrees_timeout_treated_as_active(tmp_path: Path) -> None:
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=10)):
        assert has_active_worktrees(tmp_path) is True


# ---------------------------------------------------------------------------
# unsafe_repos (integration of the above)
# ---------------------------------------------------------------------------

def test_unsafe_repos_empty_when_no_repos(tmp_path: Path) -> None:
    assert unsafe_repos(tmp_path) == []


def test_unsafe_repos_includes_dirty_repo(tmp_path: Path) -> None:
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / ".git").mkdir()

    dirty_result = MagicMock()
    dirty_result.stdout = " M file.py\n"

    clean_worktree = MagicMock()
    clean_worktree.stdout = "worktree /path\nHEAD abc\n"

    with patch("subprocess.run", side_effect=[dirty_result, clean_worktree]):
        result = unsafe_repos(tmp_path)
    assert result == [repo]


def test_unsafe_repos_excludes_clean_repo(tmp_path: Path) -> None:
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / ".git").mkdir()

    clean_status = MagicMock()
    clean_status.stdout = ""

    single_worktree = MagicMock()
    single_worktree.stdout = "worktree /path\nHEAD abc\nbranch refs/heads/main\n"

    with patch("subprocess.run", side_effect=[clean_status, single_worktree]):
        result = unsafe_repos(tmp_path)
    assert result == []
