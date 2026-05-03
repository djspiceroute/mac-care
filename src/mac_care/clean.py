from __future__ import annotations

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
_WORKSPACE_CATEGORIES = {"codex_workspaces"}

# First execution path only supports item-level or rebuildable directory moves.
# Broad containers like ~/Library/Caches and /tmp stay dry-run-only until scan
# itemizes their contents.
_EXECUTABLE_AUTO_SAFE_CATEGORIES = {"brew_cache", "xcode_derived_data"}


def safe_clean(findings: list[Finding], config: Config | None = None, dry_run: bool = True) -> list[str]:
    actions: list[str] = []
    run_id = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    for finding in findings:
        if finding.risk != "auto_safe":
            continue

        # Re-run git safety gate for workspace-adjacent categories even if
        # scan already marked them auto_safe (belt-and-suspenders guard).
        if finding.category in _WORKSPACE_CATEGORIES:
            dirty = unsafe_repos(Path(finding.path))
            if dirty:
                actions.append(
                    f"skipped {finding.category}: unsafe git repos detected at scan time — "
                    f"{', '.join(str(r) for r in dirty[:2])}"
                )
                continue

        if dry_run:
            actions.append(f"would clean {finding.category}: {finding.path}")
            continue

        if config is None:
            actions.append(
                f"skipped execution for {finding.category}: config is required for quarantine"
            )
            continue

        if finding.category not in _EXECUTABLE_AUTO_SAFE_CATEGORIES:
            actions.append(
                f"skipped execution for {finding.category}: category is not itemized for quarantine yet"
            )
            continue

        actions.append(quarantine_finding(finding, config, run_id=run_id))
    return actions


def quarantine_finding(finding: Finding, config: Config, run_id: str | None = None) -> str:
    run_id = run_id or datetime.now().strftime("%Y-%m-%d-%H%M%S")
    path = Path(finding.path).expanduser()
    if is_protected(path, config):
        return f"skipped execution for {finding.category}: protected path {path}"

    if finding.category in _WORKSPACE_CATEGORIES:
        dirty = unsafe_repos(path)
        if dirty:
            return (
                f"skipped {finding.category}: unsafe git repos detected at execution time — "
                f"{', '.join(str(r) for r in dirty[:2])}"
            )

    if not path.exists():
        return f"skipped execution for {finding.category}: path no longer exists {path}"

    destination = _quarantine_path(config, finding, run_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(destination))
    _write_metadata(destination.parent, destination, finding)
    return f"quarantined {finding.category}: {path} -> {destination}"



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
