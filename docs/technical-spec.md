# mac-care Technical Spec

## Goal

Replace the practical operational value of CleanMyMac for a developer machine with a free, local, report-first CLI tool. No polished UI clone. No surprise deletions. Integrate good OSS tools rather than rebuilding commodity scanners.

Owner: Deepankar Joshi  
Repo: https://github.com/djspiceroute/mac-care  
Local path: `~/Developer/mac-care`  
Stack: Python 3.11+, stdlib only (no pip runtime deps)

---

## Feature Status

### ✅ Shipped (main, as of 2026-05-02)

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
| Safe cleanup (dry-run) | `mac-care clean --safe --dry-run` | Prints `auto_safe` candidates, no deletion |
| Markdown + JSON reports | `mac-care scan` | Timestamped, written to `~/Documents/MacCare/reports/` |
| Protected paths config | `config.toml` | Hardcoded defaults + user override via TOML |
| GitHub Actions CI | `.github/workflows/test.yml` | `macos-latest`, Python 3.11, 73 tests |
| Branch protection | GitHub | Requires CI to pass before merge to main |
| Issue/PR templates | `.github/` | epic / story / enabler / bug + PR template |

---

### 🔜 Next sprint (planned, not started)

| Feature | Command | Notes |
|---|---|---|
| launchd schedule | `mac-care schedule install` | Writes plist to `~/Library/LaunchAgents/`; `--dry-run` prints plist |
| launchd uninstall | `mac-care schedule uninstall` | Removes plist, unloads |
| Schedule interval config | `--interval <hours>` | Default 24h; runs `mac-care scan` only (no clean) |
| Scan output flags | `mac-care scan --stdout` | Print JSON or Markdown to stdout for piping; skip writing files |
| Pearcleaner live test | — | Install `brew install --cask pearcleaner` and run real scan |

---

### 🗓 Future / backlog

| Feature | Notes |
|---|---|
| `mac-care security` | KnockKnock (Objective-See) integration — launch agents, login items, browser extensions, kernel extensions. Separate command, not part of `scan`. |
| Actual deletion (quarantine) | `mac-care clean --safe --execute` moves files to `quarantine_dir` instead of `rm`. Needs confirmation prompt. |
| Review-class cleanup with approval | Interactive approval flow for `review` findings. List → confirm each → quarantine. |
| macOS notification after scan | Post a macOS notification with summary when scheduled scan completes. |
| Menu bar / status item | Future — only after engine is proven useful. SwiftUI or Tauri. |
| `mas` integration | `mas outdated` for Mac App Store update checks. |
| Stale npm/pnpm global packages | Surface outdated global packages. |
| `brew` outdated formulae | Surface formulae with available updates (not just cache). |
| Xcode simulator cleanup | `xcrun simctl delete unavailable` — rebuildable, auto_safe candidate. |
| Python venv orphan detection | Find `.venv` dirs whose parent project no longer exists. |
| Large file finder | Top N largest files across home directory (excluding protected paths). |
| Report history / trending | Compare consecutive reports to show what grew since last scan. |

---

## OSS Tool Dependencies

All are optional — mac-care degrades gracefully when absent.

| Tool | Install | Used by | Status |
|---|---|---|---|
| `dua` | `brew install dua-cli` | `tools/disk.py` (primary) | ✅ Installed |
| `dust` | `brew install dust` | `tools/disk.py` (not yet integrated — planned secondary) | ❌ Not installed |
| `gdu` | `brew install gdu` | Not integrated (conflicts with GNU du on this machine) | ⚠️ Name collision |
| `ncdu` | `brew install ncdu` | Not integrated | ❌ Not installed |
| `pearcleaner` | `brew install --cask pearcleaner` | `tools/pearcleaner.py` | ❌ Not installed — pending live test |
| `mas` | `brew install mas` | Not yet integrated | ✅ Installed |
| `mole` | `brew install mole` | Not integrated (SSH tunnel manager — not relevant to scan) | ❌ Not installed |
| KnockKnock | Manual download (Objective-See) | Planned `mac-care security` | ❌ Not installed |

---

## Protected Paths (Defaults)

Defined in `src/mac_care/config.py:DEFAULT_PROTECTED_PATHS`. Never auto-cleaned regardless of risk level.

```
~/.codex
~/.agents
~/multica
~/multica_workspaces
~/.vscode/extensions
~/Library/Application Support/Google/Chrome/NativeMessagingHosts
~/Library/Application Support/Mozilla/NativeMessagingHosts
any path containing a dirty or active git repo (dynamic — checked at runtime)
```

---

## Known Constraints

- **No deletion implemented yet.** `mac-care clean --safe` only operates in dry-run mode. The `--execute` path exists in the interface but is a no-op stub pending quarantine implementation.
- **`gdu` name collision.** On this machine, `gdu` in PATH is GNU `du` (from `brew install coreutils`), not the Go disk usage analyzer. The `tools/disk.py` module uses `dua` as primary — `gdu` integration is blocked until the name collision is resolved (possible workaround: check binary help output to distinguish).
- **Pearcleaner not yet live-tested.** The `tools/pearcleaner.py` module is complete and tested with mocks. Live test pending `brew install --cask pearcleaner`.
- **No scan output format flags.** `mac-care scan` always writes both files. `--stdout --format json/markdown` is planned but not yet implemented.
- **launchd scheduler not yet built.** Periodic automated scanning requires `mac-care schedule install`. Until then, scan must be run manually.

---

## Test Coverage

73 tests, all passing. Runtime: ~0.3s locally, ~14s on `macos-latest` CI.

| Test file | Coverage |
|---|---|
| `tests/test_report.py` | Markdown rendering, risk grouping |
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

## Real-world scan results (2026-05-02, this machine)

| Source | Count | Size |
|---|---|---|
| Homebrew (brew cleanup) | 83 items | ~109 MB |
| Docker images | 1 | 9.8 GB reclaimable |
| Docker build cache | 1 | 5.0 GB reclaimable |
| Docker volumes | 1 | 197 MB reclaimable |
| Docker containers | 1 | 1.2 MB reclaimable |
| Gradle cache | 1 | 4.9 GB (review) |
| user_caches | 1 | 4.1 GB (auto_safe) — largest: Google 1.3 GB, ms-playwright 1.0 GB |
| Xcode DerivedData | 1 | 2.3 GB (auto_safe) |
| user_logs | 1 | 26 MB (auto_safe) |
| Codex workspaces | 1 | 38 MB (protected — dirty git repos) |
| **Total** | **97** | **25.4 GB observed** |

---

## Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-01 | Python CLI first, not SwiftUI | Get the engine working before any UI investment |
| 2026-05-01 | Report-first, no deletion by default | Primary value is visibility, not automation |
| 2026-05-01 | OSS orchestrator pattern | Trust brew/docker/dua output over reimplementing their logic |
| 2026-05-02 | `dua` as disk primary, `du` as fallback | dua is fast and parallel; du is always available; both parse cleanly |
| 2026-05-02 | `gdu` integration deferred | Name collision with GNU du on this machine — needs binary fingerprinting |
| 2026-05-02 | Docker findings all `review` | Docker cleanup is stateful and non-trivial; always require user intent |
| 2026-05-02 | Pearcleaner all `review` | Orphaned file determination is heuristic; human confirmation is necessary |
| 2026-05-02 | Quarantine dir instead of `rm` | One-way door prevention; files at `~/Documents/MacCare/quarantine/` can be recovered |
| 2026-05-02 | Repo made public | Enables GitHub Actions CI and branch protection on free tier |
