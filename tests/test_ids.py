from mac_care.ids import finding_id
from mac_care.model import Finding


def test_finding_id_is_stable_for_same_finding():
    finding = Finding("logs", "/tmp/logs", 1, "review", "reason", "native")

    assert finding_id(finding) == finding_id(finding)
    assert len(finding_id(finding)) == 16


def test_finding_id_stable_when_reason_changes():
    base = Finding("logs", "/tmp/logs", 1, "review", "largest: A (1.0 GB)", "native")
    updated = Finding("logs", "/tmp/logs", 1, "review", "largest: A (1.2 GB), B (0.8 GB)", "native")

    assert finding_id(base) == finding_id(updated)


def test_finding_id_stable_when_size_changes():
    base = Finding("brew_cache", "/tmp/cache", 100, "auto_safe", "brew cache", "brew")
    grown = Finding("brew_cache", "/tmp/cache", 9999, "auto_safe", "brew cache", "brew")

    assert finding_id(base) == finding_id(grown)


def test_finding_id_changes_when_risk_changes():
    safe = Finding("logs", "/tmp/logs", 1, "auto_safe", "reason", "native")
    review = Finding("logs", "/tmp/logs", 1, "review", "reason", "native")

    assert finding_id(safe) != finding_id(review)


def test_finding_id_changes_for_path():
    first = Finding("logs", "/tmp/logs", 1, "review", "reason", "native")
    second = Finding("logs", "/tmp/other", 1, "review", "reason", "native")

    assert finding_id(first) != finding_id(second)


def test_finding_id_changes_for_category():
    first = Finding("logs", "/tmp/logs", 1, "review", "reason", "native")
    second = Finding("caches", "/tmp/logs", 1, "review", "reason", "native")

    assert finding_id(first) != finding_id(second)
