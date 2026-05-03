from __future__ import annotations

from pathlib import Path
from shutil import which
import os
import subprocess

from .model import ToolStatus


REQUIRED_TOOLS = [
    "brew",
    "git",
    "gh",
    "go",
    "node",
    "pnpm",
    "python3",
    "docker",
    "supabase",
    "gemini",
    "codex",
]

OSS_OPTIONAL_TOOLS = [
    "gdu",
    "ncdu",
    "dust",
    "dua",
    "mole",
    "cleardisk",
    "mas",
    "pearcleaner",
]

# Grouped recommendations shown by `mac-care tools recommend`.
# Keys match entries in OSS_OPTIONAL_TOOLS where relevant.
TOOL_RECOMMENDATIONS: dict[str, dict[str, str]] = {
    # --- Disk analysis ---
    "dua": {
        "group": "Disk analysis",
        "desc": "Fast parallel disk usage tree — primary backend for mac-care scan",
        "install": "brew install dua-cli",
    },
    "dust": {
        "group": "Disk analysis",
        "desc": "Rust-based directory size tree, great for quick terminal overviews",
        "install": "brew install dust",
    },
    "gdu": {
        "group": "Disk analysis",
        "desc": "Interactive Go disk usage browser (ncdu alternative)",
        "install": "brew install gdu",
    },
    "ncdu": {
        "group": "Disk analysis",
        "desc": "Classic ncurses disk usage browser",
        "install": "brew install ncdu",
    },
    # --- Package / app management ---
    "mas": {
        "group": "Package management",
        "desc": "Mac App Store CLI — check for app updates from the terminal",
        "install": "brew install mas",
    },
    "pearcleaner": {
        "group": "App cleanup",
        "desc": "Finds orphaned app support files left behind after app deletion",
        "install": "brew install --cask pearcleaner",
    },
    # --- Network / SSH ---
    "mole": {
        "group": "Network",
        "desc": "SSH tunnel manager — not used by mac-care scan but useful on a dev machine",
        "install": "brew install mole",
    },
}


# Common bin dirs that non-interactive shells (launchd, subprocess) often miss
_EXTRA_BIN_DIRS = [
    Path.home() / ".npm-global/bin",
    Path.home() / ".local/bin",
    Path.home() / ".cargo/bin",
    Path("/usr/local/bin"),
]


def _find_tool(name: str) -> str | None:
    """Like shutil.which but also searches _EXTRA_BIN_DIRS when not on PATH."""
    found = which(name)
    if found:
        return found
    for d in _EXTRA_BIN_DIRS:
        candidate = d / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _tool_installed(name: str) -> bool:
    return _find_tool(name) is not None


def check_tools(include_optional: bool = True) -> list[ToolStatus]:
    statuses: list[ToolStatus] = []
    for name in REQUIRED_TOOLS:
        found = _find_tool(name)
        statuses.append(ToolStatus(name=name, status="ok" if found else "missing", detail=found or "not on PATH"))

    path = os.environ.get("PATH", "")
    if "/opt/homebrew/bin" in path:
        statuses.append(ToolStatus(name="homebrew_path", status="ok", detail="/opt/homebrew/bin is on PATH"))
    else:
        statuses.append(ToolStatus(name="homebrew_path", status="review", detail="/opt/homebrew/bin is missing from PATH"))

    statuses.append(_docker_status())
    statuses.extend(check_ssh_keys())
    statuses.extend(check_redundant_toolchains())

    if include_optional:
        for name in OSS_OPTIONAL_TOOLS:
            found = _find_tool(name)
            statuses.append(ToolStatus(name=name, status="available" if found else "optional_missing", detail=found or "optional integration not installed"))

    return statuses


def recommend_tools() -> list[dict[str, str]]:
    """Return recommendations for missing optional OSS tools, grouped by function.

    Each entry is a dict with keys: name, group, desc, install, status.
    Only tools that are NOT already installed are included.
    """
    missing = []
    for name, info in TOOL_RECOMMENDATIONS.items():
        if not which(name):
            missing.append({"name": name, **info, "status": "not installed"})
    return missing


