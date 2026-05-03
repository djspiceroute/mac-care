from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from mac_care.tools.pearcleaner import _guess_app_name, pearcleaner_findings


# ---------------------------------------------------------------------------
# _guess_app_name
# ---------------------------------------------------------------------------

def test_guess_app_name_bundle_id_dir(tmp_path: Path) -> None:
    path = tmp_path / "com.example.MyApp"
    path.mkdir()
    assert _guess_app_name(path) == "com.example.MyApp"


def test_guess_app_name_plist_file(tmp_path: Path) -> None:
    path = tmp_path / "com.example.MyApp.plist"
    path.touch()
    assert _guess_app_name(path) == "com.example.MyApp"


def test_guess_app_name_strips_leading_dot(tmp_path: Path) -> None:
    path = tmp_path / ".hidden-app-support"
    path.mkdir()
    assert _guess_app_name(path) == "hidden-app-support"


# ---------------------------------------------------------------------------
# pearcleaner_findings — happy path
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
/Users/user/Library/Application Support/com.example.DeletedApp
/Users/user/Library/Caches/com.example.DeletedApp
/Users/user/Library/Preferences/com.example.DeletedApp.plist

Found 3 orphaned files.
"""


def _mock_run(stdout: str, returncode: int = 0) -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    return result


def test_pearcleaner_findings_parses_paths() -> None:
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value="/usr/local/bin/pearcleaner"), \
         patch("subprocess.run", return_value=_mock_run(SAMPLE_OUTPUT)), \
         patch("mac_care.tools.pearcleaner.path_size", return_value=1024):
        findings = pearcleaner_findings()

    assert len(findings) == 3
    paths = {f.path for f in findings}
    assert "/Users/user/Library/Application Support/com.example.DeletedApp" in paths
    assert "/Users/user/Library/Caches/com.example.DeletedApp" in paths
    assert "/Users/user/Library/Preferences/com.example.DeletedApp.plist" in paths


def test_pearcleaner_findings_skips_summary_line() -> None:
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value="/usr/local/bin/pearcleaner"), \
         patch("subprocess.run", return_value=_mock_run(SAMPLE_OUTPUT)), \
         patch("mac_care.tools.pearcleaner.path_size", return_value=0):
        findings = pearcleaner_findings()

    # Summary line "Found 3 orphaned files." must not become a Finding
    assert all("Found" not in f.path for f in findings)


def test_pearcleaner_findings_all_review_risk() -> None:
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value="/usr/local/bin/pearcleaner"), \
         patch("subprocess.run", return_value=_mock_run(SAMPLE_OUTPUT)), \
         patch("mac_care.tools.pearcleaner.path_size", return_value=0):
        findings = pearcleaner_findings()

    assert all(f.risk == "review" for f in findings)


def test_pearcleaner_findings_source_is_pearcleaner() -> None:
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value="/usr/local/bin/pearcleaner"), \
         patch("subprocess.run", return_value=_mock_run(SAMPLE_OUTPUT)), \
         patch("mac_care.tools.pearcleaner.path_size", return_value=0):
        findings = pearcleaner_findings()

    assert all(f.source == "pearcleaner" for f in findings)


def test_pearcleaner_findings_reason_contains_app_name() -> None:
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value="/usr/local/bin/pearcleaner"), \
         patch("subprocess.run", return_value=_mock_run(SAMPLE_OUTPUT)), \
         patch("mac_care.tools.pearcleaner.path_size", return_value=0):
        findings = pearcleaner_findings()

    reasons = {f.reason for f in findings}
    assert any("com.example.DeletedApp" in r for r in reasons)


def test_pearcleaner_findings_empty_output() -> None:
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value="/usr/local/bin/pearcleaner"), \
         patch("subprocess.run", return_value=_mock_run("\nFound 0 orphaned files.\n")), \
         patch("mac_care.tools.pearcleaner.path_size", return_value=0):
        findings = pearcleaner_findings()

    assert findings == []


# ---------------------------------------------------------------------------
# pearcleaner_findings — degradation
# ---------------------------------------------------------------------------

def test_pearcleaner_findings_empty_when_not_installed() -> None:
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value=None):
        assert pearcleaner_findings() == []


def test_pearcleaner_findings_empty_on_timeout() -> None:
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value="/usr/local/bin/pearcleaner"), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pearcleaner", timeout=60)):
        assert pearcleaner_findings() == []


def test_pearcleaner_findings_empty_on_oserror() -> None:
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value="/usr/local/bin/pearcleaner"), \
         patch("subprocess.run", side_effect=OSError("launch failed")):
        assert pearcleaner_findings() == []
