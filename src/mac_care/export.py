from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .model import format_bytes


def latest_report_path(reports_dir: Path) -> Path | None:
    """Return the most recent JSON report in reports_dir, or None if none exist."""
    candidates = sorted(
        reports_dir.glob("mac-care-*.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def export_obsidian(reports_dir: Path, vault_path: Path) -> str:
    """Append the latest scan summary to today's Obsidian daily note.

    Returns a message describing what happened.
    """
    report_file = latest_report_path(reports_dir)
    if report_file is None:
        raise FileNotFoundError(
            f"No reports found in {reports_dir}. Run 'mac-care scan' first."
        )

    report = json.loads(report_file.read_text(encoding="utf-8"))
    generated_at = report.get("generated_at", "unknown")

    daily_note = vault_path / f"{date.today().isoformat()}.md"
    vault_path.mkdir(parents=True, exist_ok=True)

    # Dedup: skip if this scan timestamp is already in the note
    if daily_note.exists():
        existing = daily_note.read_text(encoding="utf-8")
        if generated_at in existing:
            return f"Skipped — scan from {generated_at} already in {daily_note.name}."

    block = _render_obsidian_block(report, report_file)
    with daily_note.open("a", encoding="utf-8") as f:
        f.write("\n" + block)

    return f"Appended scan from {generated_at} to {daily_note}."


def _render_obsidian_block(report: dict, report_file: Path) -> str:
    generated_at = report.get("generated_at", "unknown")
    summary = report.get("summary", {})
    risks = summary.get("risks", {})

    def _risk_line(risk: str) -> str:
        r = risks.get(risk, {})
        return f"{risk}: {r.get('count', 0)} findings, {format_bytes(r.get('size_bytes', 0))}"

    findings = report.get("findings", [])
    top = sorted(findings, key=lambda f: f.get("size_bytes", 0), reverse=True)[:5]
    top_lines = "\n".join(
        f"  - {f['category']}: {format_bytes(f.get('size_bytes', 0))} ({f.get('risk', '')})"
        for f in top
    )

    return f"""---
mac_care_scan: "{generated_at}"
report_file: "{report_file.name}"
---

## Mac Care — {generated_at}

{_risk_line('auto_safe')}
{_risk_line('review')}
{_risk_line('protected')}

### Top findings
{top_lines or '  (none)'}

"""
