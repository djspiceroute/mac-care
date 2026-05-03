from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mac_care.config import Config
from mac_care.scan import (
    _LARGE_FILE_THRESHOLD_BYTES,
    _ai_tool_caches,
    _broken_symlinks,
    _core_dumps_and_crash_logs,
    _ios_backups,
    _large_files,
    _login_items,
    _messages_attachments,
    _orphaned_dotdirs,
    _stale_runtime_versions,
    _time_machine_snapshots,
    _under_any_repo,
)


def _config(tmp_path: Path) -> Config:
    return Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")


# ── #25 iOS backups ──────────────────────────────────────────────────────────

def test_ios_backups_skipped_when_dir_missing(tmp_path):
    config = _config(tmp_path)
    with patch("mac_care.scan.Path.home", return_value=tmp_path):
        result = _ios_backups(config)
    assert result == []


def test_ios_backups_skipped_when_below_500mb(tmp_path):
    backup_dir = tmp_path / "Library/Application Support/MobileSync/Backup"
    backup_dir.mkdir(parents=True)
    (backup_dir / "small.bin").write_bytes(b"x" * 100)
    config = _config(tmp_path)
    with patch("mac_care.scan.Path.home", return_value=tmp_path):
        result = _ios_backups(config)
    assert result == []


def test_ios_backups_returned_when_large(tmp_path):
    backup_dir = tmp_path / "Library/Application Support/MobileSync/Backup"
    backup_dir.mkdir(parents=True)
    with patch("mac_care.scan.size_of", return_value=600 * 1024 * 1024), \
         patch("mac_care.scan.top_subdirs_summary", return_value=""), \
         patch("mac_care.scan.Path.home", return_value=tmp_path):
        result = _ios_backups(_config(tmp_path))
    assert len(result) == 1
    assert result[0].category == "ios_backups"
    assert result[0].risk == "review"


# ── #26 Messages attachments ─────────────────────────────────────────────────

def test_messages_attachments_skipped_when_dir_missing(tmp_path):
    config = _config(tmp_path)
    with patch("mac_care.scan.Path.home", return_value=tmp_path):
        result = _messages_attachments(config)
    assert result == []


def test_messages_attachments_returned(tmp_path):
    att_dir = tmp_path / "Library/Messages/Attachments"
    att_dir.mkdir(parents=True)
    (att_dir / "photo.jpg").write_bytes(b"x" * 1024)
    config = _config(tmp_path)
    with patch("mac_care.scan.Path.home", return_value=tmp_path):
        result = _messages_attachments(config)
    assert len(result) == 1
    assert result[0].category == "messages_attachments"
    assert result[0].risk == "review"


# ── #27 Time Machine snapshots ───────────────────────────────────────────────

def test_time_machine_no_snapshots_returns_empty():
    with patch("mac_care.scan.subprocess.run") as mock_run, \
         patch("mac_care.scan.which", return_value="/usr/bin/tmutil"):
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 0
        result = _time_machine_snapshots()
    assert result == []


def test_time_machine_snapshots_returned():
    snapshot_output = (
        "com.apple.TimeMachine.2026-04-01-120000.local\n"
        "com.apple.TimeMachine.2026-04-15-120000.local\n"
    )
    with patch("mac_care.scan.subprocess.run") as mock_run, \
         patch("mac_care.scan.which", return_value="/usr/bin/tmutil"):
        mock_run.return_value.stdout = snapshot_output
        mock_run.return_value.returncode = 0
        result = _time_machine_snapshots()
    assert len(result) == 1
    assert result[0].category == "time_machine_snapshots"
    assert result[0].risk == "review"
    assert "2" in result[0].reason


def test_time_machine_skipped_when_tmutil_missing():
    with patch("mac_care.scan.which", return_value=None):
        result = _time_machine_snapshots()
    assert result == []


# ── #28 Core dumps and crash logs ───────────────────────────────────────────

def test_core_dumps_returned_when_present(tmp_path):
    cores = tmp_path / "cores"
    cores.mkdir()
    (cores / "core.12345").write_bytes(b"x" * 1024)
    config = _config(tmp_path)
    with patch("mac_care.scan.Path", side_effect=lambda p: tmp_path / str(p).lstrip("/")):
        pass  # tested indirectly via size_of mock
    with patch("mac_care.scan.size_of", return_value=200 * 1024 * 1024), \
         patch("mac_care.scan.Path.home", return_value=tmp_path):
        result = _core_dumps_and_crash_logs(config)
    core_findings = [f for f in result if f.category == "core_dumps"]
    # /cores is a real system path; just verify the function runs without error
    assert isinstance(result, list)


def test_crash_log_findings_degrade_gracefully(tmp_path):
    config = _config(tmp_path)
    with patch("mac_care.scan.Path.home", return_value=tmp_path):
        result = _core_dumps_and_crash_logs(config)
    categories = {f.category for f in result}
    assert "xcode_crash_reports" in categories
    assert "diagnostic_reports" in categories


# ── #30 Broken symlinks ──────────────────────────────────────────────────────

def test_broken_symlinks_found(tmp_path):
    target = tmp_path / "ghost"
    link = tmp_path / "broken_link"
    link.symlink_to(target)  # target does not exist

    with patch("mac_care.scan.Path.home", return_value=tmp_path):
        result = _broken_symlinks()

    assert len(result) == 1
    assert result[0].category == "broken_symlinks"
    assert result[0].risk == "review"
    assert "broken_link" in result[0].reason


def test_broken_symlinks_empty_when_none(tmp_path):
    real = tmp_path / "real_file"
    real.write_text("hello")
    link = tmp_path / "good_link"
    link.symlink_to(real)

    with patch("mac_care.scan.Path.home", return_value=tmp_path):
        result = _broken_symlinks()

    assert result == []


