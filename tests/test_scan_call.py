from unittest.mock import patch, MagicMock
from pathlib import Path
from mac_care.scan import scan
from mac_care.config import Config

@patch("mac_care.scan.xcode_findings")
@patch("mac_care.scan.brew_cleanup_findings")
@patch("mac_care.scan.docker_findings")
@patch("mac_care.scan.pearcleaner_findings")
@patch("mac_care.scan._standard_paths")
@patch("mac_care.scan._developer_paths")
@patch("mac_care.scan._downloads_review")
@patch("mac_care.scan._ios_backups")
@patch("mac_care.scan._messages_attachments")
@patch("mac_care.scan._time_machine_snapshots")
@patch("mac_care.scan._core_dumps_and_crash_logs")
@patch("mac_care.scan._broken_symlinks")
@patch("mac_care.scan._login_items")
@patch("mac_care.scan._stale_runtime_versions")
@patch("mac_care.scan._orphaned_dotdirs")
@patch("mac_care.scan._ai_tool_caches")
def test_scan_calls_xcode_findings(
    mock_ai, mock_orphan, mock_stale, mock_login, mock_broken, mock_core,
    mock_tm, mock_msg, mock_ios, mock_downloads, mock_dev, mock_std,
    mock_pear, mock_docker, mock_brew, mock_xcode, tmp_path
):
    # Setup mocks to return empty lists to avoid crashes
    for m in [mock_ai, mock_orphan, mock_stale, mock_login, mock_broken, mock_core,
              mock_tm, mock_msg, mock_ios, mock_downloads, mock_dev, mock_std,
              mock_pear, mock_docker, mock_brew, mock_xcode]:
        m.return_value = []
        
    config = Config(reports_dir=tmp_path, quarantine_dir=tmp_path)
    scan(config)
    
    assert mock_xcode.called
