import stat
from pathlib import Path

from mac_care.actions import (
    preview_clean_action,
    preview_quarantine_action,
    preview_restore_action,
    purge_action,
    quarantine_action,
    restore_action,
)
from mac_care.config import Config
from mac_care.ids import finding_id
from mac_care.model import Finding


def test_preview_action_returns_structured_result(tmp_path):
    target = tmp_path / "cache-item"
    target.write_text("cache", encoding="utf-8")
    finding = Finding("brew_cache", str(target), 5, "auto_safe", "brew cleanup", "brew")

    result = preview_clean_action(finding)

    assert result.status == "would_clean"
    assert result.render() == f"would clean brew_cache: {target}"
    assert target.exists()


def test_quarantine_action_moves_file_and_records_destination(tmp_path):
    target = tmp_path / "cache-item"
    target.write_text("cache", encoding="utf-8")
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")
    finding = Finding("brew_cache", str(target), 5, "auto_safe", "brew cleanup", "brew")

    result = quarantine_action(finding, config, run_id="run-1")

    assert result.status == "quarantined"
    assert result.destination == str(config.quarantine_dir / "run-1" / "brew_cache" / "cache-item")
    assert result.render() == f"quarantined brew_cache: {target} -> {result.destination}"
    assert not target.exists()


def test_preview_quarantine_action_supports_review_findings(tmp_path):
    target = tmp_path / "orphan"
    target.write_text("data", encoding="utf-8")
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")
    finding = Finding("orphaned_app_files", str(target), 4, "review", "orphan", "pearcleaner")

    result = preview_quarantine_action(finding, config)

    assert result.status == "would_quarantine"
    assert result.render() == f"would quarantine review finding: {target}"
    assert target.exists()


def test_quarantine_action_skips_protected_path(tmp_path):
    protected = tmp_path / "protected"
    protected.mkdir()
    target = protected / "cache-item"
    target.write_text("cache", encoding="utf-8")
    config = Config(
        reports_dir=tmp_path / "reports",
        quarantine_dir=tmp_path / "quarantine",
        protected_paths=[protected],
    )
    finding = Finding("brew_cache", str(target), 5, "auto_safe", "brew cleanup", "brew")

    result = quarantine_action(finding, config)

    assert result.status == "skipped"
    assert result.render() == f"skipped brew_cache: protected path {target}"
    assert target.exists()


def test_quarantine_action_skips_non_itemized_auto_safe_category(tmp_path):
    target = tmp_path / "Caches"
    target.mkdir()
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")
    finding = Finding("user_caches", str(target), 5, "auto_safe", "broad cache directory")

    result = quarantine_action(finding, config)

    assert result.status == "skipped"
    assert result.render() == "skipped execution for user_caches: category is not itemized for quarantine yet"
    assert target.exists()


def test_purge_action_deletes_executable_auto_safe_file(tmp_path):
    target = tmp_path / "cache-item"
    target.write_text("cache", encoding="utf-8")
    finding = Finding("brew_cache", str(target), 5, "auto_safe", "brew cleanup", "brew")

    result = purge_action(finding)

    assert result.status == "purged"
    assert result.render() == f"purged brew_cache: {target}"
    assert not target.exists()


def test_purge_action_skips_non_itemized_auto_safe_category(tmp_path):
    target = tmp_path / "Caches"
    target.mkdir()
    (target / "cache-file").write_text("cache", encoding="utf-8")
    finding = Finding("user_caches", str(target), 5, "auto_safe", "broad cache directory")

    result = purge_action(finding)

    assert result.status == "skipped"
    assert result.render() == "skipped purge for user_caches: category is not itemized for permanent deletion yet"
    assert target.exists()
    assert (target / "cache-file").exists()


def test_preview_restore_action_finds_quarantine_by_finding_id(tmp_path):
    target = tmp_path / "cache-item"
    target.write_text("cache", encoding="utf-8")
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")
    finding = Finding("brew_cache", str(target), 5, "auto_safe", "brew cleanup", "brew")
    quarantine_action(finding, config, run_id="run-1")

    result = preview_restore_action(config, finding_id(finding))

    assert result.status == "would_restore"
    assert result.destination == str(target)
    assert target.exists() is False
    assert (config.quarantine_dir / "run-1" / "brew_cache" / "cache-item").exists()


def test_restore_action_moves_quarantined_item_back_to_original_path(tmp_path):
    target = tmp_path / "cache-item"
    target.write_text("cache", encoding="utf-8")
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")
    finding = Finding("brew_cache", str(target), 5, "auto_safe", "brew cleanup", "brew")
    quarantined = quarantine_action(finding, config, run_id="run-1")

    result = restore_action(config, quarantined.destination or "")

    assert result.status == "restored"
    assert result.destination == str(target)
    assert result.render() == f"restored {quarantined.destination} -> {target}"
    assert target.read_text(encoding="utf-8") == "cache"
    assert not (config.quarantine_dir / "run-1" / "brew_cache" / "cache-item").exists()


def test_restore_action_skips_when_destination_exists(tmp_path):
    target = tmp_path / "cache-item"
    target.write_text("cache", encoding="utf-8")
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")
    finding = Finding("brew_cache", str(target), 5, "auto_safe", "brew cleanup", "brew")
    quarantined = quarantine_action(finding, config, run_id="run-1")
    target.write_text("new file", encoding="utf-8")

    result = restore_action(config, quarantined.destination or "")

    assert result.status == "skipped"
    assert result.render() == f"skipped restore: destination already exists {target}"
    assert target.read_text(encoding="utf-8") == "new file"
    assert (config.quarantine_dir / "run-1" / "brew_cache" / "cache-item").exists()


def test_restore_action_skips_unknown_identifier(tmp_path):
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")

    result = restore_action(config, "missing")

    assert result.status == "skipped"
    assert result.render() == "skipped restore: no quarantine metadata found for missing"


def test_restore_action_skips_when_quarantined_item_missing(tmp_path):
    target = tmp_path / "cache-item"
    target.write_text("cache", encoding="utf-8")
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")
    finding = Finding("brew_cache", str(target), 5, "auto_safe", "brew cleanup", "brew")
    quarantined = quarantine_action(finding, config, run_id="run-1")
    Path(quarantined.destination or "").unlink()

    result = restore_action(config, finding_id(finding))

    assert result.status == "skipped"
    assert result.render() == f"skipped restore: quarantined item no longer exists {quarantined.destination}"

def test_quarantine_dir_created_with_restrictive_permissions(tmp_path):
    import stat
    quarantine = tmp_path / "quarantine"
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=quarantine)
    config.ensure_dirs()
    assert quarantine.exists()
    assert stat.S_IMODE(quarantine.stat().st_mode) == 0o700


def test_quarantine_run_dir_created_with_restrictive_permissions(tmp_path):
    import stat
    target = tmp_path / "cache-item"
    target.write_text("cache", encoding="utf-8")
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")
    finding = Finding("brew_cache", str(target), 5, "auto_safe", "brew cleanup", "brew")
    result = quarantine_action(finding, config, run_id="run-1")

    assert result.status == "quarantined"
    run_dir = config.quarantine_dir / "run-1"
    assert run_dir.exists()
    for directory in run_dir.rglob("*"):
        if directory.is_dir():
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700
