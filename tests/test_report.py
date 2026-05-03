import unittest

from mac_care.model import Finding, ToolStatus
from mac_care.report import render_json, render_markdown


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


if __name__ == "__main__":
    unittest.main()
