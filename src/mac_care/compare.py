from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .ids import finding_id as _finding_id
from .model import Finding, Report, ToolStatus, format_bytes


_SECURITY_CATEGORIES = {"login_items", "diagnostic_reports"}


@dataclass
class CategoryDiff:
    category: str
    old_bytes: int
    new_bytes: int
    old_reason: str
    new_reason: str

    @property
    def delta(self) -> int:
        return self.new_bytes - self.old_bytes

    @property
    def is_size_based(self) -> bool:
        return self.old_bytes > 0 or self.new_bytes > 0


@dataclass
class CompareSummary:
    appeared: list[str]       # categories new in report2
    disappeared: list[str]    # categories gone from report2
    changed: list[CategoryDiff]  # categories present in both with changes


@dataclass
class FindingDelta:
    category: str
    path: str
    old_bytes: int
    new_bytes: int

    @property
    def pct_change(self) -> float:
        if self.old_bytes == 0:
            return float("inf")
        return (self.new_bytes - self.old_bytes) / self.old_bytes


@dataclass
class WhatChangedSummary:
    new: list[Finding]
    resolved: list[Finding]
    grown: list[FindingDelta]
    shrunk: list[FindingDelta]
    security_alerts: list[str]


def compare_reports(path1: Path, path2: Path) -> CompareSummary:
    r1 = json.loads(path1.read_text(encoding="utf-8"))
    r2 = json.loads(path2.read_text(encoding="utf-8"))

    # Build category → {size, reason} maps from findings, aggregating by category
    def _index(report: dict) -> dict[str, dict]:
        index: dict[str, dict] = {}
        for f in report.get("findings", []):
            cat = f["category"]
            if cat not in index:
                index[cat] = {"size_bytes": 0, "reason": f.get("reason", "")}
            index[cat]["size_bytes"] += f.get("size_bytes", 0)
            index[cat]["reason"] = f.get("reason", "")
        return index

    idx1 = _index(r1)
    idx2 = _index(r2)

    cats1 = set(idx1)
    cats2 = set(idx2)

    appeared = sorted(cats2 - cats1)
    disappeared = sorted(cats1 - cats2)

    changed: list[CategoryDiff] = []
    for cat in sorted(cats1 & cats2):
        old_bytes = idx1[cat]["size_bytes"]
        new_bytes = idx2[cat]["size_bytes"]
        old_reason = idx1[cat]["reason"]
        new_reason = idx2[cat]["reason"]
        if old_bytes != new_bytes or old_reason != new_reason:
            changed.append(CategoryDiff(cat, old_bytes, new_bytes, old_reason, new_reason))

    # Sort changed: largest absolute delta first
    changed.sort(key=lambda d: abs(d.delta), reverse=True)

    return CompareSummary(appeared=appeared, disappeared=disappeared, changed=changed)


def what_changed(prev: Report, curr: Report) -> WhatChangedSummary:
    prev_by_key: dict[str, Finding] = {_finding_id(f): f for f in prev.findings}
    curr_by_key: dict[str, Finding] = {_finding_id(f): f for f in curr.findings}

    prev_keys = set(prev_by_key)
    curr_keys = set(curr_by_key)

    new_findings = [curr_by_key[k] for k in sorted(curr_keys - prev_keys)]
    resolved_findings = [prev_by_key[k] for k in sorted(prev_keys - curr_keys)]

    grown: list[FindingDelta] = []
    shrunk: list[FindingDelta] = []
    for key in sorted(prev_keys & curr_keys):
        old_f = prev_by_key[key]
        new_f = curr_by_key[key]
        if new_f.size_bytes > old_f.size_bytes:
            if old_f.size_bytes == 0 or (new_f.size_bytes - old_f.size_bytes) / old_f.size_bytes > 0.10:
                grown.append(FindingDelta(old_f.category, old_f.path, old_f.size_bytes, new_f.size_bytes))
        elif new_f.size_bytes < old_f.size_bytes:
            shrunk.append(FindingDelta(old_f.category, old_f.path, old_f.size_bytes, new_f.size_bytes))

    security_alerts = [
        f"New {f.category} detected: {f.reason or f.path}"
        for f in new_findings
        if f.category in _SECURITY_CATEGORIES
    ]

    return WhatChangedSummary(
        new=new_findings,
        resolved=resolved_findings,
        grown=grown,
        shrunk=shrunk,
        security_alerts=security_alerts,
    )


