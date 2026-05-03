from __future__ import annotations

import json
from pathlib import Path

import pytest

from mac_care.compare import (
    compare_reports,
    load_report_from_json,
    render_compare_json,
    render_compare_markdown,
    render_what_changed_cli,
    what_changed,
)
from mac_care.model import Finding, Report, ToolStatus


def _write_report(path: Path, findings: list[dict]) -> Path:
    path.write_text(json.dumps({"findings": findings}), encoding="utf-8")
    return path


def test_appeared_category(tmp_path):
    r1 = _write_report(tmp_path / "r1.json", [
        {"category": "brew_cache", "size_bytes": 100, "reason": "brew cache"},
    ])
    r2 = _write_report(tmp_path / "r2.json", [
        {"category": "brew_cache", "size_bytes": 100, "reason": "brew cache"},
        {"category": "ios_backups", "size_bytes": 500, "reason": "backups"},
    ])
    summary = compare_reports(r1, r2)
    assert "ios_backups" in summary.appeared
    assert summary.disappeared == []


def test_disappeared_category(tmp_path):
    r1 = _write_report(tmp_path / "r1.json", [
        {"category": "brew_cache", "size_bytes": 100, "reason": "brew cache"},
        {"category": "trash", "size_bytes": 200, "reason": "trash"},
    ])
    r2 = _write_report(tmp_path / "r2.json", [
        {"category": "brew_cache", "size_bytes": 100, "reason": "brew cache"},
    ])
    summary = compare_reports(r1, r2)
    assert "trash" in summary.disappeared
    assert summary.appeared == []


def test_grew_category(tmp_path):
    r1 = _write_report(tmp_path / "r1.json", [
        {"category": "brew_cache", "size_bytes": 100, "reason": "brew cache"},
    ])
    r2 = _write_report(tmp_path / "r2.json", [
        {"category": "brew_cache", "size_bytes": 900, "reason": "brew cache"},
    ])
    summary = compare_reports(r1, r2)
    assert len(summary.changed) == 1
    assert summary.changed[0].delta == 800


def test_shrank_category(tmp_path):
    r1 = _write_report(tmp_path / "r1.json", [
        {"category": "user_caches", "size_bytes": 1000, "reason": "caches"},
    ])
    r2 = _write_report(tmp_path / "r2.json", [
        {"category": "user_caches", "size_bytes": 200, "reason": "caches"},
    ])
    summary = compare_reports(r1, r2)
    assert summary.changed[0].delta == -800


def test_no_diff_when_identical(tmp_path):
    findings = [{"category": "brew_cache", "size_bytes": 100, "reason": "brew cache"}]
    r1 = _write_report(tmp_path / "r1.json", findings)
    r2 = _write_report(tmp_path / "r2.json", findings)
    summary = compare_reports(r1, r2)
    assert not summary.appeared
    assert not summary.disappeared
    assert not summary.changed


def test_zero_size_finding_diffs_reason(tmp_path):
    r1 = _write_report(tmp_path / "r1.json", [
        {"category": "login_items", "size_bytes": 0, "reason": "2 login item(s): Dropbox, Alfred"},
    ])
    r2 = _write_report(tmp_path / "r2.json", [
        {"category": "login_items", "size_bytes": 0, "reason": "3 login item(s): Dropbox, Alfred, Zoom"},
    ])
    summary = compare_reports(r1, r2)
    assert len(summary.changed) == 1
    assert not summary.changed[0].is_size_based


def test_render_markdown_output(tmp_path):
    r1 = _write_report(tmp_path / "r1.json", [
        {"category": "brew_cache", "size_bytes": 100, "reason": "brew cache"},
    ])
    r2 = _write_report(tmp_path / "r2.json", [
        {"category": "brew_cache", "size_bytes": 900, "reason": "brew cache"},
        {"category": "ios_backups", "size_bytes": 500, "reason": "backups"},
    ])
    summary = compare_reports(r1, r2)
    output = render_compare_markdown(summary, r1, r2)
    assert "ios_backups" in output
    assert "brew_cache" in output
    assert "800" in output or "+" in output


def test_render_json_output(tmp_path):
    r1 = _write_report(tmp_path / "r1.json", [
        {"category": "trash", "size_bytes": 500, "reason": "trash"},
    ])
    r2 = _write_report(tmp_path / "r2.json", [])
    summary = compare_reports(r1, r2)
    output = json.loads(render_compare_json(summary))
    assert "trash" in output["disappeared"]
    assert isinstance(output["appeared"], list)
    assert isinstance(output["changed"], list)


# ── what_changed tests (Report-object API) ────────────────────────────────────

