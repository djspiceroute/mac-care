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
]


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
