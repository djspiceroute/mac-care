# mac-care Architecture

## Design Philosophy

mac-care is an **orchestrator and health console**, not just a cleaner. It calls trusted OSS tools, parses their output into a unified data model, and applies a developer-centric policy layer.

The architecture is designed around **Transparency, Reversibility, and Visibility**.

---

## Data & Action Flow (Phase 2)

```
User / Scheduler
     │
     ▼
[ Interactive UI / CLI / Watcher ]
     │
     ├── mac_care.scan.scan()         → Discovery (list[Finding])
     │                                  │
     ▼                                  ▼
[ Action Service Layer ] ◀─────── [ State Store ] (~/.mac-care/state.json)
     │                                  │
     ├── quarantine_finding()           │
     ├── purge_finding()                │
     └── restore_finding()        ◀─────┘ (via ~/.mac-care/receipts/)
              │
              ▼
    [ File System Action ]
```

---

## Service Layer & State Management

### `ActionService` (Proposed)
Phase 2 extracts action logic (quarantine, purge, restore) from `cli.py` into a reusable service. This allows the CLI, a TUI (Terminal UI), and background tasks to share the same safety gates and logic.

### State Store (`state.json`)
Instead of relying solely on timestamped reports, `mac-care` maintains a "current state" cache. This store tracks:
- Last scan results.
- Pending review approvals.
- Active quarantine runs.
- Tool health status.

### Action Receipts & Restore
Every destructive action (even to quarantine) generates an **Action Receipt**.
- **Location**: `~/.mac-care/receipts/<run_id>/<finding_id>.json`
- **Content**: Original path, destination path, size, hash, and timestamp.
- **Restore**: The `restore` command uses these receipts to move files back to their original location, handling path conflicts safely.

---

## Module Boundaries

### `model.py`
Pure data types (Finding, ToolStatus, ScanSummary). No I/O. Importing this never has side effects.

### `scan.py`
The read-only orchestrator. Calls all scanner functions and returns `list[Finding]`. Applies the git safety gate to workspace paths.
**Invariant:** Never modifies the filesystem.

### `clean.py` (Evolving to Action Service)
Orchestrates the transition from finding to quarantine or purge. 
- Re-checks `is_protected` and `git_safety` immediately before execution.
- **New for Phase 2:** Path-drift detection. If a file has changed size or type since the scan, the action is aborted.

### `doctor.py`
Checks required developer tools, optional OSS integrations, Homebrew PATH, and Docker daemon reachability.

### `git_safety.py`
Detects dirty or active git repos under a path. Used as a safety gate to protect active work.

### `safety.py`
Centralized protection logic. Checks `config.protected_paths`, git state, and system-protected locations.

### `ids.py`
Computes stable finding IDs derived from the finding's **structural identity** (category + path + risk + source).

### `report.py`
Generates human-readable (MD, HTML) and machine-readable (JSON) artifacts. Manages report rotation.

### `privacy.py` & `security.py`
Specialized audit modules. `privacy.py` handles TCC database reads (requires FDA); `security.py` (Phase 2) handles persistence auditing (LaunchAgents/Daemons).

### `uninstall.py`
App-specific discovery. Pairs bundle identification with support-file discovery via Pearcleaner or native patterns.

### `compare.py`
Diffs two JSON reports to show new, resolved, or changed findings.

### `export.py`
Exports scan summaries to external formats (e.g., Obsidian).

---

## tools/ — OSS Wrappers

Every file in `tools/` follows a strict contract:
1. **Check if the tool is installed** before calling subprocess.
2. **Return `[]` on any failure** — degradation is always silent.
3. **No inline subprocess calls outside `tools/`**.
4. **Independently testable** via mocks.

---

## Safety Invariants

1. **Dry-Run by Default**: All destructive commands default to no-op.
2. **Quarantine First**: Items are moved to `~/.mac-care/quarantine/` with `0700` permissions.
3. **Git Safety Gate**: Active/dirty repos are never touched.
4. **Supply Chain Transparency**: Reports record absolute paths of every external binary invoked.
5. **Path Drift Protection**: Actions are aborted if the filesystem has changed since the scan.
6. **No Automated Sudo**: Elevated actions provide copy-paste guidance instead of automated execution.
