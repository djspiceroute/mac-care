from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .model import format_bytes


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


def _reason_diff(old: str, new: str) -> str:
    if old == new:
        return "unchanged"
    # Surface a brief change note
    return f"reason changed"
