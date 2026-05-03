# Dashboard Action Backend Safety Model

This document defines the safety contract for any future local dashboard backend.

The current HTML dashboard is static and read-only. It must stay that way until this backend contract is implemented and tested.

## Goals

- Let a local report UI preview approved actions for known findings.
- Preserve the CLI/report engine as the source of truth.
- Prevent remote access, arbitrary command execution, and accidental cleanup.
- Keep destructive behavior impossible until quarantine execution exists.

## Network Boundary

- Bind only to `127.0.0.1`.
- Never bind to `0.0.0.0`, LAN interfaces, or public addresses.
- Use an unpredictable session token in the dashboard URL.
- Reject every request that does not include the active token.
- Generate a new token every time the backend starts.
- Do not persist tokens to disk.

## Input Model

The backend may only accept stable finding IDs that come from a known mac-care report.

Allowed input:

- report ID or report path under `config.reports_dir`
- finding ID from that report
- explicit action name from an allowlist

Rejected input:

- arbitrary filesystem paths from the browser
- arbitrary shell commands
- URLs
- environment variable overrides
- unrecognized action names

## Action Phases

### Phase 1: Preview Only

The first backend implementation must be preview-only.

Allowed actions:

- list reports
- list findings
- show finding details
- show planned CLI-equivalent action
- open report files

Disallowed actions:

- move files
- delete files
- run cleanup
- invoke Docker/Pearcleaner cleanup
- modify launchd jobs

### Phase 2: Quarantine Only

After quarantine execution exists, the backend may call the same internal quarantine path as the CLI.

Requirements:

- require a confirmation request separate from preview
- accept only `auto_safe` findings unless review approval flow exists
- re-check protected paths immediately before action
- re-check git safety immediately before workspace-adjacent action
- move to `config.quarantine_dir`, never delete directly
- write an action log entry with original path, quarantine path, timestamp, risk, source, and report ID

### Phase 3: Review Approval

Review-risk findings may be actioned only after the review approval flow exists.

Requirements:

- approve individual finding IDs, not categories
- show exact planned move before execution
- never act on `protected` findings
- keep Docker, browser data, and app leftovers review-only

## Required Re-checks

The backend must not trust report data alone.

Before any action preview or execution:

- load the referenced report from `config.reports_dir`
- verify the finding ID exists in that report
- verify the path is still under the finding
- re-run protected path checks
- re-run git safety checks for workspace-adjacent categories
- reject stale reports if the finding path no longer exists or has changed in a way that invalidates the plan

## Endpoint Shape

Initial preview-only endpoints:

```text
GET  /reports
GET  /reports/{report_id}
GET  /reports/{report_id}/findings/{finding_id}
POST /reports/{report_id}/findings/{finding_id}/preview
```

Future quarantine endpoints:

```text
POST /reports/{report_id}/findings/{finding_id}/quarantine-preview
POST /reports/{report_id}/findings/{finding_id}/quarantine-confirm
```

All endpoints require the session token.

## Non-goals

- No remote dashboard.
- No cloud sync.
- No arbitrary command runner.
- No direct permanent delete.
- No cleanup from notification actions.
- No browser session cleanup until a separate privacy-specific review flow exists.