def load_report_from_json(path: Path) -> Report:
    payload = json.loads(path.read_text(encoding="utf-8"))
    findings = [
        Finding(
            category=f["category"],
            path=f["path"],
            size_bytes=f.get("size_bytes", 0),
            risk=f.get("risk", "auto_safe"),
            reason=f.get("reason", ""),
            source=f.get("source", "native"),
        )
        for f in payload.get("findings", [])
    ]
    tools = [
        ToolStatus(name=t["name"], status=t["status"], detail=t["detail"])
        for t in payload.get("tools", [])
    ]
    return Report(findings=findings, tools=tools)


def render_what_changed_cli(summary: WhatChangedSummary) -> str:
    lines = ["What's changed since last scan:"]
    lines.append(f"  New:      {_fmt_findings(summary.new)}")
    lines.append(f"  Resolved: {_fmt_findings(summary.resolved)}")
    lines.append(f"  Grown:    {_fmt_deltas(summary.grown)}")
    lines.append(f"  Shrunk:   {_fmt_deltas(summary.shrunk)}")
    for alert in summary.security_alerts:
        lines.append(f"  [security] {alert}")
    return "\n".join(lines)


def render_compare_markdown(summary: CompareSummary, path1: Path, path2: Path) -> str:
    lines = [
        "# Mac Care — Report Comparison",
        f"",
        f"**Before:** `{path1}`",
        f"**After:**  `{path2}`",
        "",
    ]

    if summary.appeared:
        lines += ["## New categories", ""]
        for cat in summary.appeared:
            lines.append(f"- `{cat}` — appeared")
        lines.append("")

    if summary.disappeared:
        lines += ["## Removed categories", ""]
        for cat in summary.disappeared:
            lines.append(f"- `{cat}` — no longer present")
        lines.append("")

    if summary.changed:
        lines += ["## Changed", "", "| Category | Before | After | Delta | Notes |", "| --- | ---: | ---: | ---: | --- |"]
        for diff in summary.changed:
            if diff.is_size_based:
                sign = "+" if diff.delta >= 0 else ""
                lines.append(
                    f"| `{diff.category}` | {format_bytes(diff.old_bytes)} | {format_bytes(diff.new_bytes)} "
                    f"| {sign}{format_bytes(diff.delta)} | |"
                )
            else:
                # Zero-size finding — diff the reason instead
                notes = _reason_diff(diff.old_reason, diff.new_reason)
                lines.append(f"| `{diff.category}` | — | — | — | {notes} |")
        lines.append("")

    if not summary.appeared and not summary.disappeared and not summary.changed:
        lines.append("No differences found between the two reports.")

    return "\n".join(lines)


def render_compare_json(summary: CompareSummary) -> str:
    return json.dumps({
        "appeared": summary.appeared,
        "disappeared": summary.disappeared,
        "changed": [
            {
                "category": d.category,
                "old_bytes": d.old_bytes,
                "new_bytes": d.new_bytes,
                "delta_bytes": d.delta,
                "old_reason": d.old_reason,
                "new_reason": d.new_reason,
            }
            for d in summary.changed
        ],
    }, indent=2)


def _fmt_findings(items: list[Finding]) -> str:
    if not items:
        return "—"
    by_cat: dict[str, int] = {}
    for f in items:
        by_cat[f.category] = by_cat.get(f.category, 0) + 1
    parts = [f"{cat} ({n})" for cat, n in sorted(by_cat.items())]
    return f"{len(items)} finding(s): {', '.join(parts)}"


def _fmt_deltas(items: list[FindingDelta]) -> str:
    if not items:
        return "—"
    parts = []
    for d in items[:3]:
        if d.old_bytes == 0:
            parts.append(f"{d.category} (new size: {format_bytes(d.new_bytes)})")
        else:
            pct = int(abs(d.pct_change) * 100)
            sign = "+" if d.new_bytes > d.old_bytes else "-"
            parts.append(f"{d.category} {sign}{pct}% ({format_bytes(d.old_bytes)} → {format_bytes(d.new_bytes)})")
    if len(items) > 3:
        parts.append(f"and {len(items) - 3} more")
    return "; ".join(parts)


def _reason_diff(old: str, new: str) -> str:
    if old == new:
        return "unchanged"
    # Surface a brief change note
    return f"reason changed"
