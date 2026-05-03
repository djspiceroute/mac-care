import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from mac_care.tools.xcode import xcode_findings


@pytest.fixture
def mock_simctl_data(tmp_path):
    # Use paths relative to tmp_path for easier testing
    unavailable_data = tmp_path / "sim/unavailable-data"
    unavailable_data.mkdir(parents=True, exist_ok=True)
    
    return {
        "devices": {
            "com.apple.CoreSimulator.SimRuntime.iOS-17-0": [
                {
                    "udid": "available-udid",
                    "name": "iPhone 15",
                    "isAvailable": True,
                    "dataPath": str(tmp_path / "sim/available-data")
                },
                {
                    "udid": "unavailable-udid",
                    "name": "iPhone 14",
                    "isAvailable": False,
                    "dataPath": str(unavailable_data)
                }
            ],
            "com.apple.CoreSimulator.SimRuntime.watchOS-10-0": [
                {
                    "udid": "unavailable-watch-udid",
                    "name": "Apple Watch Series 9",
                    "isAvailable": False
                    # No dataPath, test fallback
                }
            ]
        }
    }


@patch("mac_care.tools.xcode.which")
@patch("mac_care.tools.xcode.subprocess.run")
@patch("mac_care.tools.xcode.size_of")
@patch("mac_care.tools.xcode.Path.home")
def test_xcode_findings_unavailable_simulators(
    mock_home, mock_size, mock_run, mock_which, mock_simctl_data, tmp_path
):
    # Setup mocks
    mock_which.return_value = "/usr/bin/xcrun"
    mock_home.return_value = tmp_path
    
    # Mock subprocess.run for simctl list
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps(mock_simctl_data)
    )
    
    # Create fallback path for watch
    watch_fallback_path = tmp_path / "Library/Developer/CoreSimulator/Devices/unavailable-watch-udid"
    watch_fallback_path.mkdir(parents=True, exist_ok=True)
    
    mock_size.return_value = 1024 * 1024  # 1MB
    
    findings = xcode_findings()
    
    # We expect 2 findings for unavailable simulators (iPhone 14 and Watch)
    unavailable_findings = [f for f in findings if f.category == "xcode_unavailable_simulator"]
    assert len(unavailable_findings) == 2
    
    f1 = next(f for f in unavailable_findings if "iPhone 14" in f.reason)
    assert f1.path == str(tmp_path / "sim/unavailable-data")
    assert f1.size_bytes == 1024 * 1024
    
    f2 = next(f for f in unavailable_findings if "Apple Watch" in f.reason)
    assert f2.path == str(watch_fallback_path)


@patch("mac_care.tools.xcode.which")
@patch("mac_care.tools.xcode.Path.home")
@patch("mac_care.tools.xcode.size_of")
@patch("mac_care.tools.xcode.subprocess.run")
def test_xcode_findings_device_support(
    mock_run, mock_size, mock_home, mock_which, tmp_path
):
    mock_which.return_value = "/usr/bin/xcrun"
    mock_home.return_value = tmp_path
    mock_run.return_value = MagicMock(returncode=0, stdout='{"devices": {}}')
    
    # Setup DeviceSupport paths
    ios_support = tmp_path / "Library/Developer/Xcode/iOS DeviceSupport"
    ios_support.mkdir(parents=True, exist_ok=True)
    
    mock_size.return_value = 500 * 1024 * 1024 # 500MB
    
    findings = xcode_findings()
    
    support_findings = [f for f in findings if f.category == "xcode_device_support"]
    assert len(support_findings) == 1
    assert support_findings[0].path == str(ios_support)
    assert "iOS DeviceSupport" in support_findings[0].reason


@patch("mac_care.tools.xcode.which")
def test_xcode_findings_no_xcrun(mock_which):
    mock_which.return_value = None
    assert xcode_findings() == []
