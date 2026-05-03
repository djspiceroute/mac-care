from __future__ import annotations

from pathlib import Path
from shutil import which
import subprocess
import time

from .config import Config
from .git_safety import unsafe_repos
from .model import Finding, path_size
from .safety import is_protected
from .tools.brew import brew_cleanup_findings
from .tools.disk import size_of, top_subdirs_summary
from .tools.docker_check import docker_findings
from .tools.pearcleaner import pearcleaner_findings
from .tools.xcode import xcode_findings

# Directories larger than this get a top-subdirs breakdown appended to reason.
_BREAKDOWN_THRESHOLD_BYTES = 500 * 1024 * 1024  # 500 MB


def scan(config: Config) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(_standard_paths(config))
    findings.extend(_developer_paths(config))
    findings.extend(_downloads_review(config))
    findings.extend(_workspace_review(Path.home() / "Documents/Codex", config))
    for extra in config.additional_scan_paths:
        findings.extend(_workspace_review(extra.expanduser(), config))
    findings.extend(_ios_backups(config))
    findings.extend(_messages_attachments(config))
    findings.extend(_time_machine_snapshots())
    findings.extend(_core_dumps_and_crash_logs(config))
    findings.extend(_broken_symlinks())
    findings.extend(_login_items())
    findings.extend(_stale_runtime_versions(config))
    findings.extend(_orphaned_dotdirs())
    findings.extend(_ai_tool_caches(config))
    findings.extend(brew_cleanup_findings())
    findings.extend(docker_findings())
    findings.extend(pearcleaner_findings())
    findings.extend(xcode_findings())
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
    age_days = config.min_age_days_for("old_installers")
    total = 0
    cutoff = time.time() - (age_days * 86400)
    for child in downloads.iterdir():
        try:
            if child.is_file() and child.suffix.lower() in {".dmg", ".pkg", ".zip", ".tar", ".gz"} and child.stat().st_mtime < cutoff:
                total += child.stat().st_size
        except OSError:
            continue
    return [Finding("old_installers", str(downloads), total, "review", f"installers older than {age_days} days")]


def _workspace_review(workspace_path: Path, config: Config) -> list[Finding]:
    if not workspace_path.exists():
        return []

    if is_protected(workspace_path, config):
        total = size_of(workspace_path)
        return [Finding("codex_workspaces", str(workspace_path), total, "protected", "path is in protected list")]  # type: ignore[arg-type]

    dirty = unsafe_repos(workspace_path)
    if dirty:
        repo_list = ", ".join(str(r) for r in dirty[:3])
        suffix = f" and {len(dirty) - 3} more" if len(dirty) > 3 else ""
        reason = f"active/dirty git repos detected — cannot auto-clean: {repo_list}{suffix}"
        risk: str = "protected"
    else:
        reason = "old agent workspaces can be large; active work must be checked before deletion"
        risk = "review"

    total = size_of(workspace_path)
    if total >= _BREAKDOWN_THRESHOLD_BYTES and risk != "protected":
        summary = top_subdirs_summary(workspace_path)
        if summary:
            reason = f"{reason}; {summary}"

    return [Finding("codex_workspaces", str(workspace_path), total, risk, reason)]  # type: ignore[arg-type]


def _ios_backups(config: Config) -> list[Finding]:
    backup_dir = Path.home() / "Library/Application Support/MobileSync/Backup"
    if not backup_dir.exists():
        return []
    total = size_of(backup_dir)
    if total < 500 * 1024 * 1024:
        return []
    summary = top_subdirs_summary(backup_dir)
    reason = "iOS device backups — review before removing; keep at least one recent backup"
    if summary:
        reason = f"{reason}; {summary}"
    return [Finding("ios_backups", str(backup_dir), total, "review", reason)]  # type: ignore[arg-type]


def _messages_attachments(config: Config) -> list[Finding]:
    attachments_dir = Path.home() / "Library/Messages/Attachments"
    if not attachments_dir.exists():
        return []
    total = size_of(attachments_dir)
    return [Finding(
        "messages_attachments",
        str(attachments_dir),
        total,
        "review",
        "iMessage attachments accumulate over years — personal data, manual cleanup only",
    )]  # type: ignore[arg-type]


