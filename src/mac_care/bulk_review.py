"""
bulk_review.py — bulk quarantine and purge for review-risk findings.

Unlike clean.py (which handles auto_safe only), this module operates on
review-risk findings that the user has explicitly decided to action after
inspecting them in the dashboard or report.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from .action_log import append_action
from .actions import ActionResult, _safety_skip, _quarantine_path, _write_metadata
from .config import Config
from .model import Finding, format_bytes


def bulk_quarantine(
    findings: list[Finding],
    config: Config,
    dry_run: bool = True,
) -> list[ActionResult]:
    """Quarantine a list of review-risk findings (reversible).

    Each finding is moved to the quarantine directory with metadata so it
    can be restored via ``mac-care quarantine restore``.
    """
    run_id = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    results: list[ActionResult] = []

    for finding in findings:
        if finding.risk == "protected":
            results.append(ActionResult(
                action="quarantine", category=finding.category, path=finding.path,
                status="skipped", message=f"skipped: protected path {finding.path}",
                size_bytes=finding.size_bytes,
            ))
            continue

        blocked = _safety_skip(finding, config)
        if blocked:
            results.append(blocked)
            continue

        path = Path(finding.path).expanduser()
        if not path.exists():
            results.append(ActionResult(
                action="quarantine", category=finding.category, path=str(path),
                status="skipped", message=f"skipped: path no longer exists {path}",
                size_bytes=finding.size_bytes,
            ))
            continue

        if dry_run:
            results.append(ActionResult(
                action="quarantine", category=finding.category, path=str(path),
                status="would_quarantine",
                message=f"would quarantine {finding.category}: {path}",
                size_bytes=finding.size_bytes,
            ))
            continue

        destination = _quarantine_path(config, finding, run_id)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            shutil.move(str(path), str(destination))
        except (PermissionError, OSError, shutil.Error) as e:
            results.append(ActionResult(
                action="quarantine", category=finding.category, path=str(path),
                status="skipped", message=f"skipped: permission denied — {e}",
                size_bytes=finding.size_bytes,
            ))
            continue
        _write_metadata(destination.parent, destination, finding)
        results.append(ActionResult(
            action="quarantine", category=finding.category, path=str(path),
            status="quarantined",
            message=f"quarantined {finding.category}: {path} -> {destination}",
            destination=str(destination),
            size_bytes=finding.size_bytes,
        ))

    _log_bulk(config, "bulk_quarantine", findings, results, dry_run)
    return results


def bulk_purge(
    findings: list[Finding],
    config: Config,
    dry_run: bool = True,
) -> list[ActionResult]:
    """Permanently delete a list of review-risk findings. Cannot be undone.

    Unlike quarantine, purge does not move files to quarantine first — it
    deletes them directly. Only use after careful review.
    """
    results: list[ActionResult] = []

    for finding in findings:
        if finding.risk == "protected":
            results.append(ActionResult(
                action="purge", category=finding.category, path=finding.path,
                status="skipped", message=f"skipped: protected path {finding.path}",
                size_bytes=finding.size_bytes,
            ))
            continue

        blocked = _safety_skip(finding, config)
        if blocked:
            results.append(blocked)
            continue

        path = Path(finding.path).expanduser()
        if not path.exists():
            results.append(ActionResult(
                action="purge", category=finding.category, path=str(path),
                status="skipped", message=f"skipped: path no longer exists {path}",
                size_bytes=finding.size_bytes,
            ))
            continue

        if dry_run:
            results.append(ActionResult(
                action="purge", category=finding.category, path=str(path),
                status="would_purge",
                message=f"would purge {finding.category}: {path}",
                size_bytes=finding.size_bytes,
            ))
            continue

        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as e:
            results.append(ActionResult(
                action="purge", category=finding.category, path=str(path),
                status="failed", message=f"failed to purge {path}: {e}",
                size_bytes=finding.size_bytes,
            ))
            continue

        results.append(ActionResult(
            action="purge", category=finding.category, path=str(path),
            status="purged", message=f"purged {finding.category}: {path}",
            size_bytes=finding.size_bytes,
        ))

    _log_bulk(config, "bulk_purge", findings, results, dry_run)
    return results


def render_bulk_summary(results: list[ActionResult], action: str) -> str:
    done = [r for r in results if r.status in {"quarantined", "purged"}]
    would = [r for r in results if r.status.startswith("would_")]
    missing = [r for r in results if r.status == "skipped" and "no longer exists" in r.message]
    denied = [r for r in results if r.status == "skipped" and "permission denied" in r.message]
    other_skipped = [r for r in results if r.status == "skipped"
                     and "no longer exists" not in r.message and "permission denied" not in r.message]
    total_bytes = sum(r.size_bytes for r in done or would)

    if would:
        lines = [f"Dry run — {len(would)} item(s) would be {action}d ({format_bytes(total_bytes)}):"]
        for r in would[:10]:
            lines.append(f"  {r.path}")
        if len(would) > 10:
            lines.append(f"  … and {len(would) - 10} more")
        return "\n".join(lines)

    lines = [f"{action.capitalize()}d {len(done)} item(s) ({format_bytes(total_bytes)})."]
    if missing:
        lines.append(f"Already gone: {len(missing)} item(s) no longer existed on disk.")
    if denied:
        lines.append(
            f"Permission denied: {len(denied)} item(s) in /Library/ require sudo. "
            f"Re-run with: sudo mac-care review bulk --category ... --execute"
        )
    if other_skipped:
        lines.append(f"Skipped: {len(other_skipped)} item(s) (protected or safety check failed).")
    return "\n".join(lines)


def _log_bulk(
    config: Config,
    action: str,
    findings: list[Finding],
    results: list[ActionResult],
    dry_run: bool,
) -> None:
    done = [r for r in results if r.status in {"quarantined", "purged"}]
    skipped = [r for r in results if r.status == "skipped"]
    total_bytes = sum(r.size_bytes for r in done)
    items = [
        {"path": r.path, "status": r.status, "destination": r.destination}
        for r in results
    ]
    append_action(config, {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "category": findings[0].category if findings else "unknown",
        "count": len(done),
        "skipped": len(skipped),
        "total_bytes": total_bytes,
        "dry_run": dry_run,
        "items": items,
    })
