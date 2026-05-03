from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from mac_care.tools.disk import size_of, top_subdirs, top_subdirs_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dua_output(*entries: tuple[str, int], include_total: bool = True) -> str:
    """Build mock dua aggregate -f bytes output with ANSI codes."""
    lines = []
    total = 0
    for path, size in entries:
        lines.append(f"\x1b[32m{size:>12} b\x1b[39m \x1b[36m{path}\x1b[39m")
        total += size
    if include_total:
        lines.append(f"\x1b[32m{total:>12} b\x1b[39m total")
    return "\n".join(lines) + "\n"


def _du_output(root: str, *entries: tuple[str, int]) -> str:
    """Build mock du -d 1 -k output (kilobytes, tab-separated)."""
    lines = []
    for path, size_bytes in entries:
        kb = size_bytes // 1024
        lines.append(f"{kb}\t{path}")
    # du also includes the root itself
    total_kb = sum(size_bytes // 1024 for _, size_bytes in entries)
    lines.append(f"{total_kb}\t{root}")
    return "\n".join(lines) + "\n"


def _mock_run(stdout: str) -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    result.returncode = 0
    return result


# ---------------------------------------------------------------------------
# top_subdirs — dua path
# ---------------------------------------------------------------------------

def test_top_subdirs_dua_returns_sorted_entries(tmp_path: Path) -> None:
    # Create real children so path.iterdir() has something to return
    for name in ("small", "large", "medium"):
        (tmp_path / name).mkdir()
    output = _dua_output(
        (str(tmp_path / "small"), 1_000_000),
        (str(tmp_path / "large"), 5_000_000),
        (str(tmp_path / "medium"), 2_000_000),
    )
    with patch("mac_care.tools.disk._dua_available", return_value=True), \
         patch("subprocess.run", return_value=_mock_run(output)):
        result = top_subdirs(tmp_path, n=3)

    assert len(result) == 3
    assert result[0] == (tmp_path / "large", 5_000_000)
    assert result[1] == (tmp_path / "medium", 2_000_000)
    assert result[2] == (tmp_path / "small", 1_000_000)


def test_top_subdirs_dua_respects_n(tmp_path: Path) -> None:
    for name in ("a", "b", "c"):
        (tmp_path / name).mkdir()
    output = _dua_output(
        (str(tmp_path / "a"), 3_000_000),
        (str(tmp_path / "b"), 2_000_000),
        (str(tmp_path / "c"), 1_000_000),
    )
    with patch("mac_care.tools.disk._dua_available", return_value=True), \
         patch("subprocess.run", return_value=_mock_run(output)):
        result = top_subdirs(tmp_path, n=2)

    assert len(result) == 2
    assert result[0][0].name == "a"


def test_top_subdirs_dua_skips_total_line(tmp_path: Path) -> None:
    (tmp_path / "only").mkdir()
    output = _dua_output((str(tmp_path / "only"), 1_000_000), include_total=True)
    with patch("mac_care.tools.disk._dua_available", return_value=True), \
         patch("subprocess.run", return_value=_mock_run(output)):
        result = top_subdirs(tmp_path)

    assert len(result) == 1


# ---------------------------------------------------------------------------
# top_subdirs — du fallback
# ---------------------------------------------------------------------------

def test_top_subdirs_du_fallback(tmp_path: Path) -> None:
    output = _du_output(
        str(tmp_path),
        (str(tmp_path / "big"), 10 * 1024 * 1024),
        (str(tmp_path / "tiny"), 512 * 1024),
    )
    with patch("mac_care.tools.disk._dua_available", return_value=False), \
         patch("subprocess.run", return_value=_mock_run(output)):
        result = top_subdirs(tmp_path)

    assert len(result) == 2
    assert result[0][0].name == "big"
    assert result[0][1] == 10 * 1024 * 1024


def test_top_subdirs_empty_for_nonexistent_path() -> None:
    result = top_subdirs(Path("/nonexistent/path/xyz"))
    assert result == []


# ---------------------------------------------------------------------------
# size_of
# ---------------------------------------------------------------------------

def test_size_of_sums_dua_entries(tmp_path: Path) -> None:
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
    output = _dua_output(
        (str(tmp_path / "a"), 1_000_000),
        (str(tmp_path / "b"), 2_000_000),
    )
    with patch("mac_care.tools.disk._dua_available", return_value=True), \
         patch("subprocess.run", return_value=_mock_run(output)):
        total = size_of(tmp_path)

    assert total == 3_000_000


def test_size_of_zero_for_nonexistent() -> None:
    assert size_of(Path("/nonexistent/xyz")) == 0


def test_size_of_falls_back_to_du_when_dua_unavailable(tmp_path: Path) -> None:
    output = _du_output(
        str(tmp_path),
        (str(tmp_path / "x"), 4 * 1024 * 1024),
    )
    with patch("mac_care.tools.disk._dua_available", return_value=False), \
         patch("subprocess.run", return_value=_mock_run(output)):
        total = size_of(tmp_path)

    assert total == 4 * 1024 * 1024


# ---------------------------------------------------------------------------
# top_subdirs_summary
# ---------------------------------------------------------------------------

def test_top_subdirs_summary_format(tmp_path: Path) -> None:
    for name in ("ProjectA", "ProjectB"):
        (tmp_path / name).mkdir()
    output = _dua_output(
        (str(tmp_path / "ProjectA"), 4_300_000_000),
        (str(tmp_path / "ProjectB"), 1_100_000_000),
    )
    with patch("mac_care.tools.disk._dua_available", return_value=True), \
         patch("subprocess.run", return_value=_mock_run(output)):
        summary = top_subdirs_summary(tmp_path)

    assert summary.startswith("largest:")
    assert "ProjectA" in summary
    assert "ProjectB" in summary


def test_top_subdirs_summary_empty_for_nonexistent() -> None:
    assert top_subdirs_summary(Path("/nonexistent/xyz")) == ""
