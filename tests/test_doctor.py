from __future__ import annotations

from unittest.mock import patch

from mac_care.doctor import recommend_tools, TOOL_RECOMMENDATIONS


def test_recommend_tools_returns_missing_only() -> None:
    """Only tools not on PATH should appear in recommendations."""
    with patch("mac_care.doctor.which", return_value=None):
        recs = recommend_tools()

    names = {r["name"] for r in recs}
    assert names == set(TOOL_RECOMMENDATIONS.keys())


def test_recommend_tools_excludes_installed() -> None:
    """A tool that is installed should not appear in recommendations."""
    def fake_which(name: str) -> str | None:
        return f"/usr/local/bin/{name}" if name == "dua" else None

    with patch("mac_care.doctor.which", side_effect=fake_which):
        recs = recommend_tools()

    names = {r["name"] for r in recs}
    assert "dua" not in names


def test_recommend_tools_empty_when_all_installed() -> None:
    with patch("mac_care.doctor.which", return_value="/usr/local/bin/tool"):
        recs = recommend_tools()
    assert recs == []


def test_recommend_tools_has_required_keys() -> None:
    with patch("mac_care.doctor.which", return_value=None):
        recs = recommend_tools()
    for rec in recs:
        assert "name" in rec
        assert "group" in rec
        assert "desc" in rec
        assert "install" in rec
        assert "status" in rec


def test_recommend_tools_install_commands_start_with_brew() -> None:
    with patch("mac_care.doctor.which", return_value=None):
        recs = recommend_tools()
    for rec in recs:
        assert rec["install"].startswith("brew "), f"{rec['name']} install hint should start with 'brew'"
