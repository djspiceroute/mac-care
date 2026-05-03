"""
tools/xcode.py — Xcode simulator and device support cleanup findings.

Identifies:
- Unavailable simulators (isAvailable = false)
- Xcode DeviceSupport folders
- Simulator runtimes and caches
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from shutil import which

from ..model import Finding
from .disk import size_of


def xcode_findings() -> list[Finding]:
    """Aggregate all Xcode-related developer findings beyond DerivedData/Archives."""
    if not which("xcrun"):
        return []

    findings: list[Finding] = []
    findings.extend(_unavailable_simulators())
    findings.extend(_device_support())
    findings.extend(_simulator_runtimes_and_caches())
    return findings


def _unavailable_simulators() -> list[Finding]:
    """Identify simulator device data for unavailable simulators.

    Suggests: xcrun simctl delete unavailable
    """
    try:
        result = subprocess.run(
            ["xcrun", "simctl", "list", "--json", "devices"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
        return []

    devices_by_runtime = data.get("devices", {})
    findings: list[Finding] = []

    for runtime_id, devices in devices_by_runtime.items():
        for device in devices:
            if device.get("isAvailable") is False:
                udid = device.get("udid")
                name = device.get("name", "Unknown")
                # Attempt to find dataPath. Some simctl versions provide it.
                data_path_str = device.get("dataPath")
                if not data_path_str:
                    # Fallback: check default location
                    fallback_path = Path.home() / f"Library/Developer/CoreSimulator/Devices/{udid}"
                    if fallback_path.exists():
                        data_path_str = str(fallback_path)

                if data_path_str:
                    path = Path(data_path_str)
                    size = size_of(path)
                    findings.append(Finding(
                        category="xcode_unavailable_simulator",
                        path=str(path),
                        size_bytes=size,
                        risk="review",
                        reason=f"unavailable simulator '{name}' ({runtime_id}) — run `xcrun simctl delete unavailable` to clean up safely",
                    ))

    return findings


def _device_support() -> list[Finding]:
    """Surface iOS/watchOS/tvOS DeviceSupport folders."""
    home = Path.home()
    xcode_dir = home / "Library/Developer/Xcode"
    if not xcode_dir.exists():
        return []

    findings: list[Finding] = []
    # Known DeviceSupport folders
    targets = [
        "iOS DeviceSupport",
        "watchOS DeviceSupport",
        "tvOS DeviceSupport",
    ]

    for target in targets:
        path = xcode_dir / target
        if path.exists():
            size = size_of(path)
            if size > 0:
                findings.append(Finding(
                    category="xcode_device_support",
                    path=str(path),
                    size_bytes=size,
                    risk="review",
                    reason=f"Xcode {target} — symbols for on-device debugging; safe to remove if those OS versions aren't being debugged",
                ))

    return findings


def _simulator_runtimes_and_caches() -> list[Finding]:
    """Identify simulator runtimes and developer caches."""
    home = Path.home()
    core_sim_dir = home / "Library/Developer/CoreSimulator"
    if not core_sim_dir.exists():
        return []

    findings: list[Finding] = []

    # Runtimes are usually in ~/Library/Developer/CoreSimulator/Volumes or similar in older versions,
    # but in modern macOS they are often in /Library/Developer/CoreSimulator/Profiles/Runtimes
    # or ~/Library/Developer/CoreSimulator/Profiles/Runtimes.
    # We check the most common user-level ones.
    runtime_paths = [
        core_sim_dir / "Profiles/Runtimes",
        core_sim_dir / "Caches",
    ]

    for path in runtime_paths:
        if path.exists():
            size = size_of(path)
            if size > 0:
                findings.append(Finding(
                    category="xcode_simulator_artifacts",
                    path=str(path),
                    size_bytes=size,
                    risk="review",
                    reason=f"Simulator {path.name} — can be large; review before removing",
                ))

    return findings
