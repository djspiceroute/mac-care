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
| Safe cleanup (dry-run) | `mac-care clean --safe --dry-run` | Prints `auto_safe` candidates, no deletion |
| Markdown + JSON reports | `mac-care scan` | Timestamped, written to `~/Documents/MacCare/reports/` |
| Protected paths config | `config.toml` | Hardcoded defaults + user override via TOML |
| GitHub Actions CI | `.github/workflows/test.yml` | `macos-latest`, Python 3.11, 73 tests |
| Branch protection | GitHub | Requires CI to pass before merge to main |
| Issue/PR templates | `.github/` | epic / story / enabler / bug + PR template |

---

### 🔜 In progress (GitHub issues open, Codex active)

#### Epic: Quarantine-based cleanup ([#4](https://github.com/djspiceroute/mac-care/issues/4))

| Feature | Issue | Notes |
|---|---|---|
| Move `auto_safe` findings to quarantine | [#12](https://github.com/djspiceroute/mac-care/issues/12) | `mac-care clean --safe --execute` moves to `quarantine_dir`, never `rm` |
| Review approval flow | [#13](https://github.com/djspiceroute/mac-care/issues/13) | Interactive per-item confirmation for `review` findings |
| Dashboard action safety model | [#14](https://github.com/djspiceroute/mac-care/issues/14) | Backend safety contract for any UI-triggered cleanup |

#### Epic: Unified local report viewer ([#2](https://github.com/djspiceroute/mac-care/issues/2))

| Feature | Issue | Notes |
|---|---|---|
| Compact scan summary model | [#8](https://github.com/djspiceroute/mac-care/issues/8) | Lightweight summary struct for dashboard and notifications |
| HTML dashboard from scan results | [#9](https://github.com/djspiceroute/mac-care/issues/9) | Static HTML report generated alongside Markdown + JSON |
| Report history index | [#10](https://github.com/djspiceroute/mac-care/issues/10) | Track consecutive scans; surface what grew since last run |
| Stdout and format flags | [#6](https://github.com/djspiceroute/mac-care/issues/6) | `mac-care scan --stdout --format json/markdown` for piping |

#### Epic: Periodic local scan workflow ([#3](https://github.com/djspiceroute/mac-care/issues/3))

| Feature | Issue | Notes |
|---|---|---|
| launchd schedule install/uninstall | [#5](https://github.com/djspiceroute/mac-care/issues/5) | Writes plist to `~/Library/LaunchAgents/`; `--dry-run` prints plist |
| macOS notification after scheduled scan | [#11](https://github.com/djspiceroute/mac-care/issues/11) | Post summary notification on scan completion |

#### Enablers

| Feature | Issue | Notes |
|---|---|---|
| Pearcleaner live test | [#7](https://github.com/djspiceroute/mac-care/issues/7) | Install and run real scan; integration is mock-tested only today |

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
| `pearcleaner` | `brew install --cask pearcleaner` | `tools/pearcleaner.py` | Pending live test (#7) |
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

- **No deletion implemented yet.** `mac-care clean --safe` only operates in dry-run mode. The `--execute` path is a stub pending quarantine implementation (issue #12).
- **`gdu` name collision.** `brew install coreutils` puts a `gdu` binary on PATH that is GNU `du`, not the Go disk usage analyzer. `tools/disk.py` uses `dua` as primary — `gdu` integration is deferred until resolved (possible fix: fingerprint binary via `--help` output before use).
- **Pearcleaner not yet live-tested.** `tools/pearcleaner.py` is complete and tested with mocks. Live test pending issue #7.
- **No scan output format flags yet.** `mac-care scan` always writes both files. `--stdout --format json/markdown` is in progress (issue #6).
- **launchd scheduler not yet built.** Periodic automated scanning requires `mac-care schedule install` (issue #5).

---

## Test Coverage

75 tests, all passing. Runtime: ~0.3s locally, ~14s on `macos-latest` CI.

| Test file | Coverage |
|---|---|
| `tests/test_report.py` | Markdown rendering, risk grouping |
| `tests/test_summary.py` | Risk totals, top findings, tool warning count |
| `tests/test_git_safety.py` | `find_git_repos`, `is_dirty`, `has_active_worktrees`, `unsafe_repos` — all degradation paths |
| `tests/test_doctor.py` | `recommend_tools` — missing/installed/empty/key/brew-prefix |
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

| Source | Category examples | Risk |
|---|---|---|
| Homebrew | Per-item stale formulae, old downloads | `auto_safe` |
| Docker | Images, build cache, volumes, containers | `review` |
| Disk | Xcode DerivedData, Gradle cache, user caches | `auto_safe` / `review` |
| Disk (enriched) | Top subdirs listed in reason for dirs >500 MB | — |
| Downloads | Old .dmg / .pkg / .zip past `min_age_days` | `review` |
| Pearcleaner | Orphaned app support paths | `review` |
| Git workspaces | Any workspace with active/dirty repos | `protected` |

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
| 2026-05-02 | Quarantine dir instead of `rm` | One-way door prevention; files can be recovered from quarantine |
| 2026-05-02 | Repo made public | Enables GitHub Actions CI and branch protection on free tier |
