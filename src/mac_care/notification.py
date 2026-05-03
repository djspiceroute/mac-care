from __future__ import annotations

import subprocess

from .model import format_bytes
from .summary import ScanSummary


def notification_text(summary: ScanSummary) -> str:
    auto_safe = summary.risks["auto_safe"]
    review = summary.risks["review"]
    protected = summary.risks["protected"]
    return (
        f"{format_bytes(auto_safe.size_bytes)} auto-safe, "
        f"{format_bytes(review.size_bytes)} review, "
        f"{protected.count} protected, "
        f"{summary.tool_warning_count} tool warnings"
    )


def notify_scan_complete(summary: ScanSummary) -> bool:
    message = notification_text(summary)
    script = f'display notification "{_escape_osascript(message)}" with title "Mac Care scan complete"'
    try:
        result = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _escape_osascript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
