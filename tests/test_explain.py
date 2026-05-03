import json
from pathlib import Path
from mac_care.explain import explain_category, explain_finding
from mac_care.model import Finding
from mac_care.ids import finding_id

def test_explain_category_known():
    result = explain_category("user_logs")
    assert "User Logs" in result
    assert "troubleshooting" in result

def test_explain_category_unknown():
    result = explain_category("mysterious_void")
    assert "Mysterious Void" in result
    assert "No detailed description available" in result

def test_explain_finding_success(tmp_path):
    f = Finding(
        category="xcode_derived_data",
        path="/Users/test/Library/Developer/Xcode/DerivedData",
        size_bytes=1024 * 1024 * 100,
        risk="auto_safe",
        reason="rebuildable Xcode artifacts"
    )
    fid = finding_id(f)
    
    report = {
        "findings": [
            {
                "category": f.category,
                "path": f.path,
                "size_bytes": f.size_bytes,
                "risk": f.risk,
                "reason": f.reason
            }
        ]
    }
    
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report))
    
    result = explain_finding(fid, report_path)
    assert "Xcode Derived Data" in result
    assert "100.0 MB" in result
    assert "rebuildable Xcode artifacts" in result
    assert "AUTO_SAFE" in result

def test_explain_finding_not_found(tmp_path):
    report_path = tmp_path / "empty_report.json"
    report_path.write_text(json.dumps({"findings": []}))
    
    result = explain_finding("0123456789abcdef", report_path)
    assert "Error: Finding with ID '0123456789abcdef' not found" in result

def test_explain_finding_missing_report(tmp_path):
    result = explain_finding("some-id", tmp_path / "nonexistent.json")
    assert "Error: Report not found" in result
