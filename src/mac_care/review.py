from __future__ import annotations

import json
from pathlib import Path

from .actions import preview_quarantine_action, quarantine_action
from .config import Config
from .ids import finding_id
from .model import Finding


def approve_finding(report_path: Path, finding_id_value: str, config: Config, dry_run: bool = True) -> str:
    finding = _finding_from_report(report_path, finding_id_value)
    if finding is None:
        return f"skipped review approval: finding {finding_id_value} was not found in {report_path}"

    if finding.risk == "protected":
        return f"skipped review approval for {finding_id_value}: protected findings cannot be actioned"
    if finding.risk != "review":
        return f"skipped review approval for {finding_id_value}: finding risk is {finding.risk}, not review"

    if dry_run:
        result = preview_quarantine_action(finding, config)
        if result.status == "would_quarantine":
            return f"would quarantine review finding {finding_id_value}: {finding.path}"
        return result.render()

    return quarantine_action(finding, config).render()


def _finding_from_report(report_path: Path, finding_id_value: str) -> Finding | None:
    try:
        payload = json.loads(report_path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        return None

    for item in findings:
        if not isinstance(item, dict):
            continue
        finding = _finding_from_payload(item)
        if not finding:
            continue
        item_id = str(item.get("id") or finding_id(finding))
        if item_id == finding_id_value:
            return finding
    return None


def _finding_from_payload(payload: dict) -> Finding | None:
    required = ["category", "path", "size_bytes", "risk", "reason"]
    if any(key not in payload for key in required):
        return None
    risk = str(payload["risk"])
    if risk not in {"auto_safe", "review", "protected"}:
        return None
    return Finding(
        category=str(payload["category"]),
        path=str(payload["path"]),
        size_bytes=int(payload.get("size_bytes") or 0),
        risk=risk,  # type: ignore[arg-type]
        reason=str(payload["reason"]),
        source=str(payload.get("source") or "native"),
    )
