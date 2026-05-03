from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
from pathlib import Path
from typing import Any

from .model import format_bytes
from .summary import RISK_ORDER


@dataclass(frozen=True)
class ReportHistoryEntry:
    generated_at: str
    json_path: Path
    markdown_path: Path | None
    html_path: Path | None
    risk_sizes: dict[str, int]
    risk_counts: dict[str, int]
    tool_warning_count: int


def load_history(reports_dir: Path) -> list[ReportHistoryEntry]:
    entries: list[ReportHistoryEntry] = []
    for json_path in sorted(reports_dir.glob("mac-care-*.json"), reverse=True):
        entry = _load_history_entry(json_path)
        if entry:
            entries.append(entry)
    return entries


def render_history_index(reports_dir: Path) -> str:
    entries = load_history(reports_dir)
    rows = "\n".join(_history_row(entry) for entry in entries)
    latest_link = '<a href="latest.html">Open latest dashboard</a>' if (reports_dir / "latest.html").exists() else "No latest dashboard yet."
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mac Care Report History</title>
  <style>
    :root {{
      color-scheme: light dark;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: Canvas;
      color: CanvasText;
    }}
    body {{ margin: 0; padding: 32px; }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 0.92rem; margin-top: 20px; }}
    th, td {{ border-bottom: 1px solid color-mix(in srgb, CanvasText 14%, transparent); padding: 9px 8px; text-align: left; }}
    th {{ color: color-mix(in srgb, CanvasText 70%, transparent); font-weight: 600; }}
    .size {{ text-align: right; white-space: nowrap; }}
  </style>
</head>
<body>
<main>
  <h1>Mac Care Report History</h1>
  <p>{latest_link}</p>
  <table>
    <thead>
      <tr>
        <th>Generated</th>
        <th class="size">Auto-safe</th>
        <th class="size">Review</th>
        <th class="size">Protected</th>
        <th>Tool warnings</th>
        <th>Reports</th>
      </tr>
    </thead>
    <tbody>{rows or '<tr><td colspan="6">No reports found.</td></tr>'}</tbody>
  </table>
</main>
</body>
</html>
"""


def write_history_index(reports_dir: Path) -> Path:
    path = reports_dir / "index.html"
    path.write_text(render_history_index(reports_dir), encoding="utf-8")
    return path


def _load_history_entry(json_path: Path) -> ReportHistoryEntry | None:
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return None
    risks = summary.get("risks")
    if not isinstance(risks, dict):
        return None

    risk_sizes: dict[str, int] = {}
    risk_counts: dict[str, int] = {}
    for risk in RISK_ORDER:
        risk_payload = risks.get(risk, {})
        if not isinstance(risk_payload, dict):
            risk_payload = {}
        risk_sizes[risk] = int(risk_payload.get("size_bytes", 0) or 0)
        risk_counts[risk] = int(risk_payload.get("count", 0) or 0)

    stem = json_path.stem
    md_path = json_path.with_suffix(".md")
    return ReportHistoryEntry(
        generated_at=str(payload.get("generated_at", stem.removeprefix("mac-care-"))),
        json_path=json_path,
        markdown_path=md_path if md_path.exists() else None,
        html_path=json_path.parent / "latest.html" if (json_path.parent / "latest.html").exists() else None,
        risk_sizes=risk_sizes,
        risk_counts=risk_counts,
        tool_warning_count=int(summary.get("tool_warning_count", 0) or 0),
    )


def _history_row(entry: ReportHistoryEntry) -> str:
    report_links = [
        f'<a href="{escape(entry.json_path.name)}">JSON</a>',
    ]
    if entry.markdown_path:
        report_links.append(f'<a href="{escape(entry.markdown_path.name)}">Markdown</a>')
    if entry.html_path:
        report_links.append(f'<a href="{escape(entry.html_path.name)}">Dashboard</a>')

    return (
        "<tr>"
        f"<td>{escape(entry.generated_at)}</td>"
        f"<td class=\"size\">{_risk_cell(entry, 'auto_safe')}</td>"
        f"<td class=\"size\">{_risk_cell(entry, 'review')}</td>"
        f"<td class=\"size\">{_risk_cell(entry, 'protected')}</td>"
        f"<td>{entry.tool_warning_count}</td>"
        f"<td>{' | '.join(report_links)}</td>"
        "</tr>"
    )


def _risk_cell(entry: ReportHistoryEntry, risk: str) -> str:
    count = entry.risk_counts.get(risk, 0)
    size = format_bytes(entry.risk_sizes.get(risk, 0))
    return f"{escape(size)} ({count})"
