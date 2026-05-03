# mac-care Technical Spec

## Goal

Replace the practical operational value of CleanMyMac for a developer machine with a free, local, report-first CLI tool. No polished UI clone. No surprise deletions. Integrate good OSS tools rather than rebuilding commodity scanners.

Repo: https://github.com/djspiceroute/mac-care  
Stack: Python 3.11+, stdlib only (no pip runtime deps)

---

## Feature Status

### ✅ Shipped

| Feature | Command | Notes |
|---|---|---|
| Disk scan — standard paths | `mac-care scan` | Logs, caches, trash, tmp |
| Disk scan — developer paths | `mac-care scan` | Xcode DerivedData, Gradle cache |
| Disk scan — old installers | `mac-care scan` | Downloads: .dmg/.pkg/.zip older than `min_age_days` |
| Codex workspace scan | `mac-care scan` | Marks as `protected` if any dirty/active git repos found |
| Homebrew cache scan | `mac-care scan` | Via `brew cleanup --dry-run` — per-item, `auto_safe` |
| Docker disk usage | `mac-care scan` | Via `docker system df` — reclaimable per category, `review` |
| Orphaned app files | `mac-care scan` | Via `pearcleaner list-orphaned`, `review` (if installed) |
| Disk tree analysis | `scan` internals | Via `dua` → `du` → Python fallback; top-subdir breakdown >500 MB |
| Git/worktree safety gate | `scan` + `clean` | `git_safety.py`: dirty/active repo detection before any action |
| Developer tool health | `mac-care doctor` | Required tools, Homebrew PATH, Docker daemon |
| Tool status | `mac-care tools status` | Required + optional tools installed/missing |
| Tool recommendations | `mac-care tools recommend` | Missing OSS tools with `brew install` hints, grouped |
| Compact scan summary | `mac-care scan` | Counts and sizes by risk, top findings, tool warning count |
| Scan output flags | `mac-care scan --stdout` | Print JSON or Markdown to stdout for piping; skip writing files |
| launchd schedule | `mac-care schedule install` | Writes scan-only plist to `~/Library/LaunchAgents/`; `--dry-run` prints plist |
| launchd uninstall | `mac-care schedule uninstall` | Removes plist and attempts launchctl unload; `--dry-run` prints planned removal |
| Schedule interval config | `--interval <hours>` | Default 24h; uses launchd `StartInterval`; runs `mac-care scan --notify` only |
| macOS scan notification | `mac-care scan --notify` | Posts compact scan summary through `osascript`; degrades gracefully |
| Safe cleanup (dry-run) | `mac-care clean --safe --dry-run` | Prints `auto_safe` candidates, no deletion |
| Quarantine cleanup execution | `mac-care clean --safe --execute` | Moves eligible `auto_safe` findings to quarantine with metadata; never `rm` |
| Review approval flow | `mac-care review approve` | Approves one `review` finding by stable report finding ID; quarantine-only on execute |
| Markdown + JSON + HTML reports | `mac-care scan` | Timestamped Markdown/JSON plus read-only `latest.html` in `~/.mac-care/reports/` |
| Report history index | `mac-care scan` | Writes read-only `index.html` listing previous JSON/Markdown/dashboard reports |
| Report rotation | `mac-care scan` | Deletes old reports; configurable `retention_days` + `retention_min_keep` |
| Protected paths config | `config.toml` | Hardcoded defaults + user override via TOML |
| Per-category policy | `config.toml` | `[policy.<category>]` overrides `min_age_days` per scan category |
| Additional scan paths | `config.toml` | `additional_scan_paths` extends workspace scan beyond defaults |
| Stable finding IDs | JSON reports | SHA-256 of `category+path+risk+source` — stable across runs |
| iOS backups scan | `mac-care scan` | `~/Library/Application Support/MobileSync/Backup/` — `review` |
| Messages attachments scan | `mac-care scan` | `~/Library/Messages/Attachments/` — `review` |
| Time Machine snapshots scan | `mac-care scan` | `tmutil listlocalsnapshots /` — `review` |
| Core dumps and crash logs | `mac-care scan` | `~/Library/Logs/DiagnosticReports/` — `review` |
| Broken symlinks scan | `mac-care scan` | Common `~/Library/` dirs — `review` |
| Login items scan | `mac-care scan` | `~/Library/LaunchAgents/` — lists persistent daemons as `review` |
| Stale runtime versions | `mac-care scan` | pyenv, nvm, rbenv, sdkman, rustup orphaned versions — `review` |
| Orphaned dot directories | `mac-care scan` | Inactive `~/.<tool>` dirs not referenced by any project — `review` |
| AI tool caches | `mac-care scan` | Copilot, Cursor, Windsurf, Continue, Ollama model caches — `auto_safe` |
| SSH key encryption check | `mac-care doctor` | Warns on unencrypted private keys in `~/.ssh/` |
| Redundant toolchain check | `mac-care doctor` | Detects multiple Python/Node/Ruby/Go/Rust installations |
| App uninstall helper | `mac-care uninstall <App>` | Support file discovery via Pearcleaner or native `~/Library/` patterns; `--execute` quarantines |
| Privacy audit | `mac-care audit privacy` | Reads macOS TCC database; lists all permission grants by service |
| Report compare | `mac-care compare` | Diffs two JSON reports; shows new, resolved, and changed findings |
| Obsidian export | `mac-care export --format obsidian` | Appends scan summary to today's daily note; deduplication-safe |
| GitHub Actions CI | `.github/workflows/test.yml` | `macos-latest`, Python 3.11, 163 tests |
| Branch protection | GitHub | Requires CI to pass before merge to main |
| Issue/PR templates | `.github/` | epic / story / enabler / bug + PR template |

