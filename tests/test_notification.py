import subprocess

from mac_care.model import Finding, ToolStatus
from mac_care.notification import notification_text, notify_scan_complete
from mac_care.summary import summarize_scan


def _summary():
    return summarize_scan(
        [
            Finding("logs", "/tmp/logs", 1024, "auto_safe", "old logs"),
            Finding("docker", "/tmp/docker", 2048, "review", "docker waste", "docker"),
            Finding("codex", "/tmp/codex", 0, "protected", "dirty repo"),
        ],
        [ToolStatus("docker", "review", "daemon unavailable")],
    )


def test_notification_text_summarizes_scan():
    text = notification_text(_summary())

    assert "1.0 KB auto-safe" in text
    assert "2.0 KB review" in text
    assert "1 protected" in text
    assert "1 tool warnings" in text


def test_notify_scan_complete_returns_true_on_success(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr("mac_care.notification.subprocess.run", fake_run)

    assert notify_scan_complete(_summary()) is True
    assert calls[0][0][0][0] == "osascript"


def test_notify_scan_complete_degrades_on_failure(monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise OSError("missing osascript")

    monkeypatch.setattr("mac_care.notification.subprocess.run", fake_run)

    assert notify_scan_complete(_summary()) is False
