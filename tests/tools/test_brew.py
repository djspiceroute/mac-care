from __future__ import annotations

from unittest.mock import MagicMock, patch

from mac_care.tools.brew import _parse_size, brew_cleanup_findings


# ---------------------------------------------------------------------------
# _parse_size
# ---------------------------------------------------------------------------

def test_parse_size_megabytes() -> None:
    assert _parse_size("3.4MB") == 3_400_000


def test_parse_size_gigabytes() -> None:
    assert _parse_size("1.5GB") == 1_500_000_000


def test_parse_size_kilobytes() -> None:
    assert _parse_size("64B") == 64


def test_parse_size_with_commas() -> None:
    # brew sometimes formats as "1,641 files, 34.2MB"
    assert _parse_size("34.2MB") == 34_200_000


def test_parse_size_none() -> None:
    assert _parse_size(None) == 0


def test_parse_size_empty() -> None:
    assert _parse_size("") == 0


# ---------------------------------------------------------------------------
# brew_cleanup_findings — happy path
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
Warning: Skipping ffmpeg: most recent version 8.1 not installed
Would remove: /opt/homebrew/Cellar/xz/5.8.2 (96 files, 2.7MB)
Would remove: /Users/user/Library/Logs/Homebrew/pyenv (64B)
Would remove (broken link): /opt/homebrew/bin/github
Would remove (empty directory): /opt/homebrew/share/google-cloud-sdk/.install/.download
==> This operation would free approximately 109.2MB of disk space.
"""


def _mock_run(stdout: str):
    result = MagicMock()
    result.stdout = stdout
    result.returncode = 0
    return result


def test_brew_cleanup_findings_parses_items() -> None:
    with patch("mac_care.tools.brew.which", return_value="/opt/homebrew/bin/brew"), \
         patch("subprocess.run", return_value=_mock_run(SAMPLE_OUTPUT)):
        findings = brew_cleanup_findings()

    assert len(findings) == 4  # 4 "Would remove" lines; summary line ignored
    paths = {f.path for f in findings}
    assert "/opt/homebrew/Cellar/xz/5.8.2" in paths
    assert "/Users/user/Library/Logs/Homebrew/pyenv" in paths
    assert "/opt/homebrew/bin/github" in paths


def test_brew_cleanup_findings_sizes() -> None:
    with patch("mac_care.tools.brew.which", return_value="/opt/homebrew/bin/brew"), \
         patch("subprocess.run", return_value=_mock_run(SAMPLE_OUTPUT)):
        findings = brew_cleanup_findings()

    sizes = {f.path: f.size_bytes for f in findings}
    assert sizes["/opt/homebrew/Cellar/xz/5.8.2"] == 2_700_000
    assert sizes["/Users/user/Library/Logs/Homebrew/pyenv"] == 64
    assert sizes["/opt/homebrew/bin/github"] == 0  # broken link — no size


def test_brew_cleanup_findings_all_auto_safe() -> None:
    with patch("mac_care.tools.brew.which", return_value="/opt/homebrew/bin/brew"), \
         patch("subprocess.run", return_value=_mock_run(SAMPLE_OUTPUT)):
        findings = brew_cleanup_findings()

    assert all(f.risk == "auto_safe" for f in findings)


def test_brew_cleanup_findings_source_is_brew() -> None:
    with patch("mac_care.tools.brew.which", return_value="/opt/homebrew/bin/brew"), \
         patch("subprocess.run", return_value=_mock_run(SAMPLE_OUTPUT)):
        findings = brew_cleanup_findings()

    assert all(f.source == "brew" for f in findings)


# ---------------------------------------------------------------------------
# brew_cleanup_findings — degradation
# ---------------------------------------------------------------------------

def test_brew_cleanup_findings_empty_when_brew_missing() -> None:
    with patch("mac_care.tools.brew.which", return_value=None):
        findings = brew_cleanup_findings()
    assert findings == []


def test_brew_cleanup_findings_empty_on_timeout() -> None:
    import subprocess
    with patch("mac_care.tools.brew.which", return_value="/opt/homebrew/bin/brew"), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="brew", timeout=60)):
        findings = brew_cleanup_findings()
    assert findings == []


def test_brew_cleanup_findings_empty_on_oserror() -> None:
    with patch("mac_care.tools.brew.which", return_value="/opt/homebrew/bin/brew"), \
         patch("subprocess.run", side_effect=OSError("something went wrong")):
        findings = brew_cleanup_findings()
    assert findings == []


def test_brew_cleanup_findings_empty_output() -> None:
    with patch("mac_care.tools.brew.which", return_value="/opt/homebrew/bin/brew"), \
         patch("subprocess.run", return_value=_mock_run("")):
        findings = brew_cleanup_findings()
    assert findings == []
