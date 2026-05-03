import json

from mac_care.history import load_history, render_history_index, write_history_index


def _write_report(path, generated_at="2026-05-02T21:08:26", auto_safe_size=1024):
    path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "summary": {
                    "risks": {
                        "auto_safe": {"count": 1, "size_bytes": auto_safe_size},
                        "review": {"count": 2, "size_bytes": 2048},
                        "protected": {"count": 0, "size_bytes": 0},
                    },
                    "top_findings": [],
                    "tool_warning_count": 3,
                },
                "findings": [],
                "tools": [],
            }
        ),
        encoding="utf-8",
    )


def test_load_history_skips_malformed_reports(tmp_path):
    _write_report(tmp_path / "mac-care-2026-05-02-210000.json")
    (tmp_path / "mac-care-bad.json").write_text("{not json", encoding="utf-8")

    entries = load_history(tmp_path)

    assert len(entries) == 1
    assert entries[0].risk_counts["auto_safe"] == 1
    assert entries[0].tool_warning_count == 3


def test_render_history_index_links_latest_and_reports(tmp_path):
    _write_report(tmp_path / "mac-care-2026-05-02-210000.json")
    (tmp_path / "mac-care-2026-05-02-210000.md").write_text("# Report", encoding="utf-8")
    (tmp_path / "latest.html").write_text("<html></html>", encoding="utf-8")

    output = render_history_index(tmp_path)

    assert "Mac Care Report History" in output
    assert "Open latest dashboard" in output
    assert "mac-care-2026-05-02-210000.json" in output
    assert "mac-care-2026-05-02-210000.md" in output
    assert "1.0 KB (1)" in output


def test_write_history_index_creates_index(tmp_path):
    _write_report(tmp_path / "mac-care-2026-05-02-210000.json")

    path = write_history_index(tmp_path)

    assert path == tmp_path / "index.html"
    assert path.exists()
    assert "Mac Care Report History" in path.read_text(encoding="utf-8")
