from pathlib import Path
import plistlib

from mac_care.config import Config
from mac_care import scheduler


def test_render_plist_runs_scan_only(tmp_path):
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")

    plist = scheduler.render_plist(config, interval_hours=6, program_arguments=["/bin/mac-care", "scan", "--notify"])
    payload = plistlib.loads(plist.encode("utf-8"))

    assert payload["Label"] == scheduler.LABEL
    assert payload["ProgramArguments"] == ["/bin/mac-care", "scan", "--notify"]
    assert payload["StartInterval"] == 21600
    assert "clean" not in payload["ProgramArguments"]


def test_install_schedule_dry_run_does_not_write(monkeypatch, tmp_path):
    plist_path = tmp_path / "com.mac-care.periodic.plist"
    monkeypatch.setattr(scheduler, "PLIST_PATH", plist_path)
    monkeypatch.setattr(scheduler, "default_program_arguments", lambda: ["/bin/mac-care", "scan", "--notify"])
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")

    result = scheduler.install_schedule(config, interval_hours=12, dry_run=True)

    assert result.plist_path == plist_path
    assert "StartInterval" in result.message
    assert not plist_path.exists()


def test_install_schedule_writes_plist(monkeypatch, tmp_path):
    plist_path = tmp_path / "LaunchAgents" / "com.mac-care.periodic.plist"
    monkeypatch.setattr(scheduler, "PLIST_PATH", plist_path)
    monkeypatch.setattr(scheduler, "default_program_arguments", lambda: ["/bin/mac-care", "scan", "--notify"])
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")

    result = scheduler.install_schedule(config, interval_hours=24, dry_run=False)

    assert result.plist_path == plist_path
    assert plist_path.exists()
    payload = plistlib.loads(plist_path.read_bytes())
    assert payload["ProgramArguments"] == ["/bin/mac-care", "scan", "--notify"]


def test_uninstall_schedule_dry_run_does_not_remove(monkeypatch, tmp_path):
    plist_path = tmp_path / "com.mac-care.periodic.plist"
    plist_path.write_text("plist", encoding="utf-8")
    monkeypatch.setattr(scheduler, "PLIST_PATH", plist_path)

    result = scheduler.uninstall_schedule(dry_run=True)

    assert "Would unload and remove" in result.message
    assert plist_path.exists()


def test_uninstall_schedule_removes_existing_plist(monkeypatch, tmp_path):
    plist_path = tmp_path / "com.mac-care.periodic.plist"
    plist_path.write_text("plist", encoding="utf-8")
    monkeypatch.setattr(scheduler, "PLIST_PATH", plist_path)
    monkeypatch.setattr(scheduler, "_launchctl_unload", lambda _: None)

    result = scheduler.uninstall_schedule(dry_run=False)

    assert "Removed schedule" in result.message
    assert not plist_path.exists()
