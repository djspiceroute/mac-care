from pathlib import Path

import pytest

from mac_care.uninstall import (
    UninstallResult,
    app_deletion_hint,
    render_uninstall_report,
    validate_app_bundle,
)


def _make_valid_app_bundle(tmp_path: Path, name: str = "TestApp") -> Path:
    """Helper: create a real-looking .app bundle under tmp_path/Applications."""
    app_dir = tmp_path / "Applications"
    app_dir.mkdir()
    bundle = app_dir / f"{name}.app"
    contents = bundle / "Contents"
    contents.mkdir(parents=True)
    plist = contents / "Info.plist"
    # minimal binary-plist with CFBundleIdentifier
    import plistlib
    plist.write_bytes(plistlib.dumps({"CFBundleIdentifier": f"com.example.{name.lower()}"}))
    return bundle


# -- validate_app_bundle --


def test_validate_app_bundle_valid(tmp_path):
    app = _make_valid_app_bundle(tmp_path)
    assert validate_app_bundle(app, allowed_bases=(tmp_path / "Applications",))


def test_validate_app_bundle_missing_info_plist(tmp_path):
    app_dir = tmp_path / "Applications"
    app_dir.mkdir()
    bundle = app_dir / "NoPlist.app"
    bundle.mkdir()
    (bundle / "Contents").mkdir()
    assert not validate_app_bundle(bundle, allowed_bases=(app_dir,))


def test_validate_app_bundle_is_symlink(tmp_path):
    app_dir = tmp_path / "Applications"
    app_dir.mkdir()
    real_bundle = app_dir / "RealApp.app"
    real_bundle.mkdir()
    (real_bundle / "Contents").mkdir()
    plist = real_bundle / "Contents" / "Info.plist"
    import plistlib
    plist.write_bytes(plistlib.dumps({"CFBundleIdentifier": "com.example.real"}))

    symlink = app_dir / "LinkApp.app"
    symlink.symlink_to(real_bundle)
    assert not validate_app_bundle(symlink, allowed_bases=(app_dir,))


def test_validate_app_bundle_not_in_allowed_bases(tmp_path):
    app = _make_valid_app_bundle(tmp_path)
    # Pass a different allowed base that is NOT the parent of the bundle
    other = tmp_path / "Other"
    other.mkdir()
    assert not validate_app_bundle(app, allowed_bases=(other,))


def test_validate_app_bundle_not_app_suffix(tmp_path):
    app_dir = tmp_path / "Applications"
    app_dir.mkdir()
    bad = app_dir / "NotAnApp"
    bad.mkdir()
    assert not validate_app_bundle(bad, allowed_bases=(app_dir,))


def test_validate_app_bundle_does_not_exist(tmp_path):
    ghost = tmp_path / "Applications" / "Ghost.app"
    assert not validate_app_bundle(ghost, allowed_bases=(tmp_path / "Applications",))


# -- app_deletion_hint --


def test_app_deletion_hint_none_app_path():
    assert app_deletion_hint(None) == ""


def test_app_deletion_hint_unvalidated_path_shows_no_privilege_guidance(tmp_path):
    bad = tmp_path / "usr" / "local" / "Fake.app"
    bad.mkdir(parents=True)
    (bad / "Contents").mkdir()
    import plistlib
    (bad / "Contents" / "Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": "x"}))
    hint = app_deletion_hint(bad)
    assert "Privileged removal guidance is hidden" in hint


def test_app_deletion_hint_valid_writable_provides_trash_hint(tmp_path, monkeypatch):
    app = _make_valid_app_bundle(tmp_path)
    base = tmp_path / "Applications"
    monkeypatch.setattr("mac_care.uninstall.os.access", lambda p, _: True)
    hint = app_deletion_hint(app, allowed_bases=(base,))
    assert "trash" in hint
    assert "sudo" not in hint


def test_app_deletion_hint_valid_non_writable_provides_sudo_hint(tmp_path, monkeypatch):
    app = _make_valid_app_bundle(tmp_path)
    base = tmp_path / "Applications"
    monkeypatch.setattr("mac_care.uninstall.os.access", lambda p, _: False)
    hint = app_deletion_hint(app, allowed_bases=(base,))
    assert "sudo rm -rf" in hint
    assert "Double-check the path" in hint


# -- render_uninstall_report (integration) --


def test_render_uninstall_report_with_validated_app_sudo_hint(tmp_path, monkeypatch):
    app = _make_valid_app_bundle(tmp_path)
    base = tmp_path / "Applications"
    monkeypatch.setattr("mac_care.uninstall.os.access", lambda p, _: False)
    result = UninstallResult(
        app_path=app,
        support_files=[],
        app_hint=app_deletion_hint(app, allowed_bases=(base,)),
    )
    report = render_uninstall_report(result)
    assert "sudo rm -rf" in report
    assert "App bundle validation failed" not in report


def test_render_uninstall_report_with_validated_app_trash_hint(tmp_path, monkeypatch):
    app = _make_valid_app_bundle(tmp_path)
    base = tmp_path / "Applications"
    monkeypatch.setattr("mac_care.uninstall.os.access", lambda p, _: True)
    result = UninstallResult(
        app_path=app,
        support_files=[],
        app_hint=app_deletion_hint(app, allowed_bases=(base,)),
    )
    report = render_uninstall_report(result)
    assert "trash" in report
    assert "sudo" not in report


def test_render_uninstall_report_with_invalidated_app_hides_sudo(tmp_path):
    bad = tmp_path / "usr" / "local" / "Fake.app"
    bad.mkdir(parents=True)
    (bad / "Contents").mkdir()
    import plistlib
    (bad / "Contents" / "Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": "x"}))
    result = UninstallResult(
        app_path=bad,
        support_files=[],
        app_hint=app_deletion_hint(bad),
    )
    report = render_uninstall_report(result)
    assert "Privileged removal guidance is hidden" in report
    assert "sudo rm -rf" not in report
