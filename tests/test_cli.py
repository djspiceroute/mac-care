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
    monkeypatch.setattr(cli, "write_reports", lambda *_: ("/tmp/report.md", "/tmp/report.json"))
    monkeypatch.setattr("sys.argv", ["mac-care", "scan"])

    assert cli.main() == 0

    output = capsys.readouterr().out
    assert "Scanned 1 findings" in output
    assert "Markdown report: /tmp/report.md" in output
