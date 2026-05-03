from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import shutil
import uuid

from .config import Config
from .git_safety import unsafe_repos
from .model import Finding
from .safety import is_protected

# Categories whose paths may contain git repos — always re-check before acting.
WORKSPACE_CATEGORIES = {"codex_workspaces"}

# First execution path only supports item-level or rebuildable directory moves.
# Broad containers like ~/Library/Caches and /tmp stay dry-run-only until scan
# itemizes their contents.
EXECUTABLE_AUTO_SAFE_CATEGORIES = {"brew_cache", "xcode_derived_data"}


@dataclass(frozen=True)
class ActionResult:
    action: str
    category: str
    path: str
    status: str
    message: str
    destination: str | None = None
    size_bytes: int = 0

    def render(self) -> str:
        if self.status == "would_clean":
            return f"would clean {self.category}: {self.path}"
        if self.status == "quarantined" and self.destination:
            return f"quarantined {self.category}: {self.path} -> {self.destination}"
        if self.status == "purged":
            return f"purged {self.category}: {self.path}"
        return self.message


def preview_clean_action(finding: Finding, config: Config | None = None) -> ActionResult:
    if finding.risk != "auto_safe":
        return ActionResult(
            action="clean",
            category=finding.category,
            path=finding.path,
            status="skipped",
            message=f"skipped {finding.category}: finding risk is {finding.risk}",
            size_bytes=finding.size_bytes,
        )
    blocked = _safety_skip(finding, config)
    if blocked:
        return blocked
    return ActionResult(
        action="clean",
        category=finding.category,
        path=finding.path,
        status="would_clean",
        message=f"would clean {finding.category}: {finding.path}",
        size_bytes=finding.size_bytes,
    )


def preview_quarantine_action(finding: Finding, config: Config | None = None) -> ActionResult:
    if finding.risk == "protected":
        return ActionResult(
            action="quarantine",
            category=finding.category,
            path=finding.path,
            status="skipped",
            message=f"skipped review approval: protected findings cannot be actioned",
            size_bytes=finding.size_bytes,
        )
    blocked = _safety_skip(finding, config)
    if blocked:
        return blocked
    return ActionResult(
        action="quarantine",
        category=finding.category,
        path=finding.path,
        status="would_quarantine",
        message=f"would quarantine {finding.risk} finding: {finding.path}",
        size_bytes=finding.size_bytes,
    )


def quarantine_action(finding: Finding, config: Config, run_id: str | None = None) -> ActionResult:
    blocked = _safety_skip(finding, config)
    if blocked:
        return blocked

    if finding.category not in EXECUTABLE_AUTO_SAFE_CATEGORIES and finding.risk == "auto_safe":
        return ActionResult(
            action="quarantine",
            category=finding.category,
            path=finding.path,
            status="skipped",
            message=f"skipped execution for {finding.category}: category is not itemized for quarantine yet",
            size_bytes=finding.size_bytes,
        )

    path = Path(finding.path).expanduser()
    if not path.exists():
        return ActionResult(
            action="quarantine",
            category=finding.category,
            path=str(path),
            status="skipped",
            message=f"skipped execution for {finding.category}: path no longer exists {path}",
            size_bytes=finding.size_bytes,
        )

    run_id = run_id or datetime.now().strftime("%Y-%m-%d-%H%M%S")
    destination = _quarantine_path(config, finding, run_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(destination))
    _write_metadata(destination.parent, destination, finding)
    return ActionResult(
        action="quarantine",
        category=finding.category,
        path=str(path),
        status="quarantined",
        message=f"quarantined {finding.category}: {path} -> {destination}",
        destination=str(destination),
        size_bytes=finding.size_bytes,
    )


def purge_action(finding: Finding, config: Config | None = None) -> ActionResult:
    blocked = _safety_skip(finding, config)
    if blocked:
        return blocked

    if finding.category not in EXECUTABLE_AUTO_SAFE_CATEGORIES:
        return ActionResult(
            action="purge",
            category=finding.category,
            path=finding.path,
            status="skipped",
            message=f"skipped purge for {finding.category}: category is not itemized for permanent deletion yet",
            size_bytes=finding.size_bytes,
        )

    path = Path(finding.path).expanduser()
    if not path.exists():
        return ActionResult(
            action="purge",
            category=finding.category,
            path=str(path),
            status="skipped",
            message=f"skipped {finding.category}: path no longer exists {path}",
            size_bytes=finding.size_bytes,
        )
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except OSError as e:
        return ActionResult(
            action="purge",
            category=finding.category,
            path=str(path),
            status="failed",
            message=f"failed to purge {finding.category}: {path} — {e}",
            size_bytes=finding.size_bytes,
        )

    return ActionResult(
        action="purge",
        category=finding.category,
        path=str(path),
        status="purged",
        message=f"purged {finding.category}: {path}",
        size_bytes=finding.size_bytes,
    )


def _safety_skip(finding: Finding, config: Config | None) -> ActionResult | None:
    path = Path(finding.path).expanduser()

    if finding.category in WORKSPACE_CATEGORIES:
        dirty = unsafe_repos(path)
        if dirty:
            return ActionResult(
                action="skip",
                category=finding.category,
                path=str(path),
                status="skipped",
                message=(
                    f"skipped {finding.category}: unsafe git repos detected at execution time — "
                    f"{', '.join(str(r) for r in dirty[:2])}"
                ),
                size_bytes=finding.size_bytes,
            )

    if config and is_protected(path, config):
        return ActionResult(
            action="skip",
            category=finding.category,
            path=str(path),
            status="skipped",
            message=f"skipped {finding.category}: protected path {path}",
            size_bytes=finding.size_bytes,
        )

    return None


def _quarantine_path(config: Config, finding: Finding, run_id: str) -> Path:
    base = config.quarantine_dir.expanduser() / run_id / finding.category
    source = Path(finding.path)
    name = source.name or finding.category
    candidate = base / name
    if not candidate.exists():
        return candidate
    return base / f"{name}-{uuid.uuid4().hex[:8]}"


def _write_metadata(run_dir: Path, destination: Path, finding: Finding) -> None:
    metadata = {
        "original_path": finding.path,
        "quarantine_path": str(destination),
        "category": finding.category,
        "risk": finding.risk,
        "source": finding.source,
        "reason": finding.reason,
        "size_bytes": finding.size_bytes,
        "quarantined_at": datetime.now().isoformat(timespec="seconds"),
    }
    metadata_path = run_dir / f"{destination.name}.metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
