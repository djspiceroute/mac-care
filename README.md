# mac-care

> A free, local **Developer Health Console** for macOS — not just a cleaner, but a visibility layer for your machine.

[![Tests](https://github.com/djspiceroute/mac-care/actions/workflows/test.yml/badge.svg)](https://github.com/djspiceroute/mac-care/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

mac-care is a **coordinator, not a scanner**. It integrates trusted OSS tools — Homebrew, Docker, `dua`, Pearcleaner — to give you a unified view of your system's storage, security, and tool health. 

Everything is **local-only, transparent, and reversible**.

---

## Why

Developer machines are complex. Tools like CleanMyMac are useful but opaque and expensive. mac-care is designed for engineers who want:
- **Visibility**: See exactly where space went and why.
- **Safety**: Never delete active work (built-in git safety gate).
- **Reversibility**: Files are moved to quarantine, never instantly purged.
- **Local Control**: No cloud uploads, no "AI" magic, just grep-able reports and local logs.

---

## Features

- **Disk scan** — logs, caches, trash, tmp, Xcode DerivedData, Gradle cache, old installers.
- **Homebrew cache** — per-item reclaimable from `brew cleanup --dry-run`.
- **Docker** — reclaimable per category (images, volumes, containers, build cache).
- **Orphaned app files** — discovery via Pearcleaner integration.
- **Persistence Visibility** — list login items, launch agents, and launch daemons.
- **Dev Tool Health** — check required tools, SSH key encryption, and redundant toolchains.
- **Privacy Audit** — audit macOS TCC permissions (Full Disk Access required).
- **Git Safety Gate** — any directory with a dirty or active repo is automatically protected.
- **Safe Cleanup** — dry-run by default; `--execute` quarantines (not `rm`) findings.
- **Report History** — timestamped Markdown + JSON reports with historical rotation.

---

## Security & Privacy Boundaries

mac-care is built for security-conscious users who are proficient with the terminal.

1. **Local-Only**: All scanning and reporting happens on your machine. No data is ever uploaded.
2. **Read-Only Scans**: The `scan` command never modifies your files. It only observes.
3. **Quarantine Model**: Destructive actions move files to `~/.mac-care/quarantine/`. They are not deleted from disk until you explicitly purge them.
4. **Guided Sudo**: mac-care never runs `sudo` automatically. For actions requiring elevated permissions (like deleting system-protected apps), it provides the exact command for you to review and run manually.
5. **Full Disk Access**: Required for deep audits (like TCC or Messages attachments). mac-care explains why FDA is needed and how to grant/revoke it.
6. **Tool Transparency**: Reports record the absolute paths of external binaries used, ensuring you know exactly what was executed.

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
Runs all scanners and writes reports to `~/.mac-care/reports/`.
- Use `--stdout` for pipe-friendly output.
- Use `--notify` to get a macOS notification on completion.

### `mac-care doctor`
Checks developer tool health: required tools, PATH resolution, Docker daemon, SSH key encryption.

### `mac-care clean --safe --execute`
Moves eligible `auto_safe` findings to quarantine.
- Use `--purge` to permanently delete `auto_safe` findings (requires confirmation).

### `mac-care review approve`
Approves one `review` finding from a JSON report by its stable ID.

### `mac-care quarantine restore <identifier>`
Restores a quarantined item by stable finding ID, metadata path, original path, or quarantine path.
- Dry-run by default; use `--execute` to move the item back.
- Refuses to overwrite an existing destination.

### `mac-care uninstall <AppName>`
Finds an app bundle and its support files. Provides guidance for removal or automates quarantine.

### `mac-care audit privacy`
Lists all macOS TCC permissions granted to apps. (Requires Full Disk Access).

### `mac-care schedule install`
Installs a `launchd` plist for periodic automated scans.

### `mac-care compare`
Diffs two JSON reports to show new, resolved, or changed findings.

---

## Roadmap: Phase 2

| Status | Feature |
|---|---|
| ✅ | **App Uninstall** — Pearcleaner-first support file discovery |
| ✅ | **Privacy Audit** — TCC database permission viewer |
| ✅ | **Report Compare** — Diffing two scan results |
| ✅ | **Report Rotation** — Automated cleanup of old reports |
| ✅ | **Action Service Layer** — Reusable engine for CLI and Dashboard (#61) |
| ✅ | **Quarantine Restore** — Boringly reversible "Undo" for cleanup (#62) |
| 🗓 | **Quarantine Management** — status, purge, and auto-rotation (#44, #45) |
| 🗓 | **Security Audit** — Persistence visibility for LaunchAgents/Daemons (#54) |
| 🗓 | **Xcode Dev Cleanup** — Simulator and device support cleanup (#53) |
| 🗓 | **Large File Finder** — Global scanner with protected-path exclusions (#51) |
| 🗓 | **Interactive Dashboard** — Terminal-based (TUI) management console (#64) |

---

## OSS integrations

| Module | Backed by | What it surfaces |
|---|---|---|
| `tools/brew.py` | `brew cleanup` | Homebrew cache reclaimable |
| `tools/disk.py` | `dua` / `du` | Large directory trees |
| `tools/docker_check.py` | `docker system df` | Container and volume waste |
| `tools/pearcleaner.py` | `pearcleaner` | Orphaned app support files |

---

## License

MIT
