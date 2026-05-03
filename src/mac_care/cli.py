from __future__ import annotations

import argparse
from pathlib import Path

from .clean import safe_clean
from .config import Config
from .doctor import check_tools, recommend_tools
from .model import format_bytes
from .notification import notify_scan_complete
from .report import render_json, render_markdown, write_reports
from .review import approve_finding
from .scan import scan
from .scheduler import install_schedule, uninstall_schedule
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

    schedule_parser = subparsers.add_parser("schedule", help="Manage periodic launchd scans")
    schedule_subparsers = schedule_parser.add_subparsers(dest="schedule_action", required=True)
    install_parser = schedule_subparsers.add_parser("install", help="Install periodic scan launchd plist")
    install_parser.add_argument("--interval", type=int, default=24, help="Scan interval in hours")
    install_parser.add_argument("--dry-run", action="store_true", default=False, help="Print plist without writing files")
    uninstall_parser = schedule_subparsers.add_parser("uninstall", help="Uninstall periodic scan launchd plist")
    uninstall_parser.add_argument("--dry-run", action="store_true", default=False, help="Print planned removal without changing files")

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

    if args.command == "tools":
        if args.action == "recommend":
            return _tools_recommend()
        # default: status
        for status in check_tools(include_optional=True):
            print(f"{status.name}: {status.status} - {status.detail}")
        return 0

    if args.command == "schedule":
        if args.schedule_action == "install":
            result = install_schedule(config, interval_hours=args.interval, dry_run=args.dry_run)
            print(result.message)
            return 0
        if args.schedule_action == "uninstall":
            result = uninstall_schedule(dry_run=args.dry_run)
            print(result.message)
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
        if args.notify:
            notify_scan_complete(summary)
        return 0

    if args.command == "clean":
        actions = safe_clean(findings, config=config, dry_run=not args.execute)
        for action in actions:
            print(action)
        if not args.execute:
            print("Dry run only. No files were deleted.")
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
