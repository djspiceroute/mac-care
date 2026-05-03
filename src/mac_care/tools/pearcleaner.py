"""
tools/pearcleaner.py — orphaned app support file findings via Pearcleaner CLI.

Pearcleaner (https://github.com/alienator88/Pearcleaner) finds leftover files
from deleted apps: support directories, preferences, caches, logs that remain
after dragging an app to the trash.

CLI: `pearcleaner list-orphaned`
Output: one absolute path per line, ending with "Found N orphaned files."

All findings are risk="review" — orphaned file cleanup always requires human
confirmation. Never auto-clean anything from this source.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from shutil import which

from ..model import Finding, path_size

# Known paths where pearcleaner binary may live even if not on PATH
_APP_BINARY_PATHS = [
    "/Applications/Pearcleaner.app/Contents/MacOS/Pearcleaner",
    "/opt/homebrew/bin/pearcleaner",  # brew --cask symlink target
]


def _pearcleaner_bin() -> str | None:
    """Return path to the pearcleaner binary, or None if not found."""
    found = which("pearcleaner")
    if found:
        return found
    for candidate in _APP_BINARY_PATHS:
        if Path(candidate).exists():
            return candidate
    return None


def pearcleaner_findings() -> list[Finding]:
    """Run ``pearcleaner list-orphaned`` and return one Finding per orphaned path.

    Each finding is risk="review" — the user must confirm before any deletion.
    Returns [] (never raises) if Pearcleaner is not installed or the command fails.
    """
    binary = _pearcleaner_bin()
    if not binary:
        return []

    try:
        result = subprocess.run(
            [binary, "list-orphaned"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    findings: list[Finding] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip the summary line: "Found N orphaned files."
        if line.startswith("Found ") and line.endswith("orphaned files."):
            continue

        path = Path(line)
        # Determine a human-readable app name from the path for the reason field
        app_name = _guess_app_name(path)
        reason = f"orphaned app support files" + (f" for {app_name}" if app_name else "")

        findings.append(Finding(
            category="orphaned_app_files",
            path=str(path),
            size_bytes=path_size(path),
            risk="review",
            reason=reason,
            source="pearcleaner",
        ))

    return findings


def _guess_app_name(path: Path) -> str:
    """Extract a readable app identifier from a support file path.

    Examples:
      ~/Library/Application Support/com.example.App  → com.example.App
      ~/Library/Caches/com.example.App               → com.example.App
      ~/Library/Preferences/com.example.App.plist    → com.example.App
    """
    name = path.stem if path.is_file() else path.name
    # Strip leading dots from hidden dirs
    return name.lstrip(".")
