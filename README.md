# mac-care

Local macOS maintenance for a developer machine.

`mac-care` is not a CleanMyMac clone. It is a small local coordinator that:

- scans cleanup opportunities
- checks developer tool health
- generates Markdown and JSON reports
- separates safe cleanup from review-only cleanup
- leaves room to integrate good free/open-source utilities instead of rebuilding everything

The first version is report-first. Deletion is dry-run by default.

## Commands

```bash
mac-care scan
mac-care doctor
mac-care clean --safe --dry-run
mac-care tools
```

## Policy

Auto-clean candidates are intentionally conservative:

- old user logs
- old cache files
- old temp files
- Homebrew cache
- Xcode DerivedData

Review-only candidates include:

- old Codex workspaces
- git worktrees
- app leftovers
- Docker volumes
- browser data
- LaunchAgents and background items

Protected by default:

- `~/.codex`
- `~/.agents`
- `~/multica`
- `~/multica_workspaces`
- active or dirty git repositories
- VS Code extensions
- browser extensions

## Open-Source Utility Strategy

`mac-care` should wrap and coordinate existing tools when they are good:

- `gdu`, `ncdu`, `dust`, or `dua` for disk usage inspection
- Homebrew for package cache and update checks
- Docker/OrbStack CLI for container cleanup reporting
- Objective-See tools for security and persistence visibility
- Mole, ClearDisk, Pearcleaner, or similar tools after scan-only evaluation

The custom value is the policy layer: scheduling, reports, protected paths, review gates, and machine-specific rules.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
mac-care scan
```
