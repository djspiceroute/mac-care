from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from mac_care.tools.docker_check import _parse_docker_size, docker_findings


# ---------------------------------------------------------------------------
# _parse_docker_size
# ---------------------------------------------------------------------------

def test_parse_gb() -> None:
    assert _parse_docker_size("9.789GB") == 9_789_000_000


def test_parse_mb() -> None:
    assert _parse_docker_size("197.6MB") == 197_600_000


def test_parse_with_percentage() -> None:
    # "9.789GB (49%)" — docker includes reclaimable percentage inline
    assert _parse_docker_size("9.789GB (49%)") == 9_789_000_000


def test_parse_zero() -> None:
    assert _parse_docker_size("0B") == 0


def test_parse_empty() -> None:
    assert _parse_docker_size("") == 0


def test_parse_kb() -> None:
    assert _parse_docker_size("1.227MB") == 1_227_000


# ---------------------------------------------------------------------------
# docker_findings — happy path
# ---------------------------------------------------------------------------

SAMPLE_DF = [
    {"Active": "10", "Reclaimable": "9.789GB (49%)", "Size": "19.7GB",  "TotalCount": "52", "Type": "Images"},
    {"Active": "5",  "Reclaimable": "1.227MB (2%)",  "Size": "47.05MB", "TotalCount": "11", "Type": "Containers"},
    {"Active": "5",  "Reclaimable": "197.6MB (13%)", "Size": "1.486GB", "TotalCount": "10", "Type": "Local Volumes"},
    {"Active": "0",  "Reclaimable": "4.982GB",        "Size": "5.098GB", "TotalCount": "91", "Type": "Build Cache"},
]


def _mock_df_run() -> MagicMock:
    result = MagicMock()
    result.returncode = 0
    result.stdout = "\n".join(json.dumps(row) for row in SAMPLE_DF) + "\n"
    return result


def _mock_info_run() -> MagicMock:
    result = MagicMock()
    result.returncode = 0
    result.stdout = ""
    return result


def test_docker_findings_returns_four_categories() -> None:
    with patch("mac_care.tools.docker_check._docker_available", return_value=True), \
         patch("mac_care.tools.docker_check._daemon_reachable", return_value=True), \
         patch("subprocess.run", return_value=_mock_df_run()):
        findings = docker_findings()

    assert len(findings) == 4
    categories = {f.category for f in findings}
    assert categories == {"docker_images", "docker_containers", "docker_volumes", "docker_build_cache"}


def test_docker_findings_all_review_risk() -> None:
    with patch("mac_care.tools.docker_check._docker_available", return_value=True), \
         patch("mac_care.tools.docker_check._daemon_reachable", return_value=True), \
         patch("subprocess.run", return_value=_mock_df_run()):
        findings = docker_findings()

    assert all(f.risk == "review" for f in findings)


def test_docker_findings_all_source_docker() -> None:
    with patch("mac_care.tools.docker_check._docker_available", return_value=True), \
         patch("mac_care.tools.docker_check._daemon_reachable", return_value=True), \
         patch("subprocess.run", return_value=_mock_df_run()):
        findings = docker_findings()

    assert all(f.source == "docker" for f in findings)


def test_docker_findings_sizes_are_reclaimable() -> None:
    with patch("mac_care.tools.docker_check._docker_available", return_value=True), \
         patch("mac_care.tools.docker_check._daemon_reachable", return_value=True), \
         patch("subprocess.run", return_value=_mock_df_run()):
        findings = docker_findings()

    by_cat = {f.category: f.size_bytes for f in findings}
    assert by_cat["docker_images"] == 9_789_000_000
    assert by_cat["docker_build_cache"] == 4_982_000_000


def test_docker_findings_reason_includes_hint() -> None:
    with patch("mac_care.tools.docker_check._docker_available", return_value=True), \
         patch("mac_care.tools.docker_check._daemon_reachable", return_value=True), \
         patch("subprocess.run", return_value=_mock_df_run()):
        findings = docker_findings()

    images = next(f for f in findings if f.category == "docker_images")
    assert "docker image prune" in images.reason


def test_docker_findings_skips_zero_reclaimable() -> None:
    rows = [{"Active": "5", "Reclaimable": "0B", "Size": "10GB", "TotalCount": "5", "Type": "Images"}]
    result = MagicMock()
    result.stdout = json.dumps(rows[0]) + "\n"
    with patch("mac_care.tools.docker_check._docker_available", return_value=True), \
         patch("mac_care.tools.docker_check._daemon_reachable", return_value=True), \
         patch("subprocess.run", return_value=result):
        findings = docker_findings()

    assert findings == []


# ---------------------------------------------------------------------------
# docker_findings — degradation
# ---------------------------------------------------------------------------

def test_docker_findings_empty_when_not_installed() -> None:
    with patch("mac_care.tools.docker_check._docker_available", return_value=False):
        assert docker_findings() == []


def test_docker_findings_empty_when_daemon_offline() -> None:
    with patch("mac_care.tools.docker_check._docker_available", return_value=True), \
         patch("mac_care.tools.docker_check._daemon_reachable", return_value=False):
        assert docker_findings() == []


def test_docker_findings_empty_on_timeout() -> None:
    import subprocess
    with patch("mac_care.tools.docker_check._docker_available", return_value=True), \
         patch("mac_care.tools.docker_check._daemon_reachable", return_value=True), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=30)):
        assert docker_findings() == []


def test_docker_findings_empty_on_bad_json() -> None:
    result = MagicMock()
    result.stdout = "not json at all\n"
    with patch("mac_care.tools.docker_check._docker_available", return_value=True), \
         patch("mac_care.tools.docker_check._daemon_reachable", return_value=True), \
         patch("subprocess.run", return_value=result):
        assert docker_findings() == []
