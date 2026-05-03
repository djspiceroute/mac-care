"""
tools/disk.py — disk usage analysis via dua (preferred) or macOS du (fallback).

dua (https://github.com/Byron/dua-cli) is fast and parallel.
macOS `du` is always available and used when dua is not installed.

Public API
----------
size_of(path)           → int bytes  (total size of path)
top_subdirs(path, n=5)  → list[(Path, int)]  (largest N immediate children)
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from shutil import which

# Strip ANSI escape sequences from dua output
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


# ---------------------------------------------------------------------------
# dua helpers
# ---------------------------------------------------------------------------

def _dua_available() -> bool:
    return which("dua") is not None


def _run_dua(path: Path) -> list[tuple[Path, int]]:
    """Run ``dua aggregate -f bytes <children...>`` and return (child, bytes) pairs.

    We expand children in Python (not shell) to avoid glob quoting issues in
    subprocess. Skips the "total" summary line. Returns [] on any failure.
    """
    try:
        children = [str(c) for c in path.iterdir()]
    except (PermissionError, OSError):
        return []
    if not children:
        return []

    try:
        result = subprocess.run(
            ["dua", "aggregate", "-f", "bytes", "--no-sort", *children],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    entries: list[tuple[Path, int]] = []
    for raw_line in result.stdout.splitlines():
        line = _strip_ansi(raw_line).strip()
        if not line or line.endswith("total"):
            continue
        # Format: "<bytes> b <path>"
        parts = line.split(None, 2)  # ["27406336", "b", "/path/to/dir"]
        if len(parts) != 3 or parts[1] != "b":
            continue
        try:
            size = int(parts[0])
            child = Path(parts[2])
            entries.append((child, size))
        except (ValueError, IndexError):
            continue
    return entries


# ---------------------------------------------------------------------------
# du fallback helpers
# ---------------------------------------------------------------------------

def _run_du(path: Path) -> list[tuple[Path, int]]:
    """Run ``du -d 1 -k <path>`` (macOS built-in) and return (child, bytes) pairs.

    -d 1 limits to immediate children. -k gives kilobytes.
    Returns [] on any failure.
    """
    try:
        result = subprocess.run(
            ["du", "-d", "1", "-k", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    entries: list[tuple[Path, int]] = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        try:
            size_bytes = int(parts[0]) * 1024  # kilobytes → bytes
            child = Path(parts[1])
            # Skip the path itself (du -d 1 includes a summary line for the root)
            if child == path:
                continue
            entries.append((child, size_bytes))
        except (ValueError, IndexError):
            continue
    return entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def top_subdirs(path: Path, n: int = 5) -> list[tuple[Path, int]]:
    """Return the *n* largest immediate children of *path*, sorted descending.

    Uses dua if available, falls back to macOS du. Returns [] if path doesn't
    exist or all backends fail.
    """
    if not path.exists():
        return []

    entries = _run_dua(path) if _dua_available() else _run_du(path)
    entries.sort(key=lambda e: e[1], reverse=True)
    return entries[:n]


def size_of(path: Path) -> int:
    """Return total disk usage of *path* in bytes.

    Uses dua aggregate total if available, otherwise sums du -d 1 output.
    Falls back to Python rglob if both fail (imported lazily to avoid circular).
    """
    if not path.exists():
        return 0

    if _dua_available():
        entries = _run_dua(path)
        if entries:
            return sum(size for _, size in entries)

    # du fallback — sum all child entries (root summary not included after filtering)
    entries = _run_du(path)
    if entries:
        return sum(size for _, size in entries)

    # Last resort: Python rglob (slow but always works)
    from ..model import path_size
    return path_size(path)


def top_subdirs_summary(path: Path, n: int = 5) -> str:
    """Return a human-readable summary of the top N subdirs, e.g. for Finding.reason.

    Example: "largest: Google (1.3 GB), ms-playwright (1.1 GB), SiriTTS (499 MB)"
    Returns empty string if no data available.
    """
    from ..model import format_bytes

    entries = top_subdirs(path, n)
    if not entries:
        return ""
    parts = [f"{child.name} ({format_bytes(size)})" for child, size in entries]
    return "largest: " + ", ".join(parts)