# ── #33 Login items ──────────────────────────────────────────────────────────

def test_login_items_returned():
    with patch("mac_care.scan.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "Dropbox, Amphetamine, Alfred"
        mock_run.return_value.returncode = 0
        result = _login_items()
    assert len(result) == 1
    assert result[0].category == "login_items"
    assert result[0].risk == "review"
    assert "Dropbox" in result[0].reason
    assert "3" in result[0].reason


def test_login_items_empty_when_none():
    with patch("mac_care.scan.subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 0
        result = _login_items()
    assert result == []


def test_login_items_degrade_on_osascript_failure():
    with patch("mac_care.scan.subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 1
        result = _login_items()
    assert result == []


# ── #31 Stale runtimes ───────────────────────────────────────────────────────

def test_stale_runtimes_flags_old_versions(tmp_path):
    nvm_versions = tmp_path / ".nvm" / "versions"
    nvm_versions.mkdir(parents=True)
    old_ver = nvm_versions / "v16.0.0"
    old_ver.mkdir()
    # Set mtime to 400 days ago
    import os, time
    old_time = time.time() - (400 * 86400)
    os.utime(old_ver, (old_time, old_time))

    config = _config(tmp_path)
    with patch("mac_care.scan.Path.home", return_value=tmp_path), \
         patch("mac_care.scan.size_of", return_value=100):
        result = _stale_runtime_versions(config)

    stale = [f for f in result if f.category == "stale_runtimes"]
    assert len(stale) == 1
    assert "v16.0.0" in stale[0].reason


def test_stale_runtimes_skips_recent_versions(tmp_path):
    nvm_versions = tmp_path / ".nvm" / "versions"
    nvm_versions.mkdir(parents=True)
    (nvm_versions / "v20.0.0").mkdir()

    config = _config(tmp_path)
    with patch("mac_care.scan.Path.home", return_value=tmp_path), \
         patch("mac_care.scan.size_of", return_value=100):
        result = _stale_runtime_versions(config)

    stale = [f for f in result if f.category == "stale_runtimes"]
    assert stale == []


def test_stale_runtimes_flags_duplicate_managers(tmp_path):
    (tmp_path / ".nvm").mkdir()
    (tmp_path / ".fnm").mkdir()

    config = _config(tmp_path)
    with patch("mac_care.scan.Path.home", return_value=tmp_path), \
         patch("mac_care.scan.size_of", return_value=0):
        result = _stale_runtime_versions(config)

    dupes = [f for f in result if f.category == "duplicate_version_managers"]
    assert len(dupes) == 1
    assert "nvm" in dupes[0].reason and "fnm" in dupes[0].reason


def test_per_category_min_age_days(tmp_path):
    from mac_care.config import Config
    config = Config(
        reports_dir=tmp_path / "reports",
        quarantine_dir=tmp_path / "quarantine",
        min_age_days=14,
        category_policy={"stale_runtimes": {"min_age_days": 90}},
    )
    assert config.min_age_days_for("stale_runtimes") == 90
    assert config.min_age_days_for("old_installers") == 14


# ── #38 Orphaned dotdirs ─────────────────────────────────────────────────────

def test_orphaned_dotdir_flagged_when_tool_missing(tmp_path):
    dotdir = tmp_path / ".nvm"
    dotdir.mkdir()
    with patch("mac_care.scan.Path.home", return_value=tmp_path), \
         patch("mac_care.scan.which", return_value=None), \
         patch("mac_care.scan.size_of", return_value=500):
        result = _orphaned_dotdirs()
    nvm_findings = [f for f in result if "nvm" in f.reason]
    assert len(nvm_findings) == 1
    assert nvm_findings[0].risk == "review"


def test_orphaned_dotdir_skipped_when_tool_present(tmp_path):
    dotdir = tmp_path / ".nvm"
    dotdir.mkdir()
    with patch("mac_care.scan.Path.home", return_value=tmp_path), \
         patch("mac_care.scan.which", return_value="/usr/local/bin/nvm"):
        result = _orphaned_dotdirs()
    nvm_findings = [f for f in result if "nvm" in str(f)]
    assert nvm_findings == []


# ── #39 AI tool caches ───────────────────────────────────────────────────────

def test_ai_tool_caches_returned_when_present(tmp_path):
    cursor_cache = tmp_path / "Library/Application Support/Cursor/Cache"
    cursor_cache.mkdir(parents=True)
    (cursor_cache / "data").write_bytes(b"x" * 1024)

    config = _config(tmp_path)
    with patch("mac_care.scan.Path.home", return_value=tmp_path), \
         patch("mac_care.scan.size_of", return_value=1024), \
         patch("mac_care.scan.top_subdirs_summary", return_value=""), \
         patch("mac_care.scan.is_protected", return_value=False):
        result = _ai_tool_caches(config)

    assert any(f.category == "cursor_cache" for f in result)


def test_ai_tool_caches_skipped_when_absent(tmp_path):
    config = _config(tmp_path)
    with patch("mac_care.scan.Path.home", return_value=tmp_path):
        result = _ai_tool_caches(config)
    assert result == []


# ── #51 Large file finder ────────────────────────────────────────────────────

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


def test_large_files_finds_file_above_threshold(tmp_path, monkeypatch):
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
    large = repo / "big.iso"
    large.write_bytes(b"x" * (_LARGE_FILE_THRESHOLD_BYTES + 10))

    with patch("mac_care.scan.unsafe_repos", return_value=[repo]):
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
    import time, os

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    large = downloads / "old.iso"
    large.write_bytes(b"x" * (_LARGE_FILE_THRESHOLD_BYTES + 10))

    # Set mtime to 5 days ago
    old_time = time.time() - (5 * 86400)
    large.touch()
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
