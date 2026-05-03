from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import tomllib


DEFAULT_PROTECTED_PATHS = [
    "~/.codex",
    "~/.ssh",
    "~/.vscode/extensions",
    "~/Library/Application Support/Google/Chrome/NativeMessagingHosts",
    "~/Library/Application Support/Mozilla/NativeMessagingHosts",
]


@dataclass(frozen=True)
class Config:
    reports_dir: Path = Path("~/.mac-care/reports")
    quarantine_dir: Path = Path("~/.mac-care/quarantine")
    min_age_days: int = 14
    protected_paths: list[Path] = field(default_factory=list)
    additional_scan_paths: list[Path] = field(default_factory=list)
    # Per-category overrides: {category: {min_age_days: int, ...}}
    category_policy: dict[str, dict] = field(default_factory=dict)

    def min_age_days_for(self, category: str) -> int:
        """Return the effective min_age_days for a given category."""
        return int(self.category_policy.get(category, {}).get("min_age_days", self.min_age_days))

    @staticmethod
    def load(config_path: str | None = None) -> "Config":
        path = Path(config_path).expanduser() if config_path else Path("~/.config/mac-care/config.toml").expanduser()
        data: dict = {}
        if path.exists():
            with path.open("rb") as handle:
                data = tomllib.load(handle)

        policy = data.get("policy", {})
        protected = policy.get("protected_paths", DEFAULT_PROTECTED_PATHS)
        additional = policy.get("additional_scan_paths", [])

        # Collect [policy.<category>] subsections as per-category overrides
        category_policy: dict[str, dict] = {}
        for key, value in data.items():
            if key != "policy" and isinstance(value, dict):
                # Top-level tables like [downloads] map to category overrides
                category_policy[key] = value
        # Also support [policy.downloads] nested style
        for key, value in policy.items():
            if isinstance(value, dict):
                category_policy[key] = value

        return Config(
            reports_dir=Path(policy.get("reports_dir", "~/.mac-care/reports")).expanduser(),
            quarantine_dir=Path(policy.get("quarantine_dir", "~/.mac-care/quarantine")).expanduser(),
            min_age_days=int(policy.get("min_age_days", 14)),
            protected_paths=[Path(os.path.expanduser(item)) for item in protected],
            additional_scan_paths=[Path(os.path.expanduser(item)) for item in additional],
            category_policy=category_policy,
        )

    def ensure_dirs(self) -> None:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
