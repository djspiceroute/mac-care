# mac-care Architecture

## Design Philosophy

mac-care is an **orchestrator, not a scanner**. It calls trusted OSS tools, parses their output into a unified data model, and applies a policy layer on top. The custom code handles: policy, scheduling, protected paths, review gates, report formatting, and developer tool health. The OSS tools handle: actual disk analysis, package cache detection, container waste detection, and app leftover scanning.

This means:
- When the report says "brew can reclaim 109 MB", that's because `brew cleanup --dry-run` said so — not because we reimplemented brew's logic.
- When a Docker finding appears, `docker system df` is the source of truth.
- Our code stays small and focused on coordination.

---

## Data Flow

```
mac-care scan
     │
     ├── _standard_paths()        → native findings (logs, caches, trash, tmp)
     ├── _developer_paths()       → native findings (Xcode, Gradle)
     ├── _downloads_review()      → native findings (old installers)
     ├── _codex_workspace_review() → native + git_safety gate
     ├── brew_cleanup_findings()  → calls brew cleanup --dry-run
     ├── docker_findings()        → calls docker system df
     └── pearcleaner_findings()   → calls pearcleaner list-orphaned
              │
              ▼
        list[Finding]
              │
     ┌────────┴────────┐
     │                 │
 write_reports()    safe_clean()
 (Markdown+JSON)   (dry-run only, re-checks git_safety)
```

---

## Module Boundaries

### `model.py`
Pure data types. No I/O, no subprocess calls. Importing this never has side effects.

```python
Finding(category, path, size_bytes, risk, reason, source)
ToolStatus(name, status, detail)
format_bytes(size) -> str
path_size(path) -> int   # slow Python fallback — prefer tools/disk.py
```

`source` field values: `"native"` | `"brew"` | `"dua"` | `"docker"` | `"pearcleaner"`

`risk` field values: `"auto_safe"` | `"review"` | `"protected"`

### `scan.py`
The main orchestrator. Calls all scanner functions and returns `list[Finding]`. No deletion logic here. Applies the git safety gate to workspace paths. Uses `size_of()` from `tools/disk.py` instead of the slow Python rglob for directory sizing.

**Rule:** `scan.py` must never delete or modify files. It is read-only.

### `clean.py`
Acts on `auto_safe` findings only. Re-checks the git safety gate before touching workspace-adjacent categories (belt-and-suspenders). Deletion is not implemented yet — `--dry-run` is the only operative mode. When deletion is added, it must move files to `config.quarantine_dir`, never `rm`.

**Rule:** Only `auto_safe` risk findings are eligible. `review` and `protected` are never touched.

### `doctor.py`
Checks required developer tools (`REQUIRED_TOOLS`), optional OSS integrations (`OSS_OPTIONAL_TOOLS`), Homebrew PATH, and Docker daemon reachability. `recommend_tools()` returns missing optional tools with install hints from `TOOL_RECOMMENDATIONS`.

### `git_safety.py`
Detects dirty or active git repos under a path. Used by `scan.py` (to mark Codex workspaces as `protected`) and `clean.py` (to re-check before acting). All subprocess calls fail-safe — timeouts and missing `git` binary both return `True` (treat as dirty/active).

```python
find_git_repos(root, max_depth=4) -> list[Path]
is_dirty(repo_path) -> bool
has_active_worktrees(repo_path) -> bool
unsafe_repos(root) -> list[Path]
```

### `config.py`
Loads `~/.config/mac-care/config.toml` with fallback to hardcoded defaults. Returns a frozen `Config` dataclass. The only file that reads from disk at import time (via `Config.load()`).

### `report.py`
Writes Markdown + JSON reports to `config.reports_dir`. Reports are timestamped and never overwritten. The Markdown groups findings by risk level with size totals.

### `scheduler.py` *(planned)*
Will write/remove a launchd plist at `~/Library/LaunchAgents/com.mac-care.periodic.plist` that runs `mac-care scan` on a configurable interval. Must support `--dry-run` to print the plist without writing it.

---

## tools/ — OSS Wrappers

Every file in `tools/` follows the same contract:

1. **Check if the tool is installed** (`shutil.which`) before calling subprocess
2. **Return `[]` on any failure** — timeout, missing binary, parse error, daemon offline
3. **Never raise** — degradation is always silent and logged implicitly via empty return
4. **No inline subprocess calls outside `tools/`** — all subprocess lives here
5. **Independently testable** — mock `subprocess.run` and `shutil.which`, never call real tools in tests

