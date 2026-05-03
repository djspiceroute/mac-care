from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from mac_care.doctor import check_redundant_toolchains, check_ssh_keys, recommend_tools, TOOL_RECOMMENDATIONS


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


# ── #29 SSH key tests ────────────────────────────────────────────────────────

def test_ssh_keys_no_dir_returns_empty(tmp_path):
    with patch("mac_care.doctor.Path.home", return_value=tmp_path):
        result = check_ssh_keys()
    assert result == []


def test_ssh_key_unencrypted_flagged(tmp_path):
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    key = ssh_dir / "id_ed25519"
    key.write_bytes(b"-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQ==\n-----END OPENSSH PRIVATE KEY-----\n")
    with patch("mac_care.doctor.Path.home", return_value=tmp_path):
        result = check_ssh_keys()
    assert len(result) == 1
    assert result[0].status == "review"
    assert "no passphrase" in result[0].detail


def test_ssh_key_encrypted_ok(tmp_path):
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    key = ssh_dir / "id_ed25519"
    key.write_bytes(b"-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAACmFlczI1Ni1jdHIAAAAGYmNyeXB0\n-----END OPENSSH PRIVATE KEY-----\n")
    with patch("mac_care.doctor.Path.home", return_value=tmp_path):
        result = check_ssh_keys()
    assert len(result) == 1
    assert result[0].status == "ok"


def test_ssh_pubkey_ignored(tmp_path):
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    (ssh_dir / "id_ed25519.pub").write_bytes(b"ssh-ed25519 AAAA...")
    with patch("mac_care.doctor.Path.home", return_value=tmp_path):
        result = check_ssh_keys()
    assert result == []


# ── #37 Redundant toolchain tests ────────────────────────────────────────────

def test_redundant_toolchains_single_install_is_ok():
    def fake_which(name):
        return f"/opt/homebrew/bin/{name}" if name in ("python3", "python") else None

    with patch("mac_care.doctor.which", side_effect=fake_which), \
         patch("mac_care.doctor.Path") as mock_path:
        # Make all candidate paths non-existent except homebrew python3
        mock_path.return_value.exists.return_value = False
        mock_path.home.return_value = Path("/nonexistent")
        result = check_redundant_toolchains()
    python_status = next((s for s in result if "python" in s.name), None)
    assert python_status is not None


def test_redundant_toolchains_returns_review_when_multiple(tmp_path):
    # Simulate python3 existing in two locations
    bin1 = tmp_path / "homebrew" / "bin"
    bin1.mkdir(parents=True)
    (bin1 / "python3").write_text("stub")
    bin2 = tmp_path / "local" / "bin"
    bin2.mkdir(parents=True)
    (bin2 / "python3").write_text("stub")

    with patch("mac_care.doctor.which", return_value=str(bin1 / "python3")), \
         patch("mac_care.doctor._TOOLCHAIN_SEARCH_PATHS", [str(bin1), str(bin2)]):
        result = check_redundant_toolchains()
    python_status = next((s for s in result if "python" in s.name), None)
    assert python_status is not None
    assert python_status.status == "review"
