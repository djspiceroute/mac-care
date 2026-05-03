from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .actions import preview_restore_action, restore_action
from .clean import safe_clean
from .compare import compare_reports, load_report_from_json, render_compare_json, render_compare_markdown, render_what_changed_cli, what_changed
from .config import Config
from .dashboard.app import MacCareDashboard
from .explain import explain_category, explain_finding
from .export import export_obsidian
from .history import load_history
from .privacy import TCC_DB, audit_privacy, check_fda, render_privacy_text
from .uninstall import UninstallResult, app_deletion_hint, discover_support_files, find_app, quarantine_finding, render_uninstall_report
from .doctor import check_tools, recommend_tools
from .model import Report, format_bytes
from .notification import notify_scan_complete
from .report import render_json, render_markdown, write_reports
from .review import approve_finding
from .scan import scan
from .scheduler import get_schedule_status, install_schedule, uninstall_schedule
from .summary import summarize_scan


def main() -> int:
    parser = argparse.ArgumentParser(prog="mac-care")
    parser.add_argument("--config", help="Path to config.toml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan cleanup opportunities and write reports")
    scan_parser.add_argument("--stdout", action="store_true", help="Print report to stdout instead of writing files")
    scan_parser.add_argument("--notify", action="store_true", help="Post a macOS notification after scan completes")
    scan_parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="markdown",
        help="Output format when --stdout is used",
    )
    subparsers.add_parser("doctor", help="Check developer tool health")

    dashboard_parser = subparsers.add_parser("dashboard", help="Interactive TUI dashboard for scan findings")
    dashboard_parser.add_argument("--report", help="Path to a mac-care JSON report (defaults to latest)")

    tools_parser = subparsers.add_parser("tools", help="OSS tool status and recommendations")
    tools_parser.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "recommend"],
        help="status: show installed/missing tools (default). recommend: show install hints for missing tools.",
    )

    clean_parser = subparsers.add_parser("clean", help="Run safe cleanup policy")
    clean_parser.add_argument("--safe", action="store_true", help="Only consider auto_safe findings")
    clean_parser.add_argument("--dry-run", action="store_true", default=True, help="Do not delete anything")
    clean_parser.add_argument("--execute", action="store_true", help="Move eligible auto_safe findings to quarantine")
    clean_parser.add_argument("--purge", action="store_true", help="Permanently delete all auto_safe findings (no quarantine, requires confirmation)")

    schedule_parser = subparsers.add_parser("schedule", help="Manage periodic launchd scans")
    schedule_subparsers = schedule_parser.add_subparsers(dest="schedule_action", required=True)
    schedule_subparsers.add_parser("status", help="Show current schedule status and pinned executable")
    install_parser = schedule_subparsers.add_parser("install", help="Install periodic scan launchd plist")
    install_parser.add_argument("--interval", type=int, default=24, help="Scan interval in hours")
    install_parser.add_argument("--dry-run", action="store_true", default=False, help="Print plist without writing files")
    uninstall_parser = schedule_subparsers.add_parser("uninstall", help="Uninstall periodic scan launchd plist")
    uninstall_parser.add_argument("--dry-run", action="store_true", default=False, help="Print planned removal without changing files")

    uninstall_parser = subparsers.add_parser("uninstall", help="Find and quarantine support files for a deleted/unwanted app")
    uninstall_parser.add_argument("app_name", help="App name (e.g. Zoom, Slack)")
    uninstall_parser.add_argument("--dry-run", action="store_true", default=True, help="Show what would be quarantined (default)")
    uninstall_parser.add_argument("--execute", action="store_true", help="Quarantine discovered support files")

    quarantine_parser = subparsers.add_parser("quarantine", help="Manage quarantined items")
    quarantine_subparsers = quarantine_parser.add_subparsers(dest="quarantine_action", required=True)
    restore_parser = quarantine_subparsers.add_parser("restore", help="Restore a quarantined item by ID or path")
    restore_parser.add_argument("identifier", help="Finding ID, metadata path, original path, or quarantined item path")
    restore_parser.add_argument("--dry-run", action="store_true", default=True, help="Preview restore without moving files")
    restore_parser.add_argument("--execute", action="store_true", help="Move the quarantined item back to its original path")

    audit_parser = subparsers.add_parser("audit", help="Security and privacy audits")
    audit_subparsers = audit_parser.add_subparsers(dest="audit_action", required=True)
    audit_subparsers.add_parser("privacy", help="List macOS TCC permissions granted to apps")

    export_parser = subparsers.add_parser("export", help="Export scan results to external formats")
    export_parser.add_argument("--format", choices=["obsidian"], required=True, help="Export format")
    export_parser.add_argument("--vault-path", help="Obsidian vault path (overrides config)")

    compare_parser = subparsers.add_parser("compare", help="Diff two scan JSON reports")
    compare_parser.add_argument("report1", help="Path to first (older) JSON report")
    compare_parser.add_argument("report2", help="Path to second (newer) JSON report")
    compare_parser.add_argument(
        "--format", choices=["markdown", "json"], default="markdown",
        help="Output format (default: markdown)",
    )

    explain_parser = subparsers.add_parser("explain", help="Explain the rationale behind a finding or category")
    explain_parser.add_argument("identifier", help="Finding ID or category name")
    explain_parser.add_argument("--report", help="Path to a mac-care JSON report (defaults to latest)")

    review_parser = subparsers.add_parser("review", help="Approve review-risk findings from a report")
    review_subparsers = review_parser.add_subparsers(dest="review_action", required=True)
    approve_parser = review_subparsers.add_parser("approve", help="Approve one review-risk finding by ID")
    approve_parser.add_argument("--report", required=True, help="Path to a mac-care JSON report")
    approve_parser.add_argument("--finding-id", required=True, help="Stable finding ID from the report")
    approve_parser.add_argument("--dry-run", action="store_true", default=True, help="Preview the approval action")
    approve_parser.add_argument("--execute", action="store_true", help="Move the approved finding to quarantine")

    args = parser.parse_args()
    config = Config.load(args.config)

    if args.command == "doctor":
        for status in check_tools():
            print(f"{status.name}: {status.status} - {status.detail}")
        return 0

    if args.command == "dashboard":
        report_path = Path(args.report) if args.report else None
        if report_path is None:
            history = load_history(config.reports_dir)
            if history:
                report_path = history[0].json_path
        if not report_path or not report_path.exists():
            print("Error: No report found. Run 'mac-care scan' first.", file=sys.stderr)
            return 1
        delta = None
        try:
            history = load_history(config.reports_dir)
            if len(history) >= 2:
                prev = load_report_from_json(history[1].json_path)
                curr = load_report_from_json(report_path)
                delta = what_changed(prev, curr)
        except (OSError, KeyError, json.JSONDecodeError):
            pass
        MacCareDashboard(report_path, delta=delta).run()
        return 0

    if args.command == "tools":
        if args.action == "recommend":
            return _tools_recommend()
        # default: status
        for status in check_tools(include_optional=True):
            print(f"{status.name}: {status.status} - {status.detail}")
        return 0

    if args.command == "schedule":
        if args.schedule_action == "status":
            result = get_schedule_status()
            print(result.message)
            return 0
        if args.schedule_action == "install":
            result = install_schedule(config, interval_hours=args.interval, dry_run=args.dry_run)
            print(result.message)
            return 0
        if args.schedule_action == "uninstall":
            result = uninstall_schedule(dry_run=args.dry_run)
            print(result.message)
            return 0

    if args.command == "uninstall":
        app_path = find_app(args.app_name)
        support_files = discover_support_files(app_path) if app_path else []
        hint = app_deletion_hint(app_path) if app_path else ""
        result = UninstallResult(app_path=app_path, support_files=support_files, app_hint=hint)
        print(render_uninstall_report(result))
        if args.execute and support_files:
            print()
            run_id = None
            for finding in support_files:
                msg = quarantine_finding(finding, config, run_id=run_id)
                print(msg)
        elif not args.execute and support_files:
            print("\nDry run only. Run with --execute to quarantine support files.")
        return 0

    if args.command == "quarantine":
        if args.quarantine_action == "restore":
            result = (
                restore_action(config, args.identifier)
                if args.execute
                else preview_restore_action(config, args.identifier)
            )
            print(result.render())
            if not args.execute:
                print("Dry run only. No files were moved.")
            return 0

    if args.command == "audit" and args.audit_action == "privacy":
        if not check_fda():
            print(
                "Error: mac-care cannot read the TCC database.\n"
                "Grant Full Disk Access in:\n"
                "  System Settings → Privacy & Security → Full Disk Access\n"
                f"TCC database path: {TCC_DB}",
                file=sys.stderr,
            )
            return 1
        entries = audit_privacy()
        print(render_privacy_text(entries))
        return 0

    if args.command == "export":
        vault = Path(args.vault_path).expanduser() if args.vault_path else config.obsidian_vault_path
        if vault is None:
            print("Error: --vault-path is required (or set obsidian_vault_path in config.toml)", file=sys.stderr)
            return 1
        try:
            print(export_obsidian(config.reports_dir, vault))
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    if args.command == "compare":
        summary = compare_reports(Path(args.report1), Path(args.report2))
        if args.format == "json":
            print(render_compare_json(summary))
        else:
            print(render_compare_markdown(summary, Path(args.report1), Path(args.report2)))
        return 0

    if args.command == "explain":
        report_path = None
        if args.report:
            report_path = Path(args.report)
        else:
            history = load_history(config.reports_dir)
            if history:
                report_path = history[0].json_path

        # If it looks like a finding ID (hex, length 16) and we have a report, try explain_finding
        is_id = len(args.identifier) == 16 and all(c in "0123456789abcdef" for c in args.identifier.lower())
        
        if is_id and report_path:
            print(explain_finding(args.identifier, report_path))
        else:
            # Fallback to category explanation
            print(explain_category(args.identifier))
        return 0

    if args.command == "review":
        if args.review_action == "approve":
            print(
                approve_finding(
                    Path(args.report),
                    args.finding_id,
                    config,
                    dry_run=not args.execute,
                )
            )
            if not args.execute:
                print("Dry run only. No files were moved.")
            return 0

    findings = scan(config)
    tools = check_tools()

    if args.command == "scan":
        summary = summarize_scan(findings, tools)
        if args.stdout:
            if args.format == "json":
                print(render_json(findings, tools))
            else:
                print(render_markdown(findings, tools))
            if args.notify:
                notify_scan_complete(summary)
            return 0

        md_path, json_path, html_path = write_reports(config, findings, tools)
        total = sum(item.size_bytes for item in findings)
        review = summary.risks["review"]
        auto_safe = summary.risks["auto_safe"]
        protected = summary.risks["protected"]
        print(
            "Scanned "
            f"{len(findings)} findings, {format_bytes(total)} observed "
            f"({auto_safe.count} auto_safe / {review.count} review / {protected.count} protected; "
            f"{summary.tool_warning_count} tool warnings)."
        )
        print(f"Markdown report: {md_path}")
        print(f"JSON report: {json_path}")
        print(f"HTML report: {html_path}")

        try:
            history = load_history(config.reports_dir)
            if len(history) >= 2:
                prev_report = load_report_from_json(history[1].json_path)
                curr_report = Report(findings=findings, tools=tools)
                delta = what_changed(prev_report, curr_report)
                print()
                print(render_what_changed_cli(delta))
        except (OSError, KeyError, json.JSONDecodeError, AttributeError):
            pass

        if args.notify:
            notify_scan_complete(summary)
        return 0

    if args.command == "clean":
        output = sys.stdout

        if args.purge:
            auto_safe = [f for f in findings if f.risk == "auto_safe"]
            if not auto_safe:
                print("No auto_safe findings to purge.", file=output)
                return 0
            total = sum(f.size_bytes for f in auto_safe)
            print(
                f"About to permanently delete {len(auto_safe)} auto_safe findings ({format_bytes(total)}). "
                f"This cannot be undone.",
                file=output,
            )
            confirm = input("Continue? [y/N] ").strip().lower()
            if confirm != "y":
                print("Aborted.", file=output)
                return 0
            actions = safe_clean(findings, config=config, dry_run=False, purge=True)
            for action in actions:
                print(action, file=output)
            purged = [a for a in actions if a.startswith("purged ")]
            purged_size = sum(
                f.size_bytes for f in auto_safe if any(f.path in a for a in purged)
            )
            print(f"\nPurge complete. {len(purged)} item(s) permanently deleted ({format_bytes(purged_size)}).", file=output)
            return 0

        actions = safe_clean(findings, config=config, dry_run=not args.execute)
        for action in actions:
            print(action, file=output)
        if not args.execute:
            print("Dry run only. No files were deleted.", file=output)
        else:
            quarantined = [a for a in actions if a.startswith("quarantined ")]
            if quarantined:
                total_size = sum(
                    f.size_bytes for f in findings
                    if f.risk == "auto_safe" and any(f.path in a for a in quarantined)
                )
                print(
                    f"Execute complete. {len(quarantined)} item(s) quarantined ({format_bytes(total_size)}).",
                    file=output,
                )
            else:
                print("No actionable auto_safe findings found.", file=output)
        return 0

    parser.error("unknown command")
    return 2


def _tools_recommend() -> int:
    recs = recommend_tools()
    if not recs:
        print("All recommended OSS tools are already installed.")
        return 0

    # Group by function
    groups: dict[str, list[dict]] = {}
    for rec in recs:
        groups.setdefault(rec["group"], []).append(rec)

    print("Recommended OSS tools to install:\n")
    for group, items in groups.items():
        print(f"  {group}:")
        for item in items:
            print(f"    {item['name']:<14}  {item['desc']}")
            print(f"    {'':14}  → {item['install']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
