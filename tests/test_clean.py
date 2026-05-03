import json

from mac_care.clean import safe_clean
from mac_care.config import Config
from mac_care.model import Finding


def test_safe_clean_dry_run_does_not_move(tmp_path):
    target = tmp_path / "cache-item"
    target.write_text("cache", encoding="utf-8")
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")

    actions = safe_clean(
        [Finding("brew_cache", str(target), 5, "auto_safe", "brew cleanup", "brew")],
        config=config,
        dry_run=True,
    )

    assert actions == [f"would clean brew_cache: {target}"]
    assert target.exists()
    assert not config.quarantine_dir.exists()


def test_safe_clean_quarantines_executable_auto_safe_finding(tmp_path):
    target = tmp_path / "cache-item"
    target.write_text("cache", encoding="utf-8")
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")

    actions = safe_clean(
        [Finding("brew_cache", str(target), 5, "auto_safe", "brew cleanup", "brew")],
        config=config,
        dry_run=False,
    )

    assert actions[0].startswith("quarantined brew_cache:")
    assert not target.exists()
    moved = list(config.quarantine_dir.glob("*/brew_cache/cache-item"))
    assert len(moved) == 1
    metadata_files = list(config.quarantine_dir.glob("*/brew_cache/cache-item.metadata.json"))
    metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
    assert metadata["original_path"] == str(target)
    assert metadata["quarantine_path"] == str(moved[0])


def test_safe_clean_skips_review_and_protected_findings(tmp_path):
    review = tmp_path / "review"
    protected = tmp_path / "protected"
    review.write_text("review", encoding="utf-8")
    protected.write_text("protected", encoding="utf-8")
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")

    actions = safe_clean(
        [
            Finding("brew_cache", str(review), 1, "review", "needs review", "brew"),
            Finding("brew_cache", str(protected), 1, "protected", "protected", "brew"),
        ],
        config=config,
        dry_run=False,
    )

    assert actions == []
    assert review.exists()
    assert protected.exists()


def test_safe_clean_rechecks_protected_paths(tmp_path):
    protected_root = tmp_path / "protected"
    target = protected_root / "cache-item"
    protected_root.mkdir()
    target.write_text("cache", encoding="utf-8")
    config = Config(
        reports_dir=tmp_path / "reports",
        quarantine_dir=tmp_path / "quarantine",
        protected_paths=[protected_root],
    )

    actions = safe_clean(
        [Finding("brew_cache", str(target), 5, "auto_safe", "brew cleanup", "brew")],
        config=config,
        dry_run=False,
    )

    assert actions == [f"skipped execution for brew_cache: protected path {target}"]
    assert target.exists()


def test_safe_clean_skips_non_itemized_auto_safe_categories(tmp_path):
    target = tmp_path / "Caches"
    target.mkdir()
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")

    actions = safe_clean(
        [Finding("user_caches", str(target), 5, "auto_safe", "broad cache directory")],
        config=config,
        dry_run=False,
    )

    assert actions == ["skipped execution for user_caches: category is not itemized for quarantine yet"]
    assert target.exists()
