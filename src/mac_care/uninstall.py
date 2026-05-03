from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .clean import quarantine_finding
from .config import Config
from .model import Finding, format_bytes, path_size
from .tools.pearcleaner import _pearcleaner_bin

# Order matters: resolve() resolves symlinks, so we compare against resolved bases
_DEFAULT_APP_BASES: tuple[Path, ...] = (Path("/Applications"), Path.home() / "Applications")


@dataclass
class UninstallResult:
    app_path: Path | None
    support_files: list[Finding]
    app_hint: str


def find_app(name: str) -> Path | None:
    """Locate a .app bundle by name in /Applications or ~/Applications."""
    for base in [Path("/Applications"), Path.home() / "Applications"]:
        # Exact match first
        candidate = base / f"{name}.app"
        if candidate.exists():
            return candidate
        # Case-insensitive fallback
        if base.exists():
            for item in base.iterdir():
                if item.suffix == ".app" and item.stem.lower() == name.lower():
                    return item
    return None


def validate_app_bundle(
    app_path: Path, *, allowed_bases: tuple[Path, ...] = _DEFAULT_APP_BASES
) -> bool:
    """Validate that *app_path* is a real, trusted macOS app bundle.

    Checks:
        - exists
        - resolves to a path under one of *allowed_bases*
        - name ends with ``.app``
        - is a directory (not a symlink or file)
        - contains ``Contents/Info.plist``
    """
    if not app_path.exists():
        return False

    resolved = app_path.resolve()

    # Must be under an allowed base directory
    if not any(
        resolved == base.resolve() or base.resolve() in resolved.parents
        for base in allowed_bases
    ):
        return False

    # Must look like a bundle
    if not resolved.name.endswith(".app"):
        return False

    # Must be a real directory, not a symlink
    if app_path.is_symlink():
        return False

    # Must contain the canonical plist
    if not (resolved / "Contents" / "Info.plist").exists():
        return False

    return True


def discover_support_files(app_path: Path) -> list[Finding]:
    """Return findings for support files related to the given .app bundle.

    Uses Pearcleaner if available; falls back to standard ~/Library/ patterns.
    """
    binary = _pearcleaner_bin()
    if binary:
        return _discover_via_pearcleaner(app_path, binary)
    return _discover_native(app_path)


def _discover_via_pearcleaner(app_path: Path, binary: str) -> list[Finding]:
    import subprocess
    try:
        result = subprocess.run(
            [binary, "list-orphaned", "--app", str(app_path)],
            capture_output=True, text=True, timeout=60,
        )
        findings: list[Finding] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or (line.startswith("Found ") and "orphaned" in line):
                continue
            p = Path(line)
            size = path_size(p)
            findings.append(Finding(
                category="uninstall_support",
                path=str(p),
                size_bytes=size,
                risk="review",
                reason=f"support file for {app_path.stem}",
                source="pearcleaner",
            ))
        return findings
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return _discover_native(app_path)


def _discover_native(app_path: Path) -> list[Finding]:
    """Check standard ~/Library locations for files related to the app."""
    home = Path.home()
    app_name = app_path.stem

    # Attempt to read bundle ID from Info.plist — used for preference file lookup
    bundle_id = _read_bundle_id(app_path)

    candidates: list[Path] = []

    # Directory-based lookups
    for lib_subdir in [
        "Application Support",
        "Caches",
        "Logs",
        "Containers",
        f"WebKit",
    ]:
        for candidate_name in ([app_name] + ([bundle_id] if bundle_id else [])):
            p = home / "Library" / lib_subdir / candidate_name
            if p.exists():
                candidates.append(p)

    # Preference plists
    if bundle_id:
        for plist_name in [f"{bundle_id}.plist", f"{bundle_id}.lockfile"]:
            p = home / "Library/Preferences" / plist_name
            if p.exists():
                candidates.append(p)

    findings: list[Finding] = []
    seen: set[str] = set()
    for p in candidates:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        findings.append(Finding(
            category="uninstall_support",
            path=str(p),
            size_bytes=path_size(p),
            risk="review",
            reason=f"support file for {app_name}",
            source="native",
        ))
    return findings


def _read_bundle_id(app_path: Path) -> str | None:
    """Extract CFBundleIdentifier from Info.plist without parsing full XML."""
    plist = app_path / "Contents/Info.plist"
    if not plist.exists():
        return None
    try:
        import plistlib
        data = plistlib.loads(plist.read_bytes())
        return data.get("CFBundleIdentifier")
    except Exception:
        return None


def app_deletion_hint(
    app_path: Path | None, *, allowed_bases: tuple[Path, ...] = _DEFAULT_APP_BASES
) -> str:
    """Return an appropriate deletion hint based on actual write permissions.

    Privileged removal guidance is shown ONLY after the app bundle passes
    strict validation (validate_app_bundle). Untrusted or invalid paths
    never receive sudo guidance.
    """
    if app_path is None:
        return ""

    if not validate_app_bundle(app_path, allowed_bases=allowed_bases):
        return (
            f"App bundle validation failed for '{app_path}'.\n"
            "  Privileged removal guidance is hidden for unverified paths.\n"
            "  Remove the app manually via Finder if appropriate."
        )

    if os.access(app_path, os.W_OK):
        return f"You own this app — to remove it: trash '{app_path}'"

    return (
        f"This app requires elevated permissions to remove:\n"
        f"  sudo rm -rf '{app_path}'\n"
        f"  ⚠️  Double-check the path before running this command."
    )


def render_uninstall_report(result: UninstallResult) -> str:
    lines: list[str] = []

    if result.app_path:
        app_size = path_size(result.app_path)
        lines.append(f"Found: {result.app_path}  ({format_bytes(app_size)})")
    else:
        lines.append("App bundle not found in /Applications or ~/Applications.")

    if result.support_files:
        total = sum(f.size_bytes for f in result.support_files)
        lines.append(f"\nRelated files ({format_bytes(total)} total):")
        for f in sorted(result.support_files, key=lambda x: x.size_bytes, reverse=True):
            lines.append(f"  {f.path}  {format_bytes(f.size_bytes)}  [{f.risk}]  (via {f.source})")
    else:
        lines.append("\nNo related support files found.")

    grand_total = (path_size(result.app_path) if result.app_path else 0) + sum(f.size_bytes for f in result.support_files)
    lines.append(f"\nTotal reclaim potential: {format_bytes(grand_total)}")

    if result.support_files:
        lines.append("Run with --execute to quarantine support files.")

    if result.app_path:
        lines.append(f"\n{result.app_hint}")

    return "\n".join(lines)
