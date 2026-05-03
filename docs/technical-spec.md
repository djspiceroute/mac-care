# mac-care Technical Spec

## Goal

Provide a **Developer Health Console** for macOS that offers operational visibility and safe, reversible maintenance. mac-care acts as an orchestrator, integrating trusted OSS tools rather than rebuilding commodity scanners.

Repo: https://github.com/djspiceroute/mac-care  
Stack: Python 3.11+, stdlib only (no pip runtime deps)

---

## Feature Status

### 🟢 Phase 1: Foundation (Shipped)

| Feature | Notes |
|---|---|
| **Deep Scanners** | logs, caches, trash, tmp, Xcode DerivedData, Gradle cache |
| **OSS Integrations** | Homebrew, Docker, dua, Pearcleaner |
| **Git Safety Gate** | Dirty/active repo detection; automatic protection of workspace paths |
| **Tool Health** | Required tools check, SSH key encryption audit, redundant toolchain detection |
| **Reports** | Timestamped MD + JSON; static HTML dashboard; report rotation |
| **Safe Cleanup** | dry-run default; quarantine execution for `auto_safe` findings |
| **Uninstall** | App support-file discovery and guided removal |
| **Privacy Audit** | TCC database audit (requires Full Disk Access) |
| **History/Compare** | Historical scan index and diffing between scan results |
| **Scheduling** | launchd-backed periodic scans with macOS notifications |
| **Export** | Obsidian daily note export |

### 🟡 Phase 2: Interactive Console (In Progress)

| Feature | Notes | Issue | Status |
|---|---|---|---|
| **Quarantine Management** | status, purge, and auto-rotation | #44, #45 | Planned |
| **Security Audit** | Persistence visibility for LaunchAgents/Daemons | #54 | Planned |
| **Xcode Dev Cleanup** | Simulator and device support cleanup | #53 | Planned |
| **Large File Finder** | Global scanner with protected-path exclusions | #51 | Planned |
| **Interactive TUI** | Terminal-based management console | #64 | Planned |
| **Action Service Layer** | Reusable engine for CLI and TUI | #61 | Shipped |
| **Quarantine Restore** | Metadata-backed "Undo" for cleanup | #62 | Shipped |
| **Hardening** | 0700 permissions and path anonymization | #59, #60 | Planned |
| **Supply Chain** | Record absolute tool paths in reports | #50 | Planned |

---

## Security & Privacy Invariants

These principles guide all development:

1. **Local-Only**: No data is uploaded; all processing is on-device.
2. **Reversibility**: Files are moved to quarantine with **0700 permissions** (#59).
3. **Restore Metadata**: Quarantine metadata is used to identify and restore items; durable action receipts remain a follow-up.
4. **Supply Chain Transparency**: Resolved binary paths are pinned and recorded in reports (#50).
5. **Guided Sudo**: Privilege escalation is never automated; mac-care provides verified commands for manual execution.
6. **Path Anonymization**: Reports can redact home directory paths for safe sharing (#60).
7. **Path Drift Protection**: Actions re-verify file metadata immediately before execution to prevent TOCTOU attacks (#49).

---

## OSS Tool Dependencies

| Tool | Usage | Risk Level |
|---|---|---|
| `dua` | Fast disk usage trees | `native/dua` |
| `brew` | Package cache cleanup | `auto_safe` |
| `docker` | Container/Image management | `review` |
| `pearcleaner` | Orphaned app file discovery | `review` |

---

## Known Constraints

- **Full Disk Access (FDA)**: Required for auditing Messages attachments, Mail, and TCC databases. Users must grant this via System Settings.
- **Python Runtime**: Requires 3.11+. No external `pip` dependencies are permitted for the core runtime to ensure zero-overhead installation.
- **TUI > Web UI**: For developer workflows, a Terminal UI is preferred over a local web server to minimize security surface area and context switching.
- **Fail-Safe Git**: If the `git` binary is missing or a repo check fails, the path is always treated as `protected`.

---

## Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-01 | Python CLI first | Get the engine working before any UI investment. |
| 2026-05-01 | Report-first | Primary value is visibility, not automation. |
| 2026-05-02 | Quarantine over rm | One-way door prevention; enable recovery. |
| 2026-05-03 | TUI over Web UI | Minimize security footprint; stay in dev workflow. |
| 2026-05-03 | Lightweight Pulses | Avoid CPU/battery drain of real-time file watchers. |
| 2026-05-03 | 0700 Quarantine | Prevent local snooping on quarantined sensitive files. |
| 2026-05-03 | Action Service Layer | Enable multiple interfaces (CLI/TUI) to share safety logic. |
