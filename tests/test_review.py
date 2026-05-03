import json

from mac_care.config import Config
from mac_care.ids import finding_id
from mac_care.model import Finding
from mac_care.review import approve_finding


def _write_report(path, findings):
    path.write_text(json.dumps({"findings": findings}), encoding="utf-8")


def _payload(finding):
    payload = finding.__dict__.copy()
    payload["id"] = finding_id(finding)
    return payload


def test_approve_finding_dry_run(tmp_path):
    target = tmp_path / "orphan"
    target.write_text("data", encoding="utf-8")
    finding = Finding("orphaned_app_files", str(target), 4, "review", "orphan", "pearcleaner")
    report = tmp_path / "report.json"
    _write_report(report, [_payload(finding)])
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")

    result = approve_finding(report, finding_id(finding), config, dry_run=True)

    assert result == f"would quarantine review finding {finding_id(finding)}: {target}"
    assert target.exists()


def test_approve_finding_execute_quarantines_review_item(tmp_path):
    target = tmp_path / "orphan"
    target.write_text("data", encoding="utf-8")
    finding = Finding("orphaned_app_files", str(target), 4, "review", "orphan", "pearcleaner")
    report = tmp_path / "report.json"
    _write_report(report, [_payload(finding)])
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")

    result = approve_finding(report, finding_id(finding), config, dry_run=False)

    assert result.startswith("quarantined orphaned_app_files:")
    assert not target.exists()
    assert list(config.quarantine_dir.glob("*/orphaned_app_files/orphan"))


def test_approve_finding_rejects_protected(tmp_path):
    target = tmp_path / "protected"
    target.write_text("data", encoding="utf-8")
    finding = Finding("orphaned_app_files", str(target), 4, "protected", "protected", "pearcleaner")
    report = tmp_path / "report.json"
    _write_report(report, [_payload(finding)])
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")

    result = approve_finding(report, finding_id(finding), config, dry_run=False)

    assert "protected findings cannot be actioned" in result
    assert target.exists()


def test_approve_finding_rejects_unknown_id(tmp_path):
    report = tmp_path / "report.json"
    _write_report(report, [])
    config = Config(reports_dir=tmp_path / "reports", quarantine_dir=tmp_path / "quarantine")

    result = approve_finding(report, "missing", config, dry_run=False)

    assert "was not found" in result
