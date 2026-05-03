from __future__ import annotations

from dataclasses import asdict, dataclass

from .model import Finding, Risk, ToolStatus


RISK_ORDER: tuple[Risk, ...] = ("auto_safe", "review", "protected")
WARNING_STATUSES = {"missing", "review", "optional_missing"}


@dataclass(frozen=True)
class RiskSummary:
    count: int
    size_bytes: int


@dataclass(frozen=True)
class ScanSummary:
    risks: dict[Risk, RiskSummary]
    top_findings: list[Finding]
    tool_warning_count: int

    def to_dict(self) -> dict:
        return {
            "risks": {risk: asdict(summary) for risk, summary in self.risks.items()},
            "top_findings": [asdict(finding) for finding in self.top_findings],
            "tool_warning_count": self.tool_warning_count,
        }


def summarize_scan(findings: list[Finding], tools: list[ToolStatus], top_n: int = 5) -> ScanSummary:
    risks: dict[Risk, RiskSummary] = {}
    for risk in RISK_ORDER:
        group = [finding for finding in findings if finding.risk == risk]
        risks[risk] = RiskSummary(
            count=len(group),
            size_bytes=sum(finding.size_bytes for finding in group),
        )

    top_findings = sorted(findings, key=lambda finding: finding.size_bytes, reverse=True)[:top_n]
    tool_warning_count = sum(1 for tool in tools if tool.status in WARNING_STATUSES)
    return ScanSummary(risks=risks, top_findings=top_findings, tool_warning_count=tool_warning_count)
