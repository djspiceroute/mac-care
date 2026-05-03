from pathlib import Path

from mac_care.config import Config
from mac_care.safety import is_protected


def test_path_under_protected_is_protected(tmp_path):
    protected_root = tmp_path / "protected"
    protected_root.mkdir()
    target = protected_root / "subdir" / "file.txt"
    config = Config(
        reports_dir=tmp_path / "reports",
        quarantine_dir=tmp_path / "quarantine",
        protected_paths=[protected_root],
    )

    assert is_protected(target, config)


def test_path_outside_protected_is_not_protected(tmp_path):
    protected_root = tmp_path / "protected"
    protected_root.mkdir()
    unrelated = tmp_path / "other" / "file.txt"
    config = Config(
        reports_dir=tmp_path / "reports",
        quarantine_dir=tmp_path / "quarantine",
        protected_paths=[protected_root],
    )

    assert not is_protected(unrelated, config)


def test_path_under_quarantine_dir_is_protected(tmp_path):
    quarantine = tmp_path / "quarantine"
    quarantine.mkdir()
    inside = quarantine / "run-001" / "item"
    config = Config(
        reports_dir=tmp_path / "reports",
        quarantine_dir=quarantine,
        protected_paths=[],
    )

    assert is_protected(inside, config)


def test_protected_path_itself_is_protected(tmp_path):
    protected_root = tmp_path / "protected"
    protected_root.mkdir()
    config = Config(
        reports_dir=tmp_path / "reports",
        quarantine_dir=tmp_path / "quarantine",
        protected_paths=[protected_root],
    )

    assert is_protected(protected_root, config)


def test_no_protected_paths_returns_false(tmp_path):
    config = Config(
        reports_dir=tmp_path / "reports",
        quarantine_dir=tmp_path / "quarantine",
        protected_paths=[],
    )

    assert not is_protected(tmp_path / "anything", config)
