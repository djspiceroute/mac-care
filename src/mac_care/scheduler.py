from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

from .config import Config


LABEL = "com.mac-care.periodic"
PLIST_PATH = Path("~/Library/LaunchAgents/com.mac-care.periodic.plist").expanduser()


@dataclass(frozen=True)
class ScheduleResult:
    plist_path: Path
    message: str


def default_program_arguments() -> list[str]:
    """Resolve the absolute path to the mac-care executable or python -m mac_care."""
    executable = shutil.which("mac-care")
    if executable:
        return [str(Path(executable).resolve()), "scan", "--notify"]

    # Fallback to current python executable running the mac_care package
    return [sys.executable, "-m", "mac_care", "scan", "--notify"]


def get_schedule_status() -> ScheduleResult:
    """Check the status of the periodic scan schedule."""
    if not PLIST_PATH.exists():
        return ScheduleResult(PLIST_PATH, f"No schedule installed at {PLIST_PATH}")

    try:
        payload = plistlib.loads(PLIST_PATH.read_bytes())
        args = payload.get("ProgramArguments", [])
        executable = args[0] if args else "unknown"
        interval = payload.get("StartInterval", 0) // 3600
        return ScheduleResult(
            PLIST_PATH,
            f"Schedule installed at {PLIST_PATH}\n"
            f"  Executable: {executable}\n"
            f"  Interval:   {interval}h"
        )
    except Exception as e:
        return ScheduleResult(PLIST_PATH, f"Error reading schedule at {PLIST_PATH}: {e}")


def build_plist(config: Config, interval_hours: int = 24, program_arguments: list[str] | None = None) -> dict:
    interval_seconds = max(1, interval_hours) * 3600
    logs_dir = config.reports_dir.parent / "logs"
    return {
        "Label": LABEL,
        "ProgramArguments": program_arguments or default_program_arguments(),
        "StartInterval": interval_seconds,
        "RunAtLoad": False,
        "StandardOutPath": str(logs_dir / "mac-care-schedule.out.log"),
        "StandardErrorPath": str(logs_dir / "mac-care-schedule.err.log"),
        "EnvironmentVariables": {
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
    }


def render_plist(config: Config, interval_hours: int = 24, program_arguments: list[str] | None = None) -> str:
    payload = build_plist(config, interval_hours=interval_hours, program_arguments=program_arguments)
    return plistlib.dumps(payload, sort_keys=True).decode("utf-8")


def install_schedule(config: Config, interval_hours: int = 24, dry_run: bool = True) -> ScheduleResult:
    plist_text = render_plist(config, interval_hours=interval_hours)
    if dry_run:
        return ScheduleResult(PLIST_PATH, plist_text)

    config.ensure_dirs()
    (config.reports_dir.parent / "logs").mkdir(parents=True, exist_ok=True)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist_text, encoding="utf-8")
    activation_msg = _launchctl_load(PLIST_PATH)
    return ScheduleResult(PLIST_PATH, f"Installed schedule at {PLIST_PATH}. {activation_msg}")


def uninstall_schedule(dry_run: bool = True) -> ScheduleResult:
    if dry_run:
        return ScheduleResult(PLIST_PATH, f"Would unload and remove {PLIST_PATH}")

    _launchctl_unload(PLIST_PATH)
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
        return ScheduleResult(PLIST_PATH, f"Removed schedule at {PLIST_PATH}")
    return ScheduleResult(PLIST_PATH, f"No schedule found at {PLIST_PATH}")


def _launchctl_load(plist_path: Path) -> str:
    if not shutil.which("launchctl"):
        return "launchctl not found — job will activate on next login."
    import os
    uid = str(os.getuid())
    result = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
        check=False, capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        return "Job activated via launchctl bootstrap."
    # Fall back to legacy load (pre-10.11 or if bootstrap fails)
    fallback = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        check=False, capture_output=True, text=True, timeout=10,
    )
    if fallback.returncode == 0:
        return "Job activated via launchctl load (fallback)."
    error = (result.stderr or fallback.stderr or "unknown error").strip().splitlines()[0]
    return f"Job registered but activation failed ({error}) — it will activate on next login."


def _launchctl_unload(plist_path: Path) -> None:
    if not plist_path.exists() or not shutil.which("launchctl"):
        return
    subprocess.run(["launchctl", "unload", str(plist_path)], check=False, capture_output=True, text=True, timeout=10)
