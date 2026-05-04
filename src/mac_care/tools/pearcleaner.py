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

import os
import plistlib
import re
import subprocess
from pathlib import Path
from shutil import which

from ..model import Finding, path_size

# Known paths where pearcleaner binary may live even if not on PATH
_APP_BINARY_PATHS = [
    "/Applications/Pearcleaner.app/Contents/MacOS/Pearcleaner",
    "/opt/homebrew/bin/pearcleaner",  # brew --cask symlink target
]

# Directories to scan for installed .app bundles
_APP_DIRS = [
    Path("/Applications"),
    Path("/Applications/Setapp"),
    Path("/System/Applications"),
    Path(os.path.expanduser("~/Applications")),
]

# Team IDs are 10 uppercase alphanumeric characters followed by a dot
_TEAM_ID_RE = re.compile(r"^[A-Z0-9]{10}\.")


def _pearcleaner_bin() -> str | None:
    """Return path to the pearcleaner binary, or None if not found."""
    found = which("pearcleaner")
    if found:
        return found
    for candidate in _APP_BINARY_PATHS:
        if Path(candidate).exists():
            return candidate
    return None


def _pkgutil_package_ids() -> set[str]:
    """Return lowercased package receipt IDs from ``pkgutil --pkgs``.

    Catches apps installed via .pkg installers (Adobe, VMware, enterprise tools)
    that don't leave a .app bundle in /Applications/.
    Returns an empty set if pkgutil is unavailable or fails.
    """
    try:
        result = subprocess.run(
            ["pkgutil", "--pkgs"],
            capture_output=True, text=True, timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return set()
    return {line.strip().lower() for line in result.stdout.splitlines() if line.strip()}


def _installed_app_identifiers() -> frozenset[str]:
    """Return a frozenset of lowercased strings that identify currently installed apps.

    Sources:
    - .app bundles in /Applications/, /Applications/Setapp/, /System/Applications/,
      ~/Applications/ (depth 1 and 2): CFBundleIdentifier, CFBundleName,
      CFBundleDisplayName, and the bundle stem
    - pkgutil receipt IDs: catches pkg-installed apps (Adobe, VMware, etc.)
    """
    identifiers: set[str] = set()

    for app_dir in _APP_DIRS:
        if not app_dir.exists():
            continue
        try:
            # depth-1: /Applications/Foo.app
            # depth-2: /Applications/Vendor/Foo.app  (Adobe, WD Discovery, etc.)
            apps = list(app_dir.glob("*.app")) + list(app_dir.glob("*/*.app"))
        except (OSError, PermissionError):
            continue
        for app in apps:
            identifiers.add(app.stem.lower())
            plist_path = app / "Contents" / "Info.plist"
            if not plist_path.exists():
                continue
            try:
                with plist_path.open("rb") as fh:
                    info = plistlib.load(fh)
            except Exception:
                continue
            for key in ("CFBundleIdentifier", "CFBundleName", "CFBundleDisplayName"):
                val = info.get(key, "")
                if val:
                    identifiers.add(val.lower())

    identifiers.update(_pkgutil_package_ids())
    return frozenset(identifiers)


def _belongs_to_installed_app(path: Path, installed: frozenset[str]) -> bool:
    """Return True if *path* looks like it belongs to a currently installed app.

    Handles five cases that Pearcleaner's CLI misses:
    1. Exact bundle-ID or app-name match: ``com.spotify.client``, ``Spotify``
    2. Extension/helper suffix: ``com.spotify.client.helper`` (parent is installed)
    3. Team-ID prefix strip: ``2BBY89MBSN.dev.warp`` → ``dev.warp``
    4. Team-ID + group prefix: ``TEAMID.group.com.app`` → ``com.app``
    5. Reverse prefix (pkgutil): path name is a shared prefix of an installed pkg ID
       e.g. ``com.adobe.acrobat`` matches receipt ``com.adobe.acrobat.DC.sca.config``
    """
    name = path.stem if path.is_file() else path.name
    name_lower = name.lower()

    # Cases 1: direct match against bundle IDs or app names
    if name_lower in installed:
        return True

    # Case 2: extension / helper (name starts with an installed bundle ID)
    # e.g. com.dashlane.dashlanephonefinal.SafariWebExtension → com.dashlane.dashlanephonefinal
    for ident in installed:
        if name_lower.startswith(ident + "."):
            return True

    # Case 5: reverse prefix — name is a meaningful prefix of a pkgutil receipt ID
    # e.g. com.adobe.acrobat → com.adobe.acrobat.DC.sca.config (installed)
    # Require at least two dot-separated components to avoid spurious matches.
    if "." in name_lower:
        for ident in installed:
            if ident.startswith(name_lower + "."):
                return True

    # Cases 3 & 4: strip 10-char team-ID prefix then re-check cases 1, 2, 5
    stripped = _TEAM_ID_RE.sub("", name)
    if stripped != name:
        s = stripped.lower()
        # Remove "group." prefix that macOS app-group IDs commonly carry
        if s.startswith("group."):
            s = s[6:]
        if s in installed:
            return True
        for ident in installed:
            if s.startswith(ident + ".") or ident.startswith(s + "."):
                return True

    return False


def pearcleaner_findings() -> list[Finding]:
    """Run ``pearcleaner list-orphaned`` and return one Finding per orphaned path.

    Paths that belong to currently installed apps are filtered out (Pearcleaner's
    CLI does not check all app locations such as /Applications/Setapp/ and does not
    resolve app-extension bundle IDs back to their parent app).

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

    installed = _installed_app_identifiers()

    findings: list[Finding] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip the summary line: "Found N orphaned files."
        if line.startswith("Found ") and line.endswith("orphaned files."):
            continue

        path = Path(line)

        if _belongs_to_installed_app(path, installed):
            continue

        app_name = _guess_app_name(path)
        reason = "orphaned app support files" + (f" for {app_name}" if app_name else "")

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
