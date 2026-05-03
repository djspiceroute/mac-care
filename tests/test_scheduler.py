from pathlib import Path
import plistlib
import shutil
import sys

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
    monkeypatch.setattr(scheduler, "_launchctl_load", lambda _: "Job activated via launchctl bootstrap.")
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")

    result = scheduler.install_schedule(config, interval_hours=24, dry_run=False)

    assert result.plist_path == plist_path
    assert plist_path.exists()
    payload = plistlib.loads(plist_path.read_bytes())
    assert payload["ProgramArguments"] == ["/bin/mac-care", "scan", "--notify"]
    assert "activated" in result.message


def test_install_schedule_surfaces_activation_failure(monkeypatch, tmp_path):
    plist_path = tmp_path / "LaunchAgents" / "com.mac-care.periodic.plist"
    monkeypatch.setattr(scheduler, "PLIST_PATH", plist_path)
    monkeypatch.setattr(scheduler, "default_program_arguments", lambda: ["/bin/mac-care", "scan", "--notify"])
    monkeypatch.setattr(scheduler, "_launchctl_load", lambda _: "Job registered but activation failed (permission denied) — it will activate on next login.")
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")

    result = scheduler.install_schedule(config, interval_hours=24, dry_run=False)

    assert plist_path.exists()
    assert "next login" in result.message


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


def test_default_program_arguments_resolves_absolute_path(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/local/bin/mac-care" if cmd == "mac-care" else None)

    args = scheduler.default_program_arguments()

    assert args == ["/usr/local/bin/mac-care", "scan", "--notify"]


def test_default_program_arguments_fallback_to_sys_executable(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    args = scheduler.default_program_arguments()

    assert args == [sys.executable, "-m", "mac_care", "scan", "--notify"]


def test_get_schedule_status_not_installed(monkeypatch, tmp_path):
    plist_path = tmp_path / "nonexistent.plist"
    monkeypatch.setattr(scheduler, "PLIST_PATH", plist_path)

    result = scheduler.get_schedule_status()

    assert "No schedule installed" in result.message


def test_get_schedule_status_installed(monkeypatch, tmp_path):
    plist_path = tmp_path / "installed.plist"
    payload = {
        "ProgramArguments": ["/bin/mac-care", "scan", "--notify"],
        "StartInterval": 86400,
    }
    plist_path.write_bytes(plistlib.dumps(payload))
    monkeypatch.setattr(scheduler, "PLIST_PATH", plist_path)

    result = scheduler.get_schedule_status()

    assert "Schedule installed" in result.message
    assert "Executable: /bin/mac-care" in result.message
    assert "Interval:   24h" in result.message