def _make_finding(category: str, path: str, size_bytes: int = 0, risk: str = "auto_safe", reason: str = "") -> Finding:
    return Finding(category=category, path=path, size_bytes=size_bytes, risk=risk, reason=reason)


def _make_report(*findings: Finding) -> Report:
    return Report(findings=list(findings), tools=[])


def test_what_changed_new_finding():
    prev = _make_report(_make_finding("brew_cache", "/path/a", 100))
    curr = _make_report(
        _make_finding("brew_cache", "/path/a", 100),
        _make_finding("ios_backups", "/path/b", 500),
    )
    delta = what_changed(prev, curr)
    assert len(delta.new) == 1
    assert delta.new[0].category == "ios_backups"
    assert delta.resolved == []


def test_what_changed_resolved_finding():
    prev = _make_report(
        _make_finding("brew_cache", "/path/a", 100),
        _make_finding("trash", "/path/t", 200),
    )
    curr = _make_report(_make_finding("brew_cache", "/path/a", 100))
    delta = what_changed(prev, curr)
    assert len(delta.resolved) == 1
    assert delta.resolved[0].category == "trash"
    assert delta.new == []


def test_what_changed_grown_above_threshold():
    prev = _make_report(_make_finding("brew_cache", "/path/a", 1000))
    curr = _make_report(_make_finding("brew_cache", "/path/a", 1200))
    delta = what_changed(prev, curr)
    assert len(delta.grown) == 1
    assert delta.grown[0].pct_change == pytest.approx(0.20)
    assert delta.shrunk == []


def test_what_changed_grown_below_threshold_not_reported():
    prev = _make_report(_make_finding("brew_cache", "/path/a", 1000))
    curr = _make_report(_make_finding("brew_cache", "/path/a", 1050))
    delta = what_changed(prev, curr)
    assert delta.grown == []


def test_what_changed_shrunk():
    prev = _make_report(_make_finding("user_caches", "/path/c", 1000))
    curr = _make_report(_make_finding("user_caches", "/path/c", 200))
    delta = what_changed(prev, curr)
    assert len(delta.shrunk) == 1
    assert delta.shrunk[0].old_bytes == 1000
    assert delta.shrunk[0].new_bytes == 200
    assert delta.grown == []


def test_what_changed_security_alert_for_new_login_item():
    prev = _make_report()
    curr = _make_report(_make_finding("login_items", "/path/zoom", 0, reason="1 login item(s): Zoom"))
    delta = what_changed(prev, curr)
    assert len(delta.security_alerts) == 1
    assert "login_items" in delta.security_alerts[0]


def test_what_changed_security_alert_for_diagnostic_reports():
    prev = _make_report()
    curr = _make_report(_make_finding("diagnostic_reports", "/path/diag", 500))
    delta = what_changed(prev, curr)
    assert len(delta.security_alerts) == 1
    assert "diagnostic_reports" in delta.security_alerts[0]


def test_what_changed_no_previous_report_degrades_gracefully():
    curr = _make_report(_make_finding("brew_cache", "/path/a", 100))
    empty_prev = _make_report()
    delta = what_changed(empty_prev, curr)
    assert len(delta.new) == 1
    assert delta.resolved == []
    assert delta.grown == []
    assert delta.shrunk == []


def test_what_changed_identical_reports_produce_empty_delta():
    f = _make_finding("brew_cache", "/path/a", 100)
    prev = _make_report(f)
    curr = _make_report(f)
    delta = what_changed(prev, curr)
    assert delta.new == []
    assert delta.resolved == []
    assert delta.grown == []
    assert delta.shrunk == []
    assert delta.security_alerts == []


def test_render_what_changed_cli_includes_all_sections():
    prev = _make_report(
        _make_finding("brew_cache", "/path/a", 1000),
        _make_finding("trash", "/path/t", 500),
    )
    curr = _make_report(
        _make_finding("brew_cache", "/path/a", 1200),
        _make_finding("ios_backups", "/path/b", 300),
        _make_finding("login_items", "/path/zoom", 0, reason="1 login item(s): Zoom"),
    )
    delta = what_changed(prev, curr)
    output = render_what_changed_cli(delta)
    assert "What's changed" in output
    assert "New" in output
    assert "Resolved" in output
    assert "Grown" in output
    assert "Shrunk" in output
    assert "[security]" in output
    assert "login_items" in output


def test_load_report_from_json_round_trips(tmp_path):
    findings = [
        {"category": "brew_cache", "path": "/path/a", "size_bytes": 100, "risk": "auto_safe", "reason": "cache", "source": "native"},
    ]
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"findings": findings, "tools": []}), encoding="utf-8")
    report = load_report_from_json(path)
    assert len(report.findings) == 1
    assert report.findings[0].category == "brew_cache"
    assert report.findings[0].size_bytes == 100