def _docker_status() -> ToolStatus:
    if not which("docker"):
        return ToolStatus(name="docker_daemon", status="missing", detail="docker CLI is not on PATH")
    try:
        result = subprocess.run(["docker", "info"], check=False, capture_output=True, text=True, timeout=8)
    except subprocess.TimeoutExpired:
        return ToolStatus(name="docker_daemon", status="review", detail="docker info timed out")
    if result.returncode == 0:
        return ToolStatus(name="docker_daemon", status="ok", detail="daemon is reachable")
    return ToolStatus(name="docker_daemon", status="review", detail=(result.stderr or result.stdout).strip().splitlines()[0:1][0] if (result.stderr or result.stdout).strip() else "daemon not reachable")


# ── #29 SSH key passphrase check ─────────────────────────────────────────────

def check_ssh_keys() -> list[ToolStatus]:
    """Flag SSH private keys that appear to lack passphrase encryption."""
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.exists():
        return []

    statuses: list[ToolStatus] = []
    for key_file in sorted(ssh_dir.iterdir()):
        if not key_file.is_file():
            continue
        # Only inspect files that look like private keys (no .pub extension, no config/known_hosts)
        if key_file.suffix in {".pub", ".toml"} or key_file.name in {"config", "known_hosts", "known_hosts.old", "authorized_keys"}:
            continue
        try:
            header = key_file.read_bytes()[:256]
        except (PermissionError, OSError):
            continue
        if b"PRIVATE KEY" not in header and b"PuTTY-User-Key" not in header:
            continue
        # Encrypted OpenSSH keys contain "bcrypt" KDF header; legacy PEM keys contain "ENCRYPTED"
        encrypted = b"bcrypt" in header or b"ENCRYPTED" in header or b"Proc-Type: 4,ENCRYPTED" in header
        if encrypted:
            statuses.append(ToolStatus(
                name=f"ssh_key:{key_file.name}",
                status="ok",
                detail="passphrase-protected",
            ))
        else:
            statuses.append(ToolStatus(
                name=f"ssh_key:{key_file.name}",
                status="review",
                detail="no passphrase detected — note: Keychain-stored passphrases cannot be verified here",
            ))
    return statuses


# ── #37 Redundant toolchain installations ────────────────────────────────────

# Common paths where language runtimes are installed outside the system default.
_TOOLCHAIN_SEARCH_PATHS = [
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
]

_LANGUAGE_BINARIES: dict[str, list[str]] = {
    "python": ["python3", "python"],
    "node": ["node"],
    "ruby": ["ruby"],
    "go": ["go"],
    "rust": ["rustc"],
}


def check_redundant_toolchains() -> list[ToolStatus]:
    """Detect languages installed via multiple managers or in multiple PATH locations."""
    statuses: list[ToolStatus] = []
    for language, binaries in _LANGUAGE_BINARIES.items():
        found_paths: list[str] = []
        for binary in binaries:
            for search_path in _TOOLCHAIN_SEARCH_PATHS:
                candidate = Path(search_path) / binary
                if candidate.exists():
                    found_paths.append(str(candidate))
        # Also check what `which` finds as primary
        primary = which(binaries[0])
        if primary and primary not in found_paths:
            found_paths.insert(0, primary)

        found_paths = list(dict.fromkeys(found_paths))  # deduplicate preserving order

        if len(found_paths) > 1:
            # Check for PATH shadowing: primary which differs from first search path hit
            shadowing = primary and found_paths and primary != found_paths[0]
            detail = f"{len(found_paths)} installations found: {', '.join(found_paths)}"
            if shadowing:
                detail += f" — PATH_SHADOWING: {primary} is active but {found_paths[0]} also exists"
            statuses.append(ToolStatus(name=f"toolchain:{language}", status="review", detail=detail))
        elif found_paths:
            statuses.append(ToolStatus(name=f"toolchain:{language}", status="ok", detail=found_paths[0]))
        else:
            statuses.append(ToolStatus(name=f"toolchain:{language}", status="missing", detail="not found on PATH or common locations"))

    return statuses
