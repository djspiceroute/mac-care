from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import tomllib


DEFAULT_PROTECTED_PATHS = [
    "~/.codex",
    "~/.agents",
    "~/multica",
    "~/multica_workspaces",
    "~/.vscode/extensions",
    "~/Library/Application Support/Google/Chrome/NativeMessagingHosts",
    "~/Library/Application Support/Mozilla/NativeMessagingHosts",
]


@dataclass(frozen=True)
class Config:
    reports_dir: Path = Path("~/Documents/MacCare/reports")
    quarantine_dir: Path = Path("~/Documents/MacCare/quarantine")
    min_age_days: int = 14
    protected_paths: list[Path] = field(default_factory=list)

    @staticmethod
    def load(config_path: str | None = None) -> "Config":
        path = Path(config_path).expanduser() if config_path else Path("~/.config/mac-care/config.toml").expanduser()
        data: dict = {}
        if path.exists():
            with path.open("rb") as handle:
                data = tomllib.load(handle)

        policy = data.get("policy", {})
        protected = policy.get("protected_paths", DEFAULT_PROTECTED_PATHS)
        return Config(
            reports_dir=Path(policy.get("reports_dir", "~/Documents/MacCare/reports")).expanduser(),
            quarantine_dir=Path(policy.get("quarantine_dir", "~/Documents/MacCare/quarantine")).expanduser(),
            min_age_days=int(policy.get("min_age_days", 14)),
            protected_paths=[Path(os.path.expanduser(item)) for item in protected],
        )

    def ensure_dirs(self) -> None:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
