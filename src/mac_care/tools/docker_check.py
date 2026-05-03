"""
tools/docker_check.py — Docker disk usage findings via `docker system df`.

Reports reclaimable space per category (images, containers, volumes, build
cache) as review-risk findings. Never auto-cleans anything — Docker cleanup
requires explicit user action (docker system prune, etc.).
"""
from __future__ import annotations

import json
import re
import subprocess
from shutil import which

from ..model import Finding

# Maps docker Type → (mac-care category, cleanup hint)
_TYPE_META: dict[str, tuple[str, str]] = {
    "Images":      ("docker_images",       "remove with: docker image prune [-a]"),
    "Containers":  ("docker_containers",   "remove with: docker container prune"),
    "Local Volumes": ("docker_volumes",    "remove with: docker volume prune"),
    "Build Cache": ("docker_build_cache",  "remove with: docker builder prune"),
}

# Parses size strings like "9.789GB", "197.6MB", "1.227MB", "0B"
_SIZE_RE = re.compile(r"^(?P<value>[0-9.]+)\s*(?P<unit>[KMGT]?B)$", re.IGNORECASE)

_UNIT_BYTES: dict[str, int] = {
    "B":  1,
    "KB": 1_000,
    "MB": 1_000_000,
    "GB": 1_000_000_000,
    "TB": 1_000_000_000_000,
}


def _parse_docker_size(raw: str) -> int:
    """Convert docker size string like '9.789GB' or '197.6MB (13%)' to bytes."""
    # Strip parenthetical percentage if present: "9.789GB (49%)" → "9.789GB"
    raw = raw.split("(")[0].strip()
    m = _SIZE_RE.match(raw)
    if not m:
        return 0
    try:
        value = float(m.group("value"))
        unit = m.group("unit").upper()
        return int(value * _UNIT_BYTES.get(unit, 1))
    except (ValueError, KeyError):
        return 0


def _docker_available() -> bool:
    return which("docker") is not None


def _daemon_reachable() -> bool:
    """Return True if the Docker daemon is running and reachable."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def docker_findings() -> list[Finding]:
    """Run ``docker system df --format '{{json .}}'`` and return one Finding
    per category that has reclaimable space > 0.

    All findings are risk="review" — Docker cleanup is always user-initiated.
    Returns [] (never raises) if Docker is not installed or daemon is offline.
    """
    if not _docker_available():
        return []
    if not _daemon_reachable():
        return []

    try:
        result = subprocess.run(
            ["docker", "system", "df", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    findings: list[Finding] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue

        docker_type = row.get("Type", "")
        category, hint = _TYPE_META.get(docker_type, (None, None))
        if category is None:
            continue

        reclaimable_bytes = _parse_docker_size(row.get("Reclaimable", "0B"))
        if reclaimable_bytes == 0:
            continue

        total_bytes = _parse_docker_size(row.get("Size", "0B"))
        total_count = row.get("TotalCount", "?")
        active = row.get("Active", "?")

        reason = (
            f"{total_count} total, {active} active; "
            f"reclaimable: {row.get('Reclaimable', '?')}; {hint}"
        )

        findings.append(Finding(
            category=category,
            path="docker://" + docker_type.lower().replace(" ", "_"),
            size_bytes=reclaimable_bytes,
            risk="review",
            reason=reason,
            source="docker",
        ))

    return findings