---

---

### 🗓 Future / backlog

| Feature | Notes |
|---|---|
| `mac-care security` | KnockKnock (Objective-See) integration — launch agents, login items, browser extensions. Separate command, not part of `scan`. |
| `mas` integration | `mas outdated` for Mac App Store update checks. |
| Stale npm/pnpm global packages | Surface outdated global packages. |
| `brew` outdated formulae | Surface formulae with available updates (not just cache). |
| Xcode simulator cleanup | `xcrun simctl delete unavailable` — rebuildable, `auto_safe` candidate. |
| Python venv orphan detection | Find `.venv` dirs whose parent project no longer exists. |
| Large file finder | Top N largest files across home directory (excluding protected paths). |
| Menu bar / status item | Only after engine is proven useful. SwiftUI or Tauri. |

---

## OSS Tool Dependencies

All are optional — mac-care degrades gracefully when absent.

| Tool | Install | Used by | Notes |
|---|---|---|---|
| `dua` | `brew install dua-cli` | `tools/disk.py` (primary) | Fast parallel disk usage tree |
| `dust` | `brew install dust` | `tools/disk.py` (planned secondary) | Rust-based directory size tree |
| `gdu` | `brew install gdu` | Not integrated | Name collision with GNU `du` on machines with `coreutils` installed |
| `ncdu` | `brew install ncdu` | Not integrated | Interactive ncurses disk usage |
| `pearcleaner` | `brew install --cask pearcleaner` | `tools/pearcleaner.py` | CLI verified; `list-orphaned` timed out live |
| `mas` | `brew install mas` | Not yet integrated | Mac App Store CLI |
| KnockKnock | Manual download (Objective-See) | Planned `mac-care security` | Security persistence scanner |

---

## Protected Paths (Defaults)

Defined in `src/mac_care/config.py:DEFAULT_PROTECTED_PATHS`. Never auto-cleaned regardless of risk level. Override entirely via `protected_paths` in `config.toml`.

Key categories protected by default:
- VS Code extensions
- Browser native messaging hosts (Chrome, Firefox)
- `~/.ssh`
- Any directory containing an active or dirty git repo (checked dynamically at runtime)

---

## Known Constraints

