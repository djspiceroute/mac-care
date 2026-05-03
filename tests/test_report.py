import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mac_care.config import Config
from mac_care.model import Finding, ToolStatus
from mac_care.report import render_html, render_json, render_markdown, rotate_reports, write_reports


class ReportTests(unittest.TestCase):
    def test_render_markdown_groups_findings(self) -> None:
        output = render_markdown(
            [Finding("logs", "/tmp/logs", 1024, "auto_safe", "old logs")],
            [ToolStatus("git", "ok", "/usr/bin/git")],
        )

        self.assertIn("# Mac Care Report", output)
        self.assertIn("## Summary", output)
        self.assertIn("Tool warnings", output)
        self.assertIn("auto_safe", output)
        self.assertIn("logs", output)
        self.assertIn("git", output)

    def test_render_json_includes_summary(self) -> None:
        output = render_json(
            [Finding("logs", "/tmp/logs", 1024, "auto_safe", "old logs")],
            [ToolStatus("git", "ok", "/usr/bin/git")],
        )

        self.assertIn('"summary"', output)
        self.assertIn('"findings"', output)
        self.assertIn('"id"', output)

    def test_render_html_is_read_only_dashboard(self) -> None:
        output = render_html(
            [Finding("logs", "/tmp/<logs>", 1024, "auto_safe", "old logs")],
            [ToolStatus("git", "ok", "/usr/bin/git")],
        )

        self.assertIn("<title>Mac Care Report</title>", output)
        self.assertIn("Summary", output)
        self.assertIn("Top Findings", output)
        self.assertIn("/tmp/&lt;logs&gt;", output)
        self.assertNotIn("<button", output)

    def test_write_reports_creates_history_index(self) -> None:
        with TemporaryDirectory() as directory:
            reports_dir = Path(directory)
            config = Config(reports_dir=reports_dir, quarantine_dir=reports_dir / "quarantine")

            write_reports(
                config,
                [Finding("logs", "/tmp/logs", 1024, "auto_safe", "old logs")],
                [ToolStatus("git", "ok", "/usr/bin/git")],
            )

            self.assertTrue((reports_dir / "index.html").exists())


class RotateReportsTests(unittest.TestCase):
    def _make_report(self, reports_dir: Path, name: str, age_days: float) -> Path:
        f = reports_dir / name
        f.write_text("report", encoding="utf-8")
        mtime = time.time() - (age_days * 86400)
        os.utime(f, (mtime, mtime))
        return f

    def test_keeps_min_keep_regardless_of_age(self):
        with TemporaryDirectory() as directory:
            reports_dir = Path(directory)
            config = Config(
                reports_dir=reports_dir,
                quarantine_dir=reports_dir / "quarantine",
                retention_days=30,
                retention_min_keep=3,
            )
            # Create 3 very old reports
            for i in range(3):
                self._make_report(reports_dir, f"mac-care-2024-01-0{i+1}-120000.json", age_days=500)

            deleted = rotate_reports(config)

            assert deleted == 0
            assert len(list(reports_dir.glob("*.json"))) == 3

    def test_deletes_old_beyond_min_keep(self):
        with TemporaryDirectory() as directory:
            reports_dir = Path(directory)
            config = Config(
                reports_dir=reports_dir,
                quarantine_dir=reports_dir / "quarantine",
                retention_days=30,
                retention_min_keep=2,
            )
            # 2 recent + 3 old
            self._make_report(reports_dir, "mac-care-2026-05-01-120000.json", age_days=1)
            self._make_report(reports_dir, "mac-care-2026-04-30-120000.json", age_days=2)
            for i in range(3):
                self._make_report(reports_dir, f"mac-care-2025-01-0{i+1}-120000.json", age_days=400)

            deleted = rotate_reports(config)

            assert deleted == 3
            remaining = list(reports_dir.glob("*.json"))
            assert len(remaining) == 2

    def test_never_deletes_latest_html_or_index(self):
        with TemporaryDirectory() as directory:
            reports_dir = Path(directory)
            config = Config(
                reports_dir=reports_dir,
                quarantine_dir=reports_dir / "quarantine",
                retention_days=1,
                retention_min_keep=0,
            )
            latest = reports_dir / "latest.html"
            index = reports_dir / "index.html"
            latest.write_text("latest")
            index.write_text("index")
            old_mtime = time.time() - (400 * 86400)
            os.utime(latest, (old_mtime, old_mtime))
            os.utime(index, (old_mtime, old_mtime))

            rotate_reports(config)

            assert latest.exists()
            assert index.exists()

    def test_no_op_on_empty_directory(self):
        with TemporaryDirectory() as directory:
            config = Config(
                reports_dir=Path(directory),
                quarantine_dir=Path(directory) / "quarantine",
            )
            assert rotate_reports(config) == 0


if __name__ == "__main__":
    unittest.main()
