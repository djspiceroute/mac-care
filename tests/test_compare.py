from __future__ import annotations

import json
from pathlib import Path

import pytest

from mac_care.compare import compare_reports, render_compare_json, render_compare_markdown


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
