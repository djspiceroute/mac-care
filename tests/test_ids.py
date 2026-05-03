from mac_care.ids import finding_id
from mac_care.model import Finding


def test_finding_id_is_stable_for_same_finding():
    finding = Finding("logs", "/tmp/logs", 1, "review", "reason", "native")

    assert finding_id(finding) == finding_id(finding)
    assert len(finding_id(finding)) == 16


def test_finding_id_changes_for_path():
    first = Finding("logs", "/tmp/logs", 1, "review", "reason", "native")
    second = Finding("logs", "/tmp/other", 1, "review", "reason", "native")

    assert finding_id(first) != finding_id(second)
