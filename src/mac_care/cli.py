from __future__ import annotations

import argparse

from .clean import safe_clean
from .config import Config
from .doctor import check_tools
from .model import format_bytes
from .report import write_reports
from .scan import scan


def main() -> int:
    parser = argparse.ArgumentParser(prog="mac-care")
    parser.add_argument("--config", help="Path to config.toml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scan", help="Scan cleanup opportunities and write reports")
    subparsers.add_parser("doctor", help="Check developer tool health")
    subparsers.add_parser("tools", help="Show required and optional tool status")

    clean_parser = subparsers.add_parser("clean", help="Run safe cleanup policy")
    clean_parser.add_argument("--safe", action="store_true", help="Only consider auto_safe findings")
    clean_parser.add_argument("--dry-run", action="store_true", default=True, help="Do not delete anything")

    args = parser.parse_args()
    config = Config.load(args.config)

    if args.command == "doctor":
        for status in check_tools():
            print(f"{status.name}: {status.status} - {status.detail}")
        return 0

    if args.command == "tools":
        for status in check_tools(include_optional=True):
            print(f"{status.name}: {status.status} - {status.detail}")
        return 0

    findings = scan(config)
    tools = check_tools()

    if args.command == "scan":
        md_path, json_path = write_reports(config, findings, tools)
        total = sum(item.size_bytes for item in findings)
        print(f"Scanned {len(findings)} findings, {format_bytes(total)} observed.")
        print(f"Markdown report: {md_path}")
        print(f"JSON report: {json_path}")
        return 0

    if args.command == "clean":
        actions = safe_clean(findings, dry_run=args.dry_run)
        for action in actions:
            print(action)
        if args.dry_run:
            print("Dry run only. No files were deleted.")
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
