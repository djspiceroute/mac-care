from __future__ import annotations

from datetime import datetime
from html import escape
import json

from .config import Config
from .model import Finding, ToolStatus, format_bytes
from .summary import RISK_ORDER, summarize_scan


def report_payload(findings: list[Finding], tools: list[ToolStatus]) -> dict:
    summary = summarize_scan(findings, tools)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": summary.to_dict(),
        "findings": [finding.__dict__ for finding in findings],
        "tools": [tool.__dict__ for tool in tools],
    }


def render_json(findings: list[Finding], tools: list[ToolStatus]) -> str:
    return json.dumps(report_payload(findings, tools), indent=2)


def write_reports(config: Config, findings: list[Finding], tools: list[ToolStatus]) -> tuple[str, str, str]:
    config.ensure_dirs()
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    json_path = config.reports_dir / f"mac-care-{stamp}.json"
    md_path = config.reports_dir / f"mac-care-{stamp}.md"
    html_path = config.reports_dir / "latest.html"

    json_path.write_text(render_json(findings, tools), encoding="utf-8")
    md_path.write_text(render_markdown(findings, tools), encoding="utf-8")
    html_path.write_text(render_html(findings, tools), encoding="utf-8")
    return str(md_path), str(json_path), str(html_path)


def render_markdown(findings: list[Finding], tools: list[ToolStatus]) -> str:
    summary = summarize_scan(findings, tools)
    lines = ["# Mac Care Report", "", "## Summary", ""]
    lines.extend(["| Risk | Count | Size |", "| --- | ---: | ---: |"])
    for risk in RISK_ORDER:
        risk_summary = summary.risks[risk]
        lines.append(f"| {risk} | {risk_summary.count} | {format_bytes(risk_summary.size_bytes)} |")
    lines.extend(["", f"Tool warnings: {summary.tool_warning_count}", ""])

    if summary.top_findings:
        lines.extend(["### Top Findings", "", "| Category | Risk | Size | Source |", "| --- | --- | ---: | --- |"])
        for item in summary.top_findings:
            lines.append(f"| {item.category} | {item.risk} | {format_bytes(item.size_bytes)} | {item.source} |")
        lines.append("")

    for risk in RISK_ORDER:
        group = [item for item in findings if item.risk == risk]
        total = sum(item.size_bytes for item in group)
        lines.extend([f"## {risk}", "", f"Total: {format_bytes(total)}", ""])
        if not group:
            lines.extend(["No items.", ""])
            continue
        lines.extend(["| Category | Size | Path | Reason |", "| --- | ---: | --- | --- |"])
        for item in sorted(group, key=lambda finding: finding.size_bytes, reverse=True):
            lines.append(f"| {item.category} | {format_bytes(item.size_bytes)} | `{item.path}` | {item.reason} |")
        lines.append("")

    lines.extend(["## Doctor", "", "| Tool | Status | Detail |", "| --- | --- | --- |"])
    for tool in tools:
        lines.append(f"| {tool.name} | {tool.status} | `{tool.detail}` |")
    lines.append("")
    return "\n".join(lines)


def render_html(findings: list[Finding], tools: list[ToolStatus]) -> str:
    summary = summarize_scan(findings, tools)
    risk_cards = "\n".join(
        _risk_card(risk, summary.risks[risk].count, summary.risks[risk].size_bytes) for risk in RISK_ORDER
    )
    top_findings = _finding_rows(summary.top_findings, include_risk=True)
    risk_sections = "\n".join(_risk_section(risk, findings) for risk in RISK_ORDER)
    tool_rows = "\n".join(
        "<tr>"
        f"<td>{escape(tool.name)}</td>"
        f"<td><span class=\"status\">{escape(tool.status)}</span></td>"
        f"<td><code>{escape(tool.detail)}</code></td>"
        "</tr>"
        for tool in tools
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mac Care Report</title>
  <style>
    :root {{
      color-scheme: light dark;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: Canvas;
      color: CanvasText;
    }}
    body {{ margin: 0; padding: 32px; }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    section {{ margin-top: 32px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid color-mix(in srgb, CanvasText 18%, transparent); border-radius: 8px; padding: 14px; }}
    .label {{ color: color-mix(in srgb, CanvasText 62%, transparent); font-size: 0.86rem; }}
    .value {{ font-size: 1.5rem; font-weight: 650; margin-top: 4px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 0.92rem; }}
    th, td {{ border-bottom: 1px solid color-mix(in srgb, CanvasText 14%, transparent); padding: 9px 8px; text-align: left; vertical-align: top; }}
    th {{ color: color-mix(in srgb, CanvasText 70%, transparent); font-weight: 600; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; overflow-wrap: anywhere; }}
    .size {{ text-align: right; white-space: nowrap; }}
    .status {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
  </style>
</head>
<body>
<main>
  <h1>Mac Care Report</h1>

  <section>
    <h2>Summary</h2>
    <div class="cards">
      {risk_cards}
      <div class="card"><div class="label">Tool warnings</div><div class="value">{summary.tool_warning_count}</div></div>
    </div>
  </section>

  <section>
    <h2>Top Findings</h2>
    <table>
      <thead><tr><th>Category</th><th>Risk</th><th class="size">Size</th><th>Source</th><th>Path</th></tr></thead>
      <tbody>{top_findings or '<tr><td colspan="5">No findings.</td></tr>'}</tbody>
    </table>
  </section>

  {risk_sections}

  <section>
    <h2>Doctor</h2>
    <table>
      <thead><tr><th>Tool</th><th>Status</th><th>Detail</th></tr></thead>
      <tbody>{tool_rows or '<tr><td colspan="3">No tool statuses.</td></tr>'}</tbody>
    </table>
  </section>
</main>
</body>
</html>
"""


def _risk_card(risk: str, count: int, size_bytes: int) -> str:
    return (
        "<div class=\"card\">"
        f"<div class=\"label\">{escape(risk)}</div>"
        f"<div class=\"value\">{format_bytes(size_bytes)}</div>"
        f"<div class=\"label\">{count} findings</div>"
        "</div>"
    )


def _risk_section(risk: str, findings: list[Finding]) -> str:
    group = [finding for finding in findings if finding.risk == risk]
    rows = _finding_rows(group) or '<tr><td colspan="5">No items.</td></tr>'
    return (
        "<section>"
        f"<h2>{escape(risk)}</h2>"
        "<table>"
        "<thead><tr><th>Category</th><th class=\"size\">Size</th><th>Source</th><th>Path</th><th>Reason</th></tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
        "</section>"
    )


def _finding_rows(findings: list[Finding], include_risk: bool = False) -> str:
    rows: list[str] = []
    for finding in sorted(findings, key=lambda item: item.size_bytes, reverse=True):
        risk_cell = f"<td>{escape(finding.risk)}</td>" if include_risk else ""
        reason_cell = "" if include_risk else f"<td>{escape(finding.reason)}</td>"
        rows.append(
            "<tr>"
            f"<td>{escape(finding.category)}</td>"
            f"{risk_cell}"
            f"<td class=\"size\">{format_bytes(finding.size_bytes)}</td>"
            f"<td>{escape(finding.source)}</td>"
            f"<td><code>{escape(finding.path)}</code></td>"
            f"{reason_cell}"
            "</tr>"
        )
    return "\n".join(rows)
