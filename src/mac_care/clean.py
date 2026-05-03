from __future__ import annotations

from pathlib import Path

from .git_safety import unsafe_repos
from .model import Finding

# Categories whose paths may contain git repos — always re-check before acting.
_WORKSPACE_CATEGORIES = {"codex_workspaces"}


def safe_clean(findings: list[Finding], dry_run: bool = True) -> list[str]:
    actions: list[str] = []
    for finding in findings:
        if finding.risk != "auto_safe":
            continue

        # Re-run git safety gate for workspace-adjacent categories even if
        # scan already marked them auto_safe (belt-and-suspenders guard).
        if finding.category in _WORKSPACE_CATEGORIES:
            dirty = unsafe_repos(Path(finding.path))
            if dirty:
                actions.append(
                    f"skipped {finding.category}: unsafe git repos detected at scan time — "
                    f"{', '.join(str(r) for r in dirty[:2])}"
                )
                continue

        if dry_run:
            actions.append(f"would clean {finding.category}: {finding.path}")
        else:
            actions.append(
                f"skipped execution for {finding.category}: deletion policies are not implemented yet"
            )
    return actions
