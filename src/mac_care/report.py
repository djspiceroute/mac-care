from __future__ import annotations

from datetime import datetime
import json

from .config import Config
from .model import Finding, ToolStatus, format_bytes
from .summary import RISK_ORDER, summarize_scan


def write_reports(config: Config, findings: list[Finding], tools: list[ToolStatus]) -> tuple[str, str]:
    config.ensure_dirs()
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    json_path = config.reports_dir / f"mac-care-{stamp}.json"
    md_path = config.reports_dir / f"mac-care-{stamp}.md"

    summary = summarize_scan(findings, tools)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": summary.to_dict(),
        "findings": [finding.__dict__ for finding in findings],
        "tools": [tool.__dict__ for tool in tools],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(findings, tools), encoding="utf-8")
    return str(md_path), str(json_path)


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
