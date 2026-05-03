from __future__ import annotations

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


@staticmethod
def _tool_installed(name: str) -> bool:
    return which(name) is not None


def check_tools(include_optional: bool = True) -> list[ToolStatus]:
    statuses: list[ToolStatus] = []
    for name in REQUIRED_TOOLS:
        found = which(name)
        statuses.append(ToolStatus(name=name, status="ok" if found else "missing", detail=found or "not on PATH"))

    path = os.environ.get("PATH", "")
    if "/opt/homebrew/bin" in path:
        statuses.append(ToolStatus(name="homebrew_path", status="ok", detail="/opt/homebrew/bin is on PATH"))
    else:
        statuses.append(ToolStatus(name="homebrew_path", status="review", detail="/opt/homebrew/bin is missing from PATH"))

    statuses.append(_docker_status())

    if include_optional:
        for name in OSS_OPTIONAL_TOOLS:
            found = which(name)
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
