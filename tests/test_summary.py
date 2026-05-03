from mac_care.model import Finding, ToolStatus
from mac_care.summary import summarize_scan


def test_summarize_scan_groups_by_risk_and_size():
    summary = summarize_scan(
        [
            Finding("logs", "/tmp/logs", 100, "auto_safe", "old logs", "native"),
            Finding("docker", "/var/lib/docker", 300, "review", "reclaimable", "docker"),
            Finding("codex", "/tmp/codex", 200, "protected", "dirty repo", "native"),
            Finding("brew", "/tmp/brew", 50, "auto_safe", "brew cleanup", "brew"),
        ],
        [
            ToolStatus("git", "ok", "/usr/bin/git"),
            ToolStatus("docker", "review", "daemon unavailable"),
            ToolStatus("pearcleaner", "optional_missing", "not installed"),
        ],
        top_n=2,
    )

    assert summary.risks["auto_safe"].count == 2
    assert summary.risks["auto_safe"].size_bytes == 150
    assert summary.risks["review"].count == 1
    assert summary.risks["protected"].size_bytes == 200
    assert [finding.category for finding in summary.top_findings] == ["docker", "codex"]
    assert summary.tool_warning_count == 2


def test_summarize_scan_to_dict_is_json_ready():
    summary = summarize_scan(
        [Finding("logs", "/tmp/logs", 100, "auto_safe", "old logs", "native")],
        [],
    )

    payload = summary.to_dict()

    assert payload["risks"]["auto_safe"]["count"] == 1
    assert payload["top_findings"][0]["category"] == "logs"
