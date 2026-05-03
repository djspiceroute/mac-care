"""
tools/brew.py — Homebrew cleanup findings via `brew cleanup --dry-run`.

Parses brew's own output to determine what it considers safe to remove.
We trust brew's judgment: anything it would clean is tagged auto_safe.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from shutil import which

from ..model import Finding

# Matches: "Would remove: /some/path (42 files, 3.4MB)"
#       or "Would remove: /some/path (3.4MB)"
#       or "Would remove (broken link): /some/path"
#       or "Would remove (empty directory): /some/path"
_REMOVE_RE = re.compile(
    r"^Would remove(?P<qualifier> \([^)]+\))?: (?P<path>[^\s(]+)"
    r"(?:\s+\((?:[\d,]+ files?,\s*)?(?P<size>[0-9.]+\s*[KMGT]?B)\))?",
)

# Maps brew size suffixes → bytes multipliers
_UNIT: dict[str, int] = {
    "B": 1,
    "KB": 1_000,
    "MB": 1_000_000,
    "GB": 1_000_000_000,
    "TB": 1_000_000_000_000,
}


def _parse_size(raw: str | None) -> int:
    """Convert a brew size string like '3.4MB' or '109.2MB' to bytes."""
    if not raw:
        return 0
    raw = raw.strip().replace(",", "")
    for suffix, mult in sorted(_UNIT.items(), key=lambda kv: -len(kv[0])):
        if raw.endswith(suffix):
            try:
                return int(float(raw[: -len(suffix)]) * mult)
            except ValueError:
                return 0
    return 0


def brew_cleanup_findings() -> list[Finding]:
    """Run ``brew cleanup --dry-run`` and return one Finding per removable item.

    Returns an empty list (never raises) if brew is not installed or the
    command fails for any reason.
    """
    if not which("brew"):
        return []

    env = {**os.environ, "HOMEBREW_NO_AUTO_UPDATE": "1"}
    try:
        result = subprocess.run(
            ["brew", "cleanup", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    findings: list[Finding] = []
    for line in result.stdout.splitlines():
        m = _REMOVE_RE.match(line.strip())
        if not m:
            continue
        path = m.group("path")
        size = _parse_size(m.group("size"))
        qualifier = (m.group("qualifier") or "").strip(" ()")
        reason = f"brew cleanup: safe to remove" + (f" ({qualifier})" if qualifier else "")
        findings.append(
            Finding(
                category="brew_cache",
                path=path,
                size_bytes=size,
                risk="auto_safe",
                reason=reason,
                source="brew",
            )
        )

    return findings
