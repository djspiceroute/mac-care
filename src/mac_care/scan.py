from __future__ import annotations

from pathlib import Path
import time

from .config import Config
from .git_safety import unsafe_repos
from .model import Finding, path_size
from .tools.brew import brew_cleanup_findings
from .tools.disk import size_of, top_subdirs_summary
from .tools.docker_check import docker_findings
from .tools.pearcleaner import pearcleaner_findings

# Directories larger than this get a top-subdirs breakdown appended to reason.
_BREAKDOWN_THRESHOLD_BYTES = 500 * 1024 * 1024  # 500 MB


def scan(config: Config) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(_standard_paths(config))
    findings.extend(_developer_paths(config))
    findings.extend(_downloads_review(config))
    findings.extend(_codex_workspace_review(config))
    findings.extend(brew_cleanup_findings())
    findings.extend(docker_findings())
    findings.extend(pearcleaner_findings())
    return [item for item in findings if item.size_bytes > 0 or item.risk == "review"]


def _standard_paths(config: Config) -> list[Finding]:
    home = Path.home()
    candidates = [
        ("user_logs", home / "Library/Logs", "old user logs are usually safe after review window"),
        ("user_caches", home / "Library/Caches", "cache cleanup should be age-filtered before execution"),
        ("trash", home / ".Trash", "trash can be auto-cleaned when old enough"),
        ("tmp", Path("/tmp"), "temporary files should be age-filtered before execution"),
    ]
    return [_finding(category, path, "auto_safe", reason, config) for category, path, reason in candidates]


def _developer_paths(config: Config) -> list[Finding]:
    home = Path.home()
    candidates = [
        ("xcode_derived_data", home / "Library/Developer/Xcode/DerivedData", "rebuildable Xcode artifacts"),
        ("xcode_archives", home / "Library/Developer/Xcode/Archives", "review archives before deleting"),
        ("android_gradle_cache", home / ".gradle/caches", "Gradle cache cleanup should be conservative"),
        # homebrew_cache removed: brew_cleanup_findings() in scan() provides
        # richer, item-level findings directly from `brew cleanup --dry-run`
    ]
    findings: list[Finding] = []
    for category, path, reason in candidates:
        risk = "review" if category in {"xcode_archives", "android_gradle_cache"} else "auto_safe"
        findings.append(_finding(category, path, risk, reason, config))
    return findings


def _downloads_review(config: Config) -> list[Finding]:
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        return []
    total = 0
    cutoff = time.time() - (config.min_age_days * 86400)
    for child in downloads.iterdir():
        try:
            if child.is_file() and child.suffix.lower() in {".dmg", ".pkg", ".zip", ".tar", ".gz"} and child.stat().st_mtime < cutoff:
                total += child.stat().st_size
        except OSError:
            continue
    return [Finding("old_installers", str(downloads), total, "review", f"installers older than {config.min_age_days} days")]


def _codex_workspace_review(config: Config) -> list[Finding]:
    codex_docs = Path.home() / "Documents/Codex"
    if not codex_docs.exists():
        return []

    dirty = unsafe_repos(codex_docs)
    if dirty:
        repo_list = ", ".join(str(r) for r in dirty[:3])
        suffix = f" and {len(dirty) - 3} more" if len(dirty) > 3 else ""
        reason = f"active/dirty git repos detected — cannot auto-clean: {repo_list}{suffix}"
        risk: str = "protected"
    else:
        reason = "old agent workspaces can be large; active work must be checked before deletion"
        risk = "review"

    total = size_of(codex_docs)
    if total >= _BREAKDOWN_THRESHOLD_BYTES and risk != "protected":
        summary = top_subdirs_summary(codex_docs)
        if summary:
            reason = f"{reason}; {summary}"

    return [Finding("codex_workspaces", str(codex_docs), total, risk, reason)]  # type: ignore[arg-type]


def _finding(category: str, path: Path, risk: str, reason: str, config: Config) -> Finding:
    resolved = path.expanduser()
    if _is_protected(resolved, config):
        risk = "protected"

    total = size_of(resolved)

    # Enrich reason with top-subdirs breakdown for large directories
    if total >= _BREAKDOWN_THRESHOLD_BYTES and risk != "protected":
        summary = top_subdirs_summary(resolved)
        if summary:
            reason = f"{reason}; {summary}"

    return Finding(category, str(resolved), total, risk, reason)  # type: ignore[arg-type]


def _is_protected(path: Path, config: Config) -> bool:
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
    return False