### `tools/brew.py`

Runs `HOMEBREW_NO_AUTO_UPDATE=1 brew cleanup --dry-run`.

Output format:
```
Would remove: /path/to/file (3.4MB)
Would remove: /path/to/dir (96 files, 2.7MB)
Would remove (broken link): /path/to/symlink
Would remove (empty directory): /path/to/dir
==> This operation would free approximately 109.2MB of disk space.
```

Parses each `Would remove:` line with a regex. Size is extracted from the parenthetical. Summary line is ignored. All findings are `auto_safe` — brew itself determines what is safe.

### `tools/disk.py`

Three-tier size analysis:

1. **`dua aggregate -f bytes <children...>`** — fast parallel, ANSI output stripped by regex
2. **`du -d 1 -k <path>`** — macOS built-in, always available, kilobytes
3. **`path_size()` from `model.py`** — pure Python rglob, slowest, last resort

Children are expanded via `path.iterdir()` in Python before passing to dua (shell glob does not expand in `subprocess.run` list form).

Output format (dua, after ANSI stripping):
```
  27406336 b  /path/to/subdir
   8941568 b  /path/to/other
  36347904 b  total
```

Public API: `size_of(path)`, `top_subdirs(path, n=5)`, `top_subdirs_summary(path, n=5)`.
`top_subdirs_summary` returns a human-readable string like `"largest: Google (1.3 GB), ms-playwright (1.0 GB)"` for appending to `Finding.reason`.

### `tools/docker_check.py`

Runs `docker system df --format '{{json .}}'`.

Output format (one JSON object per line):
```json
{"Active":"10","Reclaimable":"9.789GB (49%)","Size":"19.7GB","TotalCount":"52","Type":"Images"}
```

Categories: `Images`, `Containers`, `Local Volumes`, `Build Cache` → mapped to mac-care categories `docker_images`, `docker_containers`, `docker_volumes`, `docker_build_cache`.

`size_bytes` is set to reclaimable bytes (not total). Findings with zero reclaimable are skipped. All Docker findings are `review` risk — never auto-cleaned.

Checks daemon reachability via `docker info` before calling `docker system df`.

### `tools/pearcleaner.py`

Runs `pearcleaner list-orphaned`. Binary found via `which("pearcleaner")` or known app paths (`/Applications/Pearcleaner.app/Contents/MacOS/Pearcleaner`).

CLI source verified from [alienator88/Pearcleaner — Logic/CLI.swift](https://github.com/alienator88/Pearcleaner/blob/main/Pearcleaner/Logic/CLI.swift). Subcommand is `list-orphaned`, output is one path per line, ends with `"Found N orphaned files."`.

All findings are `review` risk — never auto-cleaned.

Live validation note: Pearcleaner 5.4.3 installed via Homebrew cask and `pearcleaner --help` confirms the `list-orphaned` subcommand. On this machine, `pearcleaner list-orphaned` did not return within 60 seconds, so the wrapper timeout is part of the safety contract and should remain fail-closed to `[]`.

---

## Report Structure

### JSON report

```json
{
  "generated_at": "2026-05-02T21:08:26",
  "findings": [
    {
      "category": "brew_cache",
      "path": "/opt/homebrew/Cellar/xz/5.8.2",
      "size_bytes": 2700000,
      "risk": "auto_safe",
      "reason": "brew cleanup: safe to remove",
      "source": "brew"
    }
  ],
  "tools": [
    {
      "name": "brew",
      "status": "ok",
      "detail": "/opt/homebrew/bin/brew"
    }
  ]
}
```

### Markdown report

Grouped by risk level (`auto_safe` → `review` → `protected`), each group shows total size and a table sorted descending by size. Doctor section appended at the end.

---

## Safety Invariants

These must hold at all times. Tests should catch regressions.

1. `scan()` never modifies or deletes files.
2. `safe_clean()` only acts on `risk == "auto_safe"` findings.
3. Protected paths are checked in both `scan.py` (`_is_protected`) and `clean.py` (git safety re-check).
4. Git safety gate returns `True` (unsafe) on any subprocess failure — never silently clears a repo.
5. Every `tools/` wrapper returns `[]` on any error — never propagates exceptions to the caller.
6. `dry_run=True` is the default for `safe_clean()`. Callers must explicitly pass `dry_run=False` to act.
7. Deletion (when implemented) moves to `quarantine_dir`, never `rm`.
