# mac-care

Local macOS maintenance for a developer machine. A free, self-hosted alternative to tools like CleanMyMac — report-first, no surprise deletions, OSS tools as backends.

[![Tests](https://github.com/djspiceroute/mac-care/actions/workflows/test.yml/badge.svg)](https://github.com/djspiceroute/mac-care/actions/workflows/test.yml)

---

## What it does

`mac-care` is a coordinator, not a scanner. It calls trusted OSS tools, collects their output into a unified `Finding` model, and generates Markdown + JSON reports. You decide what to act on.

- **Scans** cleanup opportunities from Homebrew, Docker, disk usage, Xcode, caches, old installers, and orphaned app files
- **Guards** active git repos and worktrees from being touched before any cleanup
- **Checks** developer tool health (required tools, optional OSS integrations, Docker daemon)
- **Recommends** OSS tools to install with exact brew commands
- **Reports** findings grouped by risk level — `auto_safe`, `review`, `protected`
- **Cleans** only `auto_safe` findings, dry-run by default, quarantine dir instead of `rm`

---

## Quick start

```bash
git clone https://github.com/djspiceroute/mac-care.git
cd mac-care
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
mac-care scan
```

---

## Commands

### `mac-care scan`
Runs all scanners, writes a Markdown + JSON report to `~/Documents/MacCare/reports/`.

```
Scanned 42 findings, 8.3 GB observed.
Markdown report: ~/Documents/MacCare/reports/mac-care-<timestamp>.md
JSON report:     ~/Documents/MacCare/reports/mac-care-<timestamp>.json
```

### `mac-care doctor`
Checks required developer tools and environment health.

```
brew: ok
git: ok
docker_daemon: ok - daemon is reachable
homebrew_path: ok
pnpm: missing - not on PATH
```

### `mac-care tools status`
Shows all required + optional tools with installed/missing status.

### `mac-care tools recommend`
Lists missing optional OSS tools grouped by function, with install commands.

```
Disk analysis:
  dua     Fast parallel disk usage tree   →  brew install dua-cli
  dust    Rust-based directory size tree  →  brew install dust

App cleanup:
  pearcleaner  Orphaned app support files  →  brew install --cask pearcleaner
```

### `mac-care clean --safe --dry-run`
Prints what would be cleaned from `auto_safe` findings. Does not delete anything without `--execute` (not yet implemented — see roadmap).

---

## Risk levels

| Level | Meaning | Example |
|---|---|---|
| `auto_safe` | Rebuildable or explicitly safe per the source tool | Homebrew cache items, Xcode DerivedData |
| `review` | Needs human confirmation before deletion | Docker volumes, old installers, orphaned app files |
| `protected` | Never touched automatically | Active/dirty git repos, paths listed in config |

---

## OSS integrations

Each integration lives in `src/mac_care/tools/` and degrades gracefully — if the tool is not installed, it returns an empty list and the scan continues.

| Module | Tool | What it surfaces |
|---|---|---|
| `tools/brew.py` | `brew cleanup --dry-run` | Per-item Homebrew cache reclaimable, `auto_safe` |
| `tools/disk.py` | `dua` (primary) / `du` (fallback) | Fast directory sizes; top-subdir breakdown for dirs >500 MB |
| `tools/docker_check.py` | `docker system df` | Reclaimable per category: images, containers, volumes, build cache |
| `tools/pearcleaner.py` | `pearcleaner list-orphaned` | App support files orphaned after app deletion |

Finding sources are tagged in the `source` field: `native`, `brew`, `dua`, `docker`, `pearcleaner`.

### Install recommended tools

```bash
brew install dua-cli              # fast disk analysis (primary backend)
brew install dust                 # alternative disk tree
brew install --cask pearcleaner   # orphaned app file scanner
```

---

## Configuration

Config file: `~/.config/mac-care/config.toml` (optional — defaults work out of the box).

```toml
[policy]
reports_dir    = "~/Documents/MacCare/reports"
quarantine_dir = "~/Documents/MacCare/quarantine"
min_age_days   = 14

protected_paths = [
  "~/.ssh",
  "~/Projects/active-client",
  "~/.vscode/extensions",
]
```

See `examples/config.toml` for the full set of options.

---

## Protected paths

Any path listed under `protected_paths` in config will never be auto-cleaned. In addition, any directory containing an active or dirty git repository is automatically treated as protected at runtime — this is checked dynamically before every scan and clean operation.

Default protected paths are defined in `src/mac_care/config.py` and can be overridden entirely via config.

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Run a live scan
mac-care scan
```

### Project layout

```
src/mac_care/
  cli.py            Command routing
  scan.py           Orchestrates all scanners → list[Finding]
  doctor.py         Developer tool health checks + recommendations
  clean.py          Safe cleanup with git safety re-check
  report.py         Markdown + JSON report writer
  model.py          Finding, ToolStatus, format_bytes, path_size
  config.py         Config loader (TOML + defaults)
  git_safety.py     find_git_repos, is_dirty, unsafe_repos
  scheduler.py      (planned) launchd install/uninstall
  tools/
    brew.py         brew cleanup --dry-run integration
    disk.py         dua / du disk tree integration
    docker_check.py docker system df integration
    pearcleaner.py  pearcleaner list-orphaned integration

tests/
  test_report.py
  test_git_safety.py
  test_doctor.py
  tools/
    test_brew.py
    test_disk.py
    test_docker.py
    test_pearcleaner.py
```

---

## Roadmap

See `docs/technical-spec.md` for full feature status and next priorities.

**Next sprint:**
- `mac-care schedule install` / `schedule uninstall` — launchd plist for periodic automated scan
- `mac-care scan --stdout --format json` — pipe-friendly output without writing files
- KnockKnock (Objective-See) integration as a separate `mac-care security` command

---

## Agent instructions

See `AGENTS.md` for branch naming, git workflow, commit conventions, testing rules, safety constraints, and escalation policy.
