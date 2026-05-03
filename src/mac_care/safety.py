from __future__ import annotations

from pathlib import Path

from .config import Config


def is_protected(path: Path, config: Config) -> bool:
    """Return True if path is under any configured protected path or the quarantine dir."""
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path

    for protected in config.protected_paths:
        try:
            protected_resolved = protected.resolve()
        except OSError:
            protected_resolved = protected
        if resolved == protected_resolved or protected_resolved in resolved.parents:
            return True

    quarantine = config.quarantine_dir.expanduser()
    try:
        quarantine_resolved = quarantine.resolve()
    except OSError:
        quarantine_resolved = quarantine
    return resolved == quarantine_resolved or quarantine_resolved in resolved.parents
