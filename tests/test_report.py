import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mac_care.config import Config
from mac_care.model import Finding, ToolStatus
from mac_care.report import render_html, render_json, render_markdown, write_reports


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


if __name__ == "__main__":
    unittest.main()
