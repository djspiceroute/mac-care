from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


Risk = Literal["auto_safe", "review", "protected"]


@dataclass(frozen=True)
class Finding:
    category: str
    path: str
    size_bytes: int
    risk: Risk
    reason: str


@dataclass(frozen=True)
class ToolStatus:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class Report:
    findings: list[Finding]
    tools: list[ToolStatus]

    def to_dict(self) -> dict:
        return {
            "findings": [asdict(item) for item in self.findings],
            "tools": [asdict(item) for item in self.tools],
        }


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024


def path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        return path.stat().st_size

    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file() and not child.is_symlink():
                total += child.stat().st_size
        except (FileNotFoundError, PermissionError, OSError):
            continue
    return total
