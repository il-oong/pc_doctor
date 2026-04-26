"""Aggregate health score from individual check results."""
from __future__ import annotations

from dataclasses import dataclass

from .checks import CheckResult, Severity


@dataclass
class HealthSummary:
    score: int
    severity: Severity
    headline: str
    finished_at: float
    duration_ms: int
    results: list[CheckResult]

    @property
    def critical_results(self) -> list[CheckResult]:
        return [r for r in self.results if r.severity == Severity.CRITICAL]

    @property
    def warning_results(self) -> list[CheckResult]:
        return [r for r in self.results if r.severity == Severity.WARNING]


def aggregate(results: list[CheckResult], weights: dict[str, float] | None = None) -> HealthSummary:
    weights = weights or {}
    total_w = 0.0
    weighted = 0.0
    duration = 0
    for r in results:
        if r.severity == Severity.UNKNOWN:
            continue
        w = weights.get(r.key, 1.0)
        weighted += r.score * w
        total_w += w
        duration += r.duration_ms

    score = int(round(weighted / total_w)) if total_w else 0
    if score >= 90:
        severity = Severity.HEALTHY
        headline = "전반적으로 건강합니다."
    elif score >= 70:
        severity = Severity.WARNING
        headline = "주의가 필요한 항목이 있습니다."
    else:
        severity = Severity.CRITICAL
        headline = "즉시 조치가 필요한 항목이 있습니다."

    import time

    return HealthSummary(
        score=score,
        severity=severity,
        headline=headline,
        finished_at=time.time(),
        duration_ms=duration,
        results=results,
    )
