from __future__ import annotations

import hashlib

from .model import Finding


def finding_id(finding: Finding) -> str:
    payload = "\0".join(
        [
            finding.category,
            finding.path,
            finding.risk,
            finding.source,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
