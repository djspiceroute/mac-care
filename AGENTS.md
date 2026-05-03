# mac-care Agent Instructions

## Project Goal

Build a free, local macOS maintenance CLI for developer machines.

This project replaces the useful operational parts of CleanMyMac without copying its UI or building risky one-click cleanup behaviour.

## Source of Truth

Use this priority order when instructions conflict:
1. Direct user instruction
2. This `AGENTS.md`
3. GitHub Issues (`https://github.com/djspiceroute/mac-care/issues`)
4. Existing code patterns
5. Tool or framework defaults

## Defaults

- Prefer report-first behaviour over deletion.
- Never add broad `rm -rf` cleanup.
- Keep destructive actions behind explicit flags and dry-run output.
- Preserve developer work by default.
- Prefer integrating established free/open-source tools over rebuilding commodity scanners.
- Keep the CLI useful before adding any native or web UI.

## Protected Paths

Do not auto-delete these unless the user explicitly changes config:

- `~/.vscode/extensions`
- `~/.ssh`
- Browser native messaging hosts (Chrome, Firefox)
- Dirty or active git repositories or worktrees

## Architecture

- `src/mac_care/cli.py`: command routing
- `src/mac_care/scan.py`: scan-only cleanup findings
- `src/mac_care/doctor.py`: developer tool and environment checks
- `src/mac_care/clean.py`: safe cleanup orchestration
- `src/mac_care/report.py`: Markdown and JSON reports
- `src/mac_care/git_safety.py`: git repo / worktree safety gate
- `src/mac_care/scheduler.py`: launchd schedule install/uninstall
- `src/mac_care/tools/`: wrappers for external OSS utilities
  - `brew.py`: Homebrew cleanup findings
  - `disk.py`: dua/dust disk tree integration
  - `docker_check.py`: Docker disk usage findings
  - `pearcleaner.py`: orphaned app support file findings

## Open-Source Utility Strategy

mac-care is an orchestrator, not a scanner. Use existing tools where practical and parse their output into `Finding` objects. Write policy, scheduling, reporting, protected paths, and approval flow — not commodity scanners.

Preferred tools:
- `dua` (primary) / `dust` / `gdu` / `ncdu` for disk usage trees
- `brew cleanup --dry-run` for Homebrew cache analysis
- `docker system df` for container/image/volume waste
- `pearcleaner list-orphaned` for orphaned app support files
- Objective-See tools (KnockKnock) for security/persistence visibility — future

Each wrapper in `tools/` must:
1. Check if the tool is installed (`shutil.which`) before calling it
2. Degrade gracefully — return `[]` if the tool is absent, never raise
3. Never inline `subprocess` calls outside `tools/`
4. Be independently testable with mocked subprocess output

## Branch Naming

Always prefix with agent identity, lowercase, followed by a slash and short descriptor:

```
claude/git-safety
claude/brew-integration
codex/docker-findings
```

Never create a branch without an agent prefix unless the user explicitly requests it.

## Git Workflow

- Work on a branch — never commit directly to `main`
- Use git worktrees for multi-file items to keep work isolated:
  ```bash
  git worktree add ../mac-care-<agent>-<task> -b <agent>/<task>
  ```
- Rebase on `main` before opening a PR:
  ```bash
  git fetch origin && git rebase origin/main
  ```
- **Local commits are allowed after each item passes tests** — no need to ask
- **Never push without explicit user instruction**
- Never force-push `main`
- Remove worktrees after branch is merged:
  ```bash
  git worktree remove ../mac-care-<agent>-<task>
  ```

## Commit Message Convention

Use Conventional Commits format:
```
feat(scan): add brew cleanup integration
fix(doctor): handle missing PATH for homebrew
test(git_safety): add dirty-repo detection tests
chore(infra): add GitHub Actions test workflow
docs(agents): update architecture and git policies
```

Types: `feat`, `fix`, `test`, `chore`, `docs`, `refactor`

## Standard Workflow

1. Read `AGENTS.md` and relevant source files before starting
2. Confirm scope — escalate if ambiguous rather than guessing
3. Implement the narrowest change that fully solves the problem
4. Run `python -m pytest tests/` — do not claim validation without running it
5. Update docs if behaviour, setup, or contracts changed
6. Summarise: what changed / files touched / validation performed / risks / next steps

## Testing Rules

- Every new module gets at least one unit test
- Every new `tools/` module must have at least one degradation test (tool missing, timeout, OSError)
- Tests never touch the real filesystem — use `tmp_path` (pytest) or `tempfile`
- Tests never call real external tools — mock all `subprocess` calls
- Mock target is always the module's own import (e.g. `mac_care.doctor.which`, not `shutil.which`)
- Tests must run in under 5 seconds total
- Clearly state when tests could not run and why

## Dependency Rules

Only add a Python dependency to `pyproject.toml` if all are true:
1. The stdlib cannot reasonably solve the task
2. It materially reduces complexity
3. It is mature and well-maintained
4. The maintenance cost is justified

If added, justify it in the PR body. External binaries (`brew`, `dua`, `docker`, etc.) are not Python dependencies — they are optional integrations.

## Safety Rules

- `dry_run=True` is the default for all clean operations
- Protected paths are checked before every action, not just at scan time
- Never `rm -rf` — quarantine dir (`~/Documents/MacCare/quarantine/`) is the deletion target
- Git safety gate (`git_safety.py`) must run before any action touching workspace directories
- `auto_safe` is the only risk level eligible for automated cleanup — `review` always requires human approval

## GitHub Issue Convention

Title format: `type(scope): Short action-oriented summary`

Types: `epic`, `story`, `enabler`, `bug`

Required body sections:
```markdown
## Description
## Acceptance Criteria
- [ ]
## Non-goals
## Parent
```

Labels: type label + priority (`P0`–`P3`) + scope label (`scan`, `clean`, `doctor`, `tools`, `report`, `infra`, `schedule`)

## Escalation Rules

Escalate instead of guessing when:
- Requirements are ambiguous
- Multiple architectural paths are plausible
- A change may have irreversible impact
- Critical assumptions cannot be verified

State: what is unclear / viable options / the blocked assumption.

## Final Response Format

After completing any item, include:
1. What changed
2. Files touched
3. Validation performed
4. Limitations / risks
5. Recommended next steps

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **mac-care** (460 symbols, 726 relationships, 26 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/mac-care/context` | Codebase overview, check index freshness |
| `gitnexus://repo/mac-care/clusters` | All functional areas |
| `gitnexus://repo/mac-care/processes` | All execution flows |
| `gitnexus://repo/mac-care/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
