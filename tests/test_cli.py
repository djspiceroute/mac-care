from __future__ import annotations

import json

from mac_care import cli
from mac_care.model import Finding, ToolStatus


def test_scan_stdout_json(monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "load", lambda _: object())
    monkeypatch.setattr(cli, "scan", lambda _: [Finding("logs", "/tmp/logs", 100, "auto_safe", "old logs")])
    monkeypatch.setattr(cli, "check_tools", lambda: [ToolStatus("git", "ok", "/usr/bin/git")])
    monkeypatch.setattr("sys.argv", ["mac-care", "scan", "--stdout", "--format", "json"])

    assert cli.main() == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["risks"]["auto_safe"]["count"] == 1
    assert payload["findings"][0]["category"] == "logs"


def test_scan_stdout_markdown(monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "load", lambda _: object())
    monkeypatch.setattr(cli, "scan", lambda _: [Finding("logs", "/tmp/logs", 100, "auto_safe", "old logs")])
    monkeypatch.setattr(cli, "check_tools", lambda: [ToolStatus("git", "ok", "/usr/bin/git")])
    monkeypatch.setattr("sys.argv", ["mac-care", "scan", "--stdout", "--format", "markdown"])

    assert cli.main() == 0

    output = capsys.readouterr().out
    assert "# Mac Care Report" in output
    assert "| auto_safe | 1 | 100.0 B |" in output


def test_scan_default_writes_reports(monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "load", lambda _: object())
    monkeypatch.setattr(cli, "scan", lambda _: [Finding("logs", "/tmp/logs", 100, "auto_safe", "old logs")])
    monkeypatch.setattr(cli, "check_tools", lambda: [ToolStatus("git", "ok", "/usr/bin/git")])
    monkeypatch.setattr(cli, "write_reports", lambda *_: ("/tmp/report.md", "/tmp/report.json", "/tmp/latest.html"))
    monkeypatch.setattr("sys.argv", ["mac-care", "scan"])

    assert cli.main() == 0

    output = capsys.readouterr().out
    assert "Scanned 1 findings" in output
    assert "Markdown report: /tmp/report.md" in output
    assert "HTML report: /tmp/latest.html" in output


def test_schedule_install_dry_run(monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "load", lambda _: object())
    monkeypatch.setattr(cli, "install_schedule", lambda *_args, **_kwargs: type("Result", (), {"message": "<plist/>"})())
    monkeypatch.setattr("sys.argv", ["mac-care", "schedule", "install", "--dry-run"])

    assert cli.main() == 0

    assert "<plist/>" in capsys.readouterr().out


def test_schedule_uninstall_dry_run(monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "load", lambda _: object())
    monkeypatch.setattr(
        cli,
        "uninstall_schedule",
        lambda **_kwargs: type("Result", (), {"message": "Would unload and remove plist"})(),
    )
    monkeypatch.setattr("sys.argv", ["mac-care", "schedule", "uninstall", "--dry-run"])

    assert cli.main() == 0

    assert "Would unload" in capsys.readouterr().out
