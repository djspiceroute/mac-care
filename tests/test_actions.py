from mac_care.actions import preview_clean_action, preview_quarantine_action, purge_action, quarantine_action
from mac_care.config import Config
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