def _time_machine_snapshots() -> list[Finding]:
    if not which("tmutil"):
        return []
    try:
        result = subprocess.run(
            ["tmutil", "listlocalsnapshots", "/"],
            check=False, capture_output=True, text=True, timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip().startswith("com.apple.TimeMachine")]
    if not lines:
        return []
    reason = f"{len(lines)} local snapshot(s) on boot volume — macOS manages purgeable space automatically"
    # We report size as 0 because tmutil doesn't expose exact snapshot sizes without sudo.
    # The finding is informational (risk: review) so size_bytes=0 is kept by the filter above.
    return [Finding("time_machine_snapshots", "/", 0, "review", reason)]  # type: ignore[arg-type]


def _core_dumps_and_crash_logs(config: Config) -> list[Finding]:
    findings: list[Finding] = []
    home = Path.home()

    cores_dir = Path("/cores")
    if cores_dir.exists():
        total = size_of(cores_dir)
        if total > 0:
            findings.append(Finding(
                "core_dumps", str(cores_dir), total, "auto_safe",
                "kernel core dumps — safe to delete, regenerated on next crash",
            ))  # type: ignore[arg-type]

    for category, path, reason in [
        ("xcode_crash_reports", home / "Library/Diagnostics",
         "Xcode crash reports — review before deleting if actively debugging"),
        ("diagnostic_reports", home / "Library/Logs/DiagnosticReports",
         "stale Apple crash logs — usually safe after review"),
    ]:
        findings.append(_finding(category, path, "review", reason, config))

    return findings


def _broken_symlinks() -> list[Finding]:
    home = Path.home()
    # Directories to skip — too broad, too risky, or contain intentional broken links.
    skip_prefixes = {
        home / ".Trash",
        home / "Library",
        home / ".git",
    }
    broken: list[Path] = []
    try:
        for item in home.iterdir():
            if any(item == s or s in item.parents for s in skip_prefixes):
                continue
            try:
                _walk_for_broken_symlinks(item, broken)
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        return []

    if not broken:
        return []

    paths_preview = ", ".join(str(p) for p in broken[:3])
    suffix = f" and {len(broken) - 3} more" if len(broken) > 3 else ""
    reason = f"{len(broken)} broken symlink(s): {paths_preview}{suffix}"
    # Report as a single finding pointing to home; path is informational.
    return [Finding("broken_symlinks", str(home), 0, "review", reason)]  # type: ignore[arg-type]


def _walk_for_broken_symlinks(path: Path, broken: list[Path], depth: int = 0) -> None:
    if depth > 5:
        return
    if path.is_symlink():
        if not path.exists():
            broken.append(path)
        return
    if path.is_dir():
        try:
            for child in path.iterdir():
                _walk_for_broken_symlinks(child, broken, depth + 1)
        except (PermissionError, OSError):
            pass


def _login_items() -> list[Finding]:
    script = 'tell application "System Events" to get the name of every login item'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False, capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    items = [item.strip() for item in result.stdout.strip().split(",") if item.strip()]
    if not items:
        return []
    reason = f"{len(items)} login item(s): {', '.join(items)}"
    return [Finding("login_items", str(Path.home()), 0, "review", reason)]  # type: ignore[arg-type]


