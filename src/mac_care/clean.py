from __future__ import annotations

from datetime import datetime

from .actions import preview_clean_action, purge_action, quarantine_action
from .config import Config
from .model import Finding


def safe_clean(
    findings: list[Finding],
    config: Config | None = None,
    dry_run: bool = True,
    purge: bool = False,
) -> list[str]:
    actions: list[str] = []
    run_id = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    for finding in findings:
        if finding.risk != "auto_safe":
            continue

        if dry_run:
            actions.append(preview_clean_action(finding, config).render())
            continue

        if purge:
            actions.append(purge_action(finding, config).render())
            continue

        if config is None:
            actions.append(
                f"skipped execution for {finding.category}: config is required for quarantine"
            )
            continue

        actions.append(quarantine_action(finding, config, run_id=run_id).render())
    return actions


def _purge_finding(finding: Finding) -> str:
    return purge_action(finding).render()


def quarantine_finding(finding: Finding, config: Config, run_id: str | None = None) -> str:
    return quarantine_action(finding, config, run_id=run_id).render()
