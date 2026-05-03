# mac-care Agent Instructions

## Project Goal

Build a free, local macOS maintenance tool for Deepankar's developer machine.

This project should replace the useful operational parts of CleanMyMac without copying its UI or building risky one-click cleanup behavior.

## Defaults

- Prefer report-first behavior over deletion.
- Never add broad `rm -rf` cleanup.
- Keep destructive actions behind explicit flags and dry-run output.
- Preserve developer work by default.
- Prefer integrating established free/open-source tools over rebuilding commodity scanners.
- Keep the CLI useful before adding any native or web UI.

## Protected Paths

Do not auto-delete these unless the user explicitly changes config:

- `~/.codex`
- `~/.agents`
- `~/multica`
- `~/multica_workspaces`
- `~/.vscode/extensions`
- browser extensions and native messaging hosts
- dirty git repositories or worktrees

## Architecture

- `src/mac_care/cli.py`: command routing
- `src/mac_care/scan.py`: scan-only cleanup findings
- `src/mac_care/doctor.py`: developer tool and environment checks
- `src/mac_care/clean.py`: safe cleanup orchestration
- `src/mac_care/report.py`: Markdown and JSON reports
- `src/mac_care/tools/`: wrappers for external OSS utilities

## Open-Source Utility Strategy

Use existing tools where practical:

- `gdu`, `ncdu`, `dust`, or `dua` for disk usage
- Homebrew for package cache/update checks
- Docker/OrbStack CLI for container cleanup reports
- Objective-See tools for security/persistence visibility
- Mole, ClearDisk, Pearcleaner, or similar tools only after scan-only evaluation

The custom code should focus on policy, scheduling, reporting, protected paths, and approval flow.
