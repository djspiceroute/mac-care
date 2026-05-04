from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from mac_care.tools.pearcleaner import (
    _belongs_to_installed_app,
    _guess_app_name,
    pearcleaner_findings,
)


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


_NO_INSTALLED = frozenset()


def test_pearcleaner_findings_parses_paths() -> None:
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value="/usr/local/bin/pearcleaner"), \
         patch("subprocess.run", return_value=_mock_run(SAMPLE_OUTPUT)), \
         patch("mac_care.tools.pearcleaner._installed_app_identifiers", return_value=_NO_INSTALLED), \
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
         patch("mac_care.tools.pearcleaner._installed_app_identifiers", return_value=_NO_INSTALLED), \
         patch("mac_care.tools.pearcleaner.path_size", return_value=0):
        findings = pearcleaner_findings()

    # Summary line "Found 3 orphaned files." must not become a Finding
    assert all("Found" not in f.path for f in findings)


def test_pearcleaner_findings_all_review_risk() -> None:
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value="/usr/local/bin/pearcleaner"), \
         patch("subprocess.run", return_value=_mock_run(SAMPLE_OUTPUT)), \
         patch("mac_care.tools.pearcleaner._installed_app_identifiers", return_value=_NO_INSTALLED), \
         patch("mac_care.tools.pearcleaner.path_size", return_value=0):
        findings = pearcleaner_findings()

    assert all(f.risk == "review" for f in findings)


def test_pearcleaner_findings_source_is_pearcleaner() -> None:
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value="/usr/local/bin/pearcleaner"), \
         patch("subprocess.run", return_value=_mock_run(SAMPLE_OUTPUT)), \
         patch("mac_care.tools.pearcleaner._installed_app_identifiers", return_value=_NO_INSTALLED), \
         patch("mac_care.tools.pearcleaner.path_size", return_value=0):
        findings = pearcleaner_findings()

    assert all(f.source == "pearcleaner" for f in findings)


def test_pearcleaner_findings_reason_contains_app_name() -> None:
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value="/usr/local/bin/pearcleaner"), \
         patch("subprocess.run", return_value=_mock_run(SAMPLE_OUTPUT)), \
         patch("mac_care.tools.pearcleaner._installed_app_identifiers", return_value=_NO_INSTALLED), \
         patch("mac_care.tools.pearcleaner.path_size", return_value=0):
        findings = pearcleaner_findings()

    reasons = {f.reason for f in findings}
    assert any("com.example.DeletedApp" in r for r in reasons)


def test_pearcleaner_findings_empty_output() -> None:
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value="/usr/local/bin/pearcleaner"), \
         patch("subprocess.run", return_value=_mock_run("\nFound 0 orphaned files.\n")), \
         patch("mac_care.tools.pearcleaner._installed_app_identifiers", return_value=_NO_INSTALLED), \
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


# ---------------------------------------------------------------------------
# _belongs_to_installed_app — filtering logic
# ---------------------------------------------------------------------------

_INSTALLED = frozenset([
    "com.spotify.client",
    "spotify",
    "com.anthropic.claudefordesktop",
    "claude",
    "com.dashlane.dashlanephonefinal",
    "dashlane",
])


def test_belongs_direct_bundle_id_match(tmp_path: Path) -> None:
    p = tmp_path / "com.spotify.client"
    p.mkdir()
    assert _belongs_to_installed_app(p, _INSTALLED) is True


def test_belongs_app_name_match(tmp_path: Path) -> None:
    p = tmp_path / "Claude"
    p.mkdir()
    assert _belongs_to_installed_app(p, _INSTALLED) is True


def test_belongs_extension_suffix_match(tmp_path: Path) -> None:
    # App extension bundle IDs are suffixes of the parent app's bundle ID
    p = tmp_path / "com.dashlane.dashlanephonefinal.SafariWebExtension"
    p.mkdir()
    assert _belongs_to_installed_app(p, _INSTALLED) is True


def test_belongs_helper_suffix_match(tmp_path: Path) -> None:
    p = tmp_path / "com.spotify.client.helper"
    p.mkdir()
    assert _belongs_to_installed_app(p, _INSTALLED) is True


def test_belongs_team_id_prefix_stripped(tmp_path: Path) -> None:
    # Team ID (10 uppercase alphanum chars) should be stripped before matching
    p = tmp_path / "ABCDE12345.com.spotify.client"
    p.mkdir()
    assert _belongs_to_installed_app(p, _INSTALLED) is True


def test_belongs_team_id_with_group_prefix(tmp_path: Path) -> None:
    # App groups use pattern TEAMID.group.bundle.id
    p = tmp_path / "ABCDE12345.group.com.spotify.client"
    p.mkdir()
    assert _belongs_to_installed_app(p, _INSTALLED) is True


def test_belongs_plist_file_match(tmp_path: Path) -> None:
    p = tmp_path / "com.spotify.client.plist"
    p.touch()
    assert _belongs_to_installed_app(p, _INSTALLED) is True


def test_belongs_unrecognized_returns_false(tmp_path: Path) -> None:
    p = tmp_path / "com.deleted.OldApp"
    p.mkdir()
    assert _belongs_to_installed_app(p, _INSTALLED) is False


def test_pearcleaner_findings_filters_installed_app_paths() -> None:
    output = (
        "/Users/user/Library/Application Support/com.spotify.client\n"
        "/Users/user/Library/Application Support/com.deleted.OldApp\n"
        "Found 2 orphaned files.\n"
    )
    installed = frozenset(["com.spotify.client", "spotify"])
    with patch("mac_care.tools.pearcleaner._pearcleaner_bin", return_value="/usr/local/bin/pearcleaner"), \
         patch("subprocess.run", return_value=_mock_run(output)), \
         patch("mac_care.tools.pearcleaner._installed_app_identifiers", return_value=installed), \
         patch("mac_care.tools.pearcleaner.path_size", return_value=1024):
        findings = pearcleaner_findings()

    assert len(findings) == 1
    assert findings[0].path == "/Users/user/Library/Application Support/com.deleted.OldApp"