- **Quarantine execution is intentionally narrow.** `mac-care clean --safe --execute` moves eligible `auto_safe` findings to quarantine, but broad container findings such as `user_caches`, `user_logs`, `trash`, and `tmp` are skipped until scan itemizes their contents.
- **`gdu` name collision.** `brew install coreutils` puts a `gdu` binary on PATH that is GNU `du`, not the Go disk usage analyzer. `tools/disk.py` uses `dua` as primary — `gdu` integration is deferred until resolved (possible fix: fingerprint binary via `--help` output before use).
- **Pearcleaner live constraint.** Pearcleaner 5.4.3 installed successfully via Homebrew cask and linked `/opt/homebrew/bin/pearcleaner`. `pearcleaner --help` confirms `list-orphaned`, but the real `pearcleaner list-orphaned` call did not return within 60 seconds on this machine. The wrapper's timeout path returned `[]` as intended, so scans stay responsive and Pearcleaner findings remain optional/review-only.
- **No scan output format flags yet.** `mac-care scan` always writes both files. `--stdout --format json/markdown` is in progress (issue #6).
- **Interactive notification actions are not implemented.** Notifications summarize the scan only; review still happens in reports.

---

## Test Coverage

163 tests, all passing. Runtime: ~0.3s locally, ~14s on `macos-latest` CI.

| Test file | Coverage |
|---|---|
| `tests/test_clean.py` | Dry-run default, quarantine moves, metadata, protected-path re-check, non-itemized skip |
| `tests/test_cli.py` | Scan stdout JSON/Markdown and default report-writing command behavior |
| `tests/test_compare.py` | New/resolved/changed finding diff, zero-size reason diff, JSON/Markdown render |
| `tests/test_export.py` | Obsidian daily note creation, deduplication, missing reports error |
| `tests/test_history.py` | Report history loading, malformed report skipping, index rendering/writing |
| `tests/test_ids.py` | Stable finding ID behavior; reason/size exclusion; risk-change stability |
| `tests/test_notification.py` | Notification text and graceful `osascript` delivery behavior |
| `tests/test_safety.py` | `is_protected()` — protected paths, quarantine dir, non-protected paths |
| `tests/test_scan.py` | All new scan functions: iOS backups, Messages, Time Machine, crash logs, broken symlinks, login items, stale runtimes, orphaned dotdirs, AI tool caches |
| `tests/test_scheduler.py` | launchd plist rendering, bootstrap activation, dry-run install/uninstall, plist write/remove |
| `tests/test_report.py` | Markdown/JSON/HTML rendering, risk grouping, read-only dashboard guard, rotation |
| `tests/test_review.py` | Review approval dry-run, quarantine execution, protected/unknown finding rejection |
| `tests/test_summary.py` | Risk totals, top findings, tool warning count |
| `tests/test_git_safety.py` | `find_git_repos`, `is_dirty`, `has_active_worktrees`, `unsafe_repos` — all degradation paths |
| `tests/test_doctor.py` | `recommend_tools`, SSH key encryption check, redundant toolchain detection |
| `tests/tools/test_brew.py` | `_parse_size`, full parse, sizes, risk/source tagging, all degradation |
| `tests/tools/test_disk.py` | dua path, du fallback, `size_of`, nonexistent, summary format |
| `tests/tools/test_docker.py` | `_parse_docker_size`, 4-category parse, reclaimable sizes, hints, degradation |
| `tests/tools/test_pearcleaner.py` | `_guess_app_name`, path parse, summary line skip, risk/source, degradation |

**Testing rules (must be maintained):**
- Tests never touch the real filesystem — use `tmp_path`
- Tests never call real external tools — mock all `subprocess.run` calls
- Mock target is always the module's own import (e.g. `mac_care.doctor.which`, not `shutil.which`)
- Every new `tools/` module must have at least one degradation test (tool missing, timeout, OSError)

---

## Example scan output shape

Reports include a reusable compact summary used by CLI output and intended for future HTML reports and notifications:

```json
{
  "summary": {
    "risks": {
      "auto_safe": {"count": 12, "size_bytes": 109000000},
      "review": {"count": 4, "size_bytes": 9800000000},
      "protected": {"count": 1, "size_bytes": 3200000000}
    },
    "top_findings": [],
    "tool_warning_count": 2
  }
}
```

JSON report findings also include stable IDs used for review approval. The ID is a 16-character hex prefix of `SHA-256(category + "\0" + path + "\0" + risk + "\0" + source)`. `reason` and `size_bytes` are intentionally excluded so IDs remain stable across scans even when subdirectory sizes change:

```json
{
  "findings": [
    {
      "id": "3b6d0f0d9a8c1e2f",
      "category": "orphaned_app_files",
      "path": "/Users/you/Library/Application Support/Zoom",
      "risk": "review",
      "source": "pearcleaner"
    }
  ]
}
```

Pipe-friendly scan output skips file writing and emits a single report format:

```bash
mac-care scan --stdout --format json
mac-care scan --stdout --format markdown
```

Default scan writes `latest.html` as a static local dashboard alongside timestamped Markdown and JSON reports. The HTML is read-only by design: it summarizes findings, risk groups, top findings, and doctor output, but does not include cleanup action controls.

Periodic scan scheduling is launchd-based and scan-only:

```bash
mac-care schedule install --dry-run
mac-care schedule install --interval 24
mac-care schedule uninstall --dry-run
mac-care schedule uninstall
```

Scheduled scans use `mac-care scan --notify`, which writes reports and posts a compact macOS notification. Notification delivery failures are ignored so scan/report generation still succeeds.

Each default scan also updates `index.html` in the reports directory. The index is read-only and lists historical JSON/Markdown/dashboard reports in reverse chronological order, skipping malformed JSON reports safely.

| Source | Category examples | Risk |
|---|---|---|
| Homebrew | Per-item stale formulae, old downloads | `auto_safe` |
| Docker | Images, build cache, volumes, containers | `review` |
| Disk | Xcode DerivedData, Gradle cache, user caches | `auto_safe` / `review` |
| Disk (enriched) | Top subdirs listed in reason for dirs >500 MB | — |
| Downloads | Old .dmg / .pkg / .zip past `min_age_days` | `review` |
| Pearcleaner | Orphaned app support paths (uninstall command) | `review` |
| Git workspaces | Any workspace with active/dirty repos | `protected` |
| Native (scan.py) | iOS backups, Messages attachments, Time Machine snapshots | `review` |
| Native (scan.py) | Core dumps, crash logs, broken symlinks, login items | `review` |
| Native (scan.py) | Stale runtime versions (pyenv/nvm/rbenv/sdkman/rustup) | `review` |
| Native (scan.py) | Orphaned dot directories | `review` |
| Native (scan.py) | AI tool caches (Copilot, Cursor, Ollama, etc.) | `auto_safe` |

---

## Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-01 | Python CLI first, not SwiftUI | Get the engine working before any UI investment |
| 2026-05-01 | Report-first, no deletion by default | Primary value is visibility, not automation |
| 2026-05-01 | OSS orchestrator pattern | Trust brew/docker/dua output over reimplementing their logic |
| 2026-05-02 | `dua` as disk primary, `du` as fallback | dua is fast and parallel; du is always available; both parse cleanly |
| 2026-05-02 | `gdu` integration deferred | Name collision with GNU du — needs binary fingerprinting before use |
| 2026-05-02 | Docker findings all `review` | Docker cleanup is stateful and non-trivial; always require user intent |
| 2026-05-02 | Pearcleaner all `review` | Orphaned file determination is heuristic; human confirmation is necessary |
| 2026-05-02 | Keep Pearcleaner timeout degradation | Live `list-orphaned` can hang; wrapper should return `[]` rather than block scan |
| 2026-05-02 | Quarantine dir instead of `rm` | One-way door prevention; files can be recovered from quarantine |
| 2026-05-02 | Repo made public | Enables GitHub Actions CI and branch protection on free tier |