def _stale_runtime_versions(config: Config) -> list[Finding]:
    """Surface old language runtime versions installed via version managers (#31)."""
    home = Path.home()
    age_days = config.min_age_days_for("stale_runtimes")
    cutoff = time.time() - (age_days * 86400)
    findings: list[Finding] = []

    version_dirs: list[tuple[str, Path]] = [
        ("nvm", home / ".nvm/versions"),
        ("fnm", home / ".fnm/node-versions"),
        ("pyenv", home / ".pyenv/versions"),
        ("rbenv", home / ".rbenv/versions"),
        ("rustup", home / ".rustup/toolchains"),
    ]

    # Detect duplicate managers per language
    node_managers = [m for m, p in version_dirs[:2] if (home / f".{m}").exists()]
    py_managers = ["pyenv"] if (home / ".pyenv").exists() else []
    rb_managers = ["rbenv"] if (home / ".rbenv").exists() else []

    for managers, lang in [(node_managers, "node"), (py_managers, "python"), (rb_managers, "ruby")]:
        if len(managers) > 1:
            findings.append(Finding(
                "duplicate_version_managers",
                str(home),
                0,
                "review",
                f"{lang}: multiple version managers detected ({', '.join(managers)}) — pick one to avoid PATH conflicts",
            ))  # type: ignore[arg-type]

    for manager, versions_path in version_dirs:
        if not versions_path.exists():
            continue
        stale: list[str] = []
        for version_dir in versions_path.iterdir():
            if not version_dir.is_dir():
                continue
            try:
                mtime = version_dir.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                stale.append(version_dir.name)
        if stale:
            total = size_of(versions_path)
            findings.append(Finding(
                "stale_runtimes",
                str(versions_path),
                total,
                "review",
                f"{manager}: {len(stale)} version(s) unused for >{age_days} days: {', '.join(sorted(stale)[:5])}",
            ))  # type: ignore[arg-type]

    return findings


# Known CLI tools and the dotdir they leave behind.
_ORPHAN_DOTDIR_CANDIDATES: list[tuple[str, str]] = [
    ("nvm", ".nvm"),
    ("rvm", ".rvm"),
    ("rbenv", ".rbenv"),
    ("pyenv", ".pyenv"),
    ("asdf", ".asdf"),
    ("fnm", ".fnm"),
    ("nodenv", ".nodenv"),
    ("plenv", ".plenv"),
    ("phpenv", ".phpenv"),
    ("jenv", ".jenv"),
    ("sdkman", ".sdkman"),
    ("pnpm", ".pnpm-store"),
    ("poetry", ".poetry"),
    ("pipenv", ".local/share/virtualenvs"),
]


def _orphaned_dotdirs() -> list[Finding]:
    """Flag dotdirs belonging to CLI tools no longer on PATH (#38)."""
    home = Path.home()
    findings: list[Finding] = []
    for tool, dotdir in _ORPHAN_DOTDIR_CANDIDATES:
        dir_path = home / dotdir
        if not dir_path.exists():
            continue
        if which(tool) is not None:
            continue  # tool still active
        total = size_of(dir_path)
        findings.append(Finding(
            "orphan_dotdir",
            str(dir_path),
            total,
            "review",
            f"{tool} is no longer on PATH but {dotdir} still exists — may be intentional if tool was deactivated",
        ))  # type: ignore[arg-type]
    return findings


# AI and modern dev tool cache directories (#39).
_AI_TOOL_CACHES: list[tuple[str, str]] = [
    ("cursor_cache", "Library/Application Support/Cursor/Cache"),
    ("cursor_gpu_cache", "Library/Application Support/Cursor/GPUCache"),
    ("claude_cache", "Library/Application Support/Claude/Cache"),
    ("claude_gpu_cache", "Library/Application Support/Claude/GPUCache"),
    ("playwright_cache", "Library/Caches/ms-playwright"),
    ("codex_runtime_cache", "Library/Caches/codex"),
]


def _ai_tool_caches(config: Config) -> list[Finding]:
    """Surface AI tool and modern dev cache directories (#39)."""
    home = Path.home()
    findings: list[Finding] = []
    for category, rel_path in _AI_TOOL_CACHES:
        path = home / rel_path
        if not path.exists():
            continue
        findings.append(_finding(category, path, "auto_safe", f"AI/dev tool cache — safe to clear", config))
    return findings


def _finding(category: str, path: Path, risk: str, reason: str, config: Config) -> Finding:
    resolved = path.expanduser()
    if is_protected(resolved, config):
        risk = "protected"

    total = size_of(resolved)

    # Enrich reason with top-subdirs breakdown for large directories
    if total >= _BREAKDOWN_THRESHOLD_BYTES and risk != "protected":
        summary = top_subdirs_summary(resolved)
        if summary:
            reason = f"{reason}; {summary}"

    return Finding(category, str(resolved), total, risk, reason)  # type: ignore[arg-type]


