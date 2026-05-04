"""
action_log.py — append-only JSONL history of bulk cleanup actions.

Written to ~/.mac-care/action-log.jsonl, one JSON object per line.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import Config
from .model import format_bytes


def append_action(config: Config, entry: dict) -> None:
    """Append *entry* as a single JSON line to the action log."""
    log_path = _log_path(config)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def load_action_history(config: Config) -> list[dict]:
    """Return all action log entries, newest first."""
    log_path = _log_path(config)
    if not log_path.exists():
        return []
    entries = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(entries))


def render_history_text(entries: list[dict], limit: int = 20) -> str:
    if not entries:
        return "No action history found."
    lines = ["Action history (newest first):\n"]
    for entry in entries[:limit]:
        ts = entry.get("timestamp", "?")
        action = entry.get("action", "?")
        category = entry.get("category", "all")
        count = entry.get("count", 0)
        total_bytes = entry.get("total_bytes", 0)
        skipped = entry.get("skipped", 0)
        dry = " [dry-run]" if entry.get("dry_run") else ""
        lines.append(
            f"  {ts}  {action:<18} {category:<30} "
            f"{count} item(s) ({format_bytes(total_bytes)})"
            f"{f'  {skipped} skipped' if skipped else ''}{dry}"
        )
    if len(entries) > limit:
        lines.append(f"\n  … {len(entries) - limit} older entries not shown")
    return "\n".join(lines)


def _log_path(config: Config) -> Path:
    return config.reports_dir / "action-log.jsonl"
