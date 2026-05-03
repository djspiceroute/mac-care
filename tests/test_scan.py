import time
from pathlib import Path

import pytest

from mac_care.config import Config
from mac_care.scan import (
    _LARGE_FILE_THRESHOLD_BYTES,
    _large_files,
    _under_any_repo,
)


# -- _under_any_repo --


def test_under_any_repo_exact_match():
    repo = Path("/tmp/repo")
    assert _under_any_repo(repo, {str(repo)})


def test_under_any_repo_child_path():
    repo = Path("/tmp/repo")
    child = Path("/tmp/repo/sub/file.txt")
    assert _under_any_repo(child, {str(repo)})


def test_under_any_repo_unrelated_path():
    repo = Path("/tmp/repo")
    other = Path("/tmp/other/file.txt")
    assert not _under_any_repo(other, {str(repo)})


def test_under_any_repo_empty_set():
    assert not _under_any_repo(Path("/tmp/file.txt"), set())


# -- _large_files --


def test_large_files_finds_file_above_threshold(tmp_path, monkeypatch):
    # Mock HOME to tmp_path so we can write into ~/Downloads
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    large = downloads / "big.iso"
    large.write_bytes(b"x" * (_LARGE_FILE_THRESHOLD_BYTES + 10))

    config = Config(protected_paths=[])
    findings = _large_files(config)
    assert len(findings) == 1
    assert findings[0].category == "large_files"
    assert findings[0].risk == "review"
    assert str(large) in findings[0].path


def test_large_files_ignores_file_below_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    small = downloads / "small.txt"
    small.write_bytes(b"under threshold")

    config = Config()
    findings = _large_files(config)
    assert findings == []


def test_large_files_skips_symlinks(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    real = downloads / "real.iso"
    real.write_bytes(b"x" * (_LARGE_FILE_THRESHOLD_BYTES + 10))
    link = downloads / "link.iso"
    link.symlink_to(real)

    config = Config()
    findings = _large_files(config)
    # Only the real file should appear
    assert len(findings) == 1
    assert "real.iso" in findings[0].path


def test_large_files_ignores_protected_path(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    protected = downloads / "protected.iso"
    protected.write_bytes(b"x" * (_LARGE_FILE_THRESHOLD_BYTES + 10))

    config = Config(protected_paths=[protected])
    findings = _large_files(config)
    assert findings == []


def test_large_files_skips_dirty_repo(tmp_path, monkeypatch):
    """A file inside a dirty git repo should not be surfaced."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    repo = downloads / "project"
    repo.mkdir()
    # Init a git repo
    import subprocess
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    # Make a change so it's dirty
    (repo / "file.txt").write_text("dirty")
    large = repo / "big.iso"
    large.write_bytes(b"x" * (_LARGE_FILE_THRESHOLD_BYTES + 10))

    config = Config()
    findings = _large_files(config)
    assert findings == []


def test_large_files_includes_nested_in_toplevel(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    nested = downloads / "deep" / "nested" / "dir"
    nested.mkdir(parents=True)
    large = nested / "archive.tar"
    large.write_bytes(b"x" * (_LARGE_FILE_THRESHOLD_BYTES + 10))

    config = Config()
    findings = _large_files(config)
    assert len(findings) == 1
    assert "archive.tar" in findings[0].path


def test_large_files_includes_age_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    large = downloads / "old.iso"
    large.write_bytes(b"x" * (_LARGE_FILE_THRESHOLD_BYTES + 10))

    # Set mtime to 5 days ago
    old_time = time.time() - (5 * 86400)
    large.touch()
    import os
    os.utime(large, (old_time, old_time))

    config = Config()
    findings = _large_files(config)
    assert len(findings) == 1
    assert "age 5 days" in findings[0].reason
    assert "GB" in findings[0].reason


def test_large_files_multiple_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for sub in ["Downloads", "Desktop", "Documents"]:
        d = tmp_path / sub
        d.mkdir()
        (d / "big.iso").write_bytes(b"x" * (_LARGE_FILE_THRESHOLD_BYTES + 10))

    config = Config()
    findings = _large_files(config)
    assert len(findings) == 3
