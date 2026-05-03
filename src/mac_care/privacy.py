from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


TCC_DB = Path("~/Library/Application Support/com.apple.TCC/TCC.db").expanduser()

# Human-readable names for TCC service keys
SERVICE_NAMES: dict[str, str] = {
    "kTCCServiceCamera": "Camera",
    "kTCCServiceMicrophone": "Microphone",
    "kTCCServiceScreenCapture": "Screen Recording",
    "kTCCServiceAccessibility": "Accessibility",
    "kTCCServiceSystemPolicyAllFiles": "Full Disk Access",
    "kTCCServiceLocation": "Location",
    "kTCCServiceContacts": "Contacts",
    "kTCCServiceCalendar": "Calendar",
    "kTCCServiceReminders": "Reminders",
    "kTCCServicePhotos": "Photos",
    "kTCCServiceMediaLibrary": "Media Library",
    "kTCCServiceSpeechRecognition": "Speech Recognition",
    "kTCCServiceListenEvent": "Input Monitoring",
    "kTCCServicePostEvent": "Accessibility (Post Events)",
    "kTCCServiceScreenCommunication": "Screen Communication",
}


@dataclass
class PermissionEntry:
    service: str
    service_display: str
    bundle_id: str
    app_name: str
    allowed: bool
    last_modified: str | None


def check_fda() -> bool:
    """Return True if mac-care can read the user TCC database."""
    try:
        conn = sqlite3.connect(f"file:{TCC_DB}?mode=ro", uri=True)
        conn.execute("SELECT count(*) FROM access LIMIT 1")
        conn.close()
        return True
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        return False


def audit_privacy() -> list[PermissionEntry]:
    """Read the user TCC database and return all non-default permission entries."""
    if not TCC_DB.exists():
        return []

    try:
        conn = sqlite3.connect(f"file:{TCC_DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        # Column names vary slightly across macOS versions; we handle both
        try:
            rows = conn.execute(
                "SELECT service, client, auth_value, last_modified FROM access"
            ).fetchall()
        except sqlite3.OperationalError:
            # Older schema (pre-Ventura) uses 'allowed' instead of 'auth_value'
            rows = conn.execute(
                "SELECT service, client, allowed, last_modified FROM access"
            ).fetchall()
        conn.close()
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        return []

    entries: list[PermissionEntry] = []
    for row in rows:
        service = row[0] or ""
        bundle_id = row[1] or ""
        # auth_value: 0=denied, 2=allowed; older 'allowed': 0=denied, 1=allowed
        raw_allowed = row[2]
        allowed = raw_allowed in (1, 2)
        raw_mtime = row[3]

        last_modified: str | None = None
        if raw_mtime:
            try:
                # TCC stores seconds since 2001-01-01 (Mac absolute time)
                mac_epoch_offset = 978307200
                last_modified = datetime.utcfromtimestamp(int(raw_mtime) + mac_epoch_offset).strftime("%Y-%m-%d")
            except (ValueError, OSError):
                last_modified = str(raw_mtime)

        app_name = bundle_id.split(".")[-1].title() if bundle_id else bundle_id
        service_display = SERVICE_NAMES.get(service, service)

        entries.append(PermissionEntry(
            service=service,
            service_display=service_display,
            bundle_id=bundle_id,
            app_name=app_name,
            allowed=allowed,
            last_modified=last_modified,
        ))

    return sorted(entries, key=lambda e: (e.service_display, e.bundle_id))


def render_privacy_text(entries: list[PermissionEntry]) -> str:
    if not entries:
        return "No TCC permission entries found."

    lines: list[str] = []
    current_service = ""
    for entry in entries:
        if entry.service_display != current_service:
            if lines:
                lines.append("")
            lines.append(entry.service_display)
            lines.append("  " + "-" * len(entry.service_display))
            current_service = entry.service_display
        state = "✓ allowed" if entry.allowed else "✗ denied "
        mtime = entry.last_modified or "unknown date"
        lines.append(f"  {state}  {entry.app_name:<28} {entry.bundle_id:<45} {mtime}")

    return "\n".join(lines)
