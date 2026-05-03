# mac-care

> A free, local macOS maintenance CLI for developer machines — report-first, no surprise deletions.

[![Tests](https://github.com/djspiceroute/mac-care/actions/workflows/test.yml/badge.svg)](https://github.com/djspiceroute/mac-care/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

mac-care is a **coordinator, not a scanner**. It calls trusted OSS tools — Homebrew, Docker, `dua`, Pearcleaner — collects their output into a unified model, and produces Markdown + JSON reports you can act on. Nothing is deleted without your explicit intent.

---

## Why

Tools like CleanMyMac are useful but cost money, run in the cloud, and make opaque decisions. mac-care is the opposite: free, fully local, transparent about what it found and why, and designed to be safe enough to run on a machine with active work.

---

## Features

- **Disk scan** — logs, caches, trash, tmp, Xcode DerivedData, Gradle cache, old installers
- **Homebrew cache** — per-item reclaimable from `brew cleanup --dry-run`
- **Docker** — reclaimable per category (images, volumes, containers, build cache)
- **Orphaned app files** — via Pearcleaner, if installed
- **iOS backups, Messages attachments, Time Machine snapshots** — surfaced as `review` findings
- **Core dumps and crash logs** — per-item from `~/Library/Logs/DiagnosticReports`
- **Broken symlinks** — detected across standard home library paths
- **Login items** — lists persistent launch agents/daemons as `review` findings
- **Stale runtime versions** — orphaned `pyenv`, `nvm`, `rbenv`, `sdkman`, `rustup` versions
- **Orphaned dot directories** — inactive `~/.tool-version` directories not referenced by any project
- **AI tool caches** — Copilot, Cursor, Windsurf, Continue, Ollama model caches
- **Git safety gate** — any directory with a dirty or active repo is marked `protected` and never touched
- **Developer tool health** — checks required tools, SSH key encryption, redundant toolchains
- **OSS recommendations** — lists missing optional tools with exact `brew install` commands
- **Safe cleanup** — dry-run by default; `--execute` quarantines (not `rm`) eligible findings
- **App uninstall helper** — finds support files for a deleted app via Pearcleaner or native patterns
- **Privacy audit** — reads macOS TCC database to list all permission grants
- **Scheduled scans** — launchd-backed periodic scans with macOS notification on completion
- **Report compare** — diff two JSON reports to surface new, resolved, and changed findings
- **Obsidian export** — appends scan summary to your daily note (deduplication-safe)

---

## Quick start

```bash
git clone https://github.com/djspiceroute/mac-care.git
cd mac-care
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
mac-care scan
```

No external dependencies required. Optional OSS tools (listed below) extend what the scan surfaces.

---

## Commands

### `mac-care scan`

Runs all scanners and writes a timestamped Markdown + JSON report to `~/.mac-care/reports/`.

```
$ mac-care scan
Scanned 42 findings, 8.3 GB observed (18 auto_safe / 21 review / 3 protected; 0 tool warnings).
Markdown report: ~/.mac-care/reports/mac-care-2026-05-02-210826.md
JSON report:     ~/.mac-care/reports/mac-care-2026-05-02-210826.json
HTML report:     ~/.mac-care/reports/latest.html
```

The report groups findings by risk level — `auto_safe`, `review`, `protected` — with size totals and per-item reasons.

### `mac-care doctor`

Checks developer tool health: required tools, Homebrew PATH, Docker daemon reachability.

```
$ mac-care doctor
brew:           ok
git:            ok
docker_daemon:  ok - daemon is reachable
homebrew_path:  ok
pnpm:           missing - not on PATH
```

### `mac-care tools status`

Shows all required and optional tools with installed/missing status.

### `mac-care tools recommend`

Lists missing optional OSS tools grouped by function, with install commands.

```
$ mac-care tools recommend

Disk analysis:
  dua     Fast parallel disk usage tree   →  brew install dua-cli
  dust    Rust-based directory size tree  →  brew install dust

App cleanup:
  pearcleaner  Orphaned app support files  →  brew install --cask pearcleaner
```

### `mac-care clean --safe --dry-run`

Prints what would be cleaned from `auto_safe` findings. Does not delete anything.

### `mac-care clean --safe --execute`

Moves eligible `auto_safe` findings to the configured quarantine directory. This is intentionally narrower than scan output: broad containers such as `~/Library/Caches` and `/tmp` are skipped until scan itemizes their contents.

### `mac-care review approve`

Approves one `review` finding from a JSON report by stable finding ID. Dry-run is the default.

```bash
mac-care review approve --report ~/.mac-care/reports/mac-care-2026-05-02-220005.json --finding-id abc123
mac-care review approve --report ~/.mac-care/reports/mac-care-2026-05-02-220005.json --finding-id abc123 --execute
```

### `mac-care uninstall <AppName>`

Finds the app bundle and all related support files. Dry-run by default; `--execute` quarantines them.

```bash
mac-care uninstall Zoom
mac-care uninstall Zoom --execute
```

Uses Pearcleaner for deep discovery when installed; falls back to native `~/Library/` pattern matching.

### `mac-care audit privacy`

Reads the macOS TCC database and lists every permission grant grouped by service. Requires Full Disk Access.

```bash
mac-care audit privacy
```

### `mac-care schedule install`

Installs a launchd plist that runs `mac-care scan --notify` on a configurable interval.

```bash
mac-care schedule install --interval 12   # every 12 hours
mac-care schedule install --dry-run       # print plist without writing
mac-care schedule uninstall
```

### `mac-care compare`

Diffs two JSON reports and shows new, resolved, and changed findings.

```bash
mac-care compare old.json new.json
mac-care compare old.json new.json --format json
```

### `mac-care export --format obsidian`

Appends a scan summary block to today's Obsidian daily note. Skips silently if the same scan was already exported.

```bash
mac-care export --format obsidian --vault-path ~/Notes
```

---

## Risk levels

Every finding has a risk level that controls what mac-care will and won't do automatically.

| Level | Meaning | Example |
|---|---|---|
| `auto_safe` | Rebuildable or declared safe by the source tool | Homebrew cache, Xcode DerivedData |
| `review` | Needs human confirmation before deletion | Docker volumes, old installers, orphaned app files |
| `protected` | Never touched — ever | Dirty/active git repos, paths listed in config |

Only `auto_safe` findings are eligible for `mac-care clean`. `review` and `protected` findings only appear in reports.

---

## OSS integrations

Each integration lives in `src/mac_care/tools/` and degrades gracefully — if the tool is not installed, it returns an empty finding list and the scan continues uninterrupted.

| Module | Backed by | What it surfaces |
|---|---|---|
| `tools/brew.py` | `brew cleanup --dry-run` | Per-item Homebrew cache reclaimable |
| `tools/disk.py` | `dua` (primary) / `du` (fallback) | Directory sizes; top-subdir breakdown for dirs >500 MB |
| `tools/docker_check.py` | `docker system df` | Reclaimable per category |
| `tools/pearcleaner.py` | `pearcleaner list-orphaned` | App support files orphaned after app deletion |

Install the recommended backends for the best results:

```bash
brew install dua-cli              # fast parallel disk analysis
brew install --cask pearcleaner   # orphaned app file scanner
```

---

## Configuration

Config file: `~/.config/mac-care/config.toml` — optional, defaults work out of the box.

```toml
[policy]
reports_dir    = "~/.mac-care/reports"
quarantine_dir = "~/.mac-care/quarantine"
min_age_days   = 14
retention_days = 30        # delete reports older than this
retention_min_keep = 10    # always keep at least this many

protected_paths = [
  "~/.ssh",
  "~/Projects/active-client",
]

# additional_scan_paths = ["~/workspace"]  # scan extra workspace dirs

# [policy.downloads]
# min_age_days = 30   # per-category override
```

Any path under `protected_paths` is never auto-cleaned. Paths containing active or dirty git repositories are also automatically protected at runtime — this is checked dynamically on every scan.

---

## Project layout

```
src/mac_care/
  cli.py            Command routing (10 commands)
  scan.py           Orchestrates all scanners → list[Finding]
  doctor.py         Developer tool health checks + recommendations
  clean.py          Safe cleanup with git safety re-check
  report.py         Markdown + JSON + HTML report writer; report rotation
  model.py          Finding, ToolStatus, format_bytes, path_size
  config.py         Config loader (TOML + defaults)
  config.py         Per-category policy, retention, additional scan paths
  git_safety.py     find_git_repos, is_dirty, unsafe_repos
  safety.py         is_protected() — shared by scan.py and clean.py
  ids.py            Stable finding ID (SHA-256 of category+path+risk+source)
  summary.py        ScanSummary — risk totals, top findings, tool warnings
  review.py         approve_finding() by stable ID
  scheduler.py      launchd plist install/uninstall
  notification.py   macOS notification via osascript
  history.py        Report history index.html writer
  privacy.py        TCC database audit
  uninstall.py      App support file discovery and quarantine
  compare.py        Diff two JSON reports
  export.py         Obsidian daily note export
  tools/
    brew.py         brew cleanup --dry-run integration
    disk.py         dua / du disk tree integration
    docker_check.py docker system df integration
    pearcleaner.py  pearcleaner list-orphaned integration
```

---

## Development

```bash
pip install -e ".[dev]"       # install with dev dependencies
python -m pytest tests/ -v    # run all tests (~0.3s)
mac-care scan                  # live scan
```

Tests never touch the real filesystem and never call real external tools — all subprocess calls are mocked. See `AGENTS.md` for contribution rules and branch conventions.

---

## Roadmap

| Status | Feature |
|---|---|
| ✅ | `mac-care scan` — full disk + developer + AI tool scan |
| ✅ | `mac-care clean --safe --execute` — quarantine-based cleanup (never `rm`) |
| ✅ | `mac-care review approve` — stable-ID approval for `review` findings |
| ✅ | `mac-care schedule install/uninstall` — launchd periodic scan |
| ✅ | `mac-care scan --stdout --format json/markdown` — pipe-friendly output |
| ✅ | `mac-care uninstall <App>` — support file discovery and quarantine |
| ✅ | `mac-care audit privacy` — TCC permission audit |
| ✅ | `mac-care compare` — diff two JSON reports |
| ✅ | `mac-care export --format obsidian` — daily note export |
| ✅ | Report rotation — keep last N reports, configurable retention |
| 🗓 | `mac-care security` — KnockKnock (Objective-See) integration for login items, browser extensions |
| 🗓 | `mas` integration — Mac App Store update checks |
| 🗓 | Xcode simulator cleanup — `xcrun simctl delete unavailable` |
| 🗓 | Large file finder — top N files across home directory |

See [`docs/technical-spec.md`](docs/technical-spec.md) for full feature status, known constraints, and decision log.

---

## License

MIT
