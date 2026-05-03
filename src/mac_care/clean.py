from __future__ import annotations

from .model import Finding


def safe_clean(findings: list[Finding], dry_run: bool = True) -> list[str]:
    actions: list[str] = []
    for finding in findings:
        if finding.risk != "auto_safe":
            continue
        if dry_run:
            actions.append(f"would clean {finding.category}: {finding.path}")
        else:
            actions.append(f"skipped execution for {finding.category}: deletion policies are not implemented yet")
    return actions
