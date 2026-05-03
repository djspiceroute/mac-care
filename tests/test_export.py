from __future__ import annotations

import json
import time
import os
from datetime import date
from pathlib import Path

import pytest

from mac_care.export import export_obsidian, latest_report_path


def _write_report(reports_dir: Path, stamp: str = "2026-05-03-120000") -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    p = reports_dir / f"mac-care-{stamp}.json"
    p.write_text(json.dumps({
        "generated_at": f"2026-05-03T12:00:00",
        "summary": {
            "risks": {
                "auto_safe": {"count": 2, "size_bytes": 1024},
                "review": {"count": 1, "size_bytes": 512},
                "protected": {"count": 0, "size_bytes": 0},
            }
        },
        "findings": [
            {"category": "brew_cache", "size_bytes": 1024, "risk": "auto_safe", "reason": "brew cache"},
        ],
    }), encoding="utf-8")
    return p


def test_latest_report_path_returns_most_recent(tmp_path):
    r1 = _write_report(tmp_path, "2026-04-01-120000")
    time.sleep(0.01)
    r2 = _write_report(tmp_path, "2026-05-01-120000")
    assert latest_report_path(tmp_path) == r2


def test_latest_report_path_returns_none_when_empty(tmp_path):
    assert latest_report_path(tmp_path) is None


def test_export_obsidian_creates_daily_note(tmp_path):
    reports_dir = tmp_path / "reports"
    vault = tmp_path / "vault"
    _write_report(reports_dir)

    msg = export_obsidian(reports_dir, vault)

    daily = vault / f"{date.today().isoformat()}.md"
    assert daily.exists()
    content = daily.read_text(encoding="utf-8")
    assert "mac_care_scan" in content
    assert "brew_cache" in content
    assert "appended" in msg.lower() or "Appended" in msg


def test_export_obsidian_deduplicates(tmp_path):
    reports_dir = tmp_path / "reports"
    vault = tmp_path / "vault"
    _write_report(reports_dir)

    export_obsidian(reports_dir, vault)
    msg2 = export_obsidian(reports_dir, vault)

    assert "Skipped" in msg2
    # Daily note should have only one occurrence of the scan block
    daily = vault / f"{date.today().isoformat()}.md"
    content = daily.read_text(encoding="utf-8")
    assert content.count("mac_care_scan") == 1


def test_export_obsidian_no_reports_raises(tmp_path):
    reports_dir = tmp_path / "empty_reports"
    reports_dir.mkdir()
    vault = tmp_path / "vault"

    with pytest.raises(FileNotFoundError, match="No reports found"):
        export_obsidian(reports_dir, vault)
