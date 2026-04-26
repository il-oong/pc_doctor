"""Base classes for individual health checks."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

    @property
    def label_ko(self) -> str:
        return {
            Severity.HEALTHY: "정상",
            Severity.WARNING: "주의",
            Severity.CRITICAL: "위험",
            Severity.UNKNOWN: "확인 불가",
        }[self]


@dataclass
class CheckResult:
    key: str
    title: str
    score: int
    severity: Severity
    summary: str
    metrics: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    duration_ms: int = 0
    icon: str = ""  # short emoji/character used as fallback icon

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "score": self.score,
            "severity": self.severity.value,
            "summary": self.summary,
            "metrics": self.metrics,
            "recommendations": list(self.recommendations),
            "duration_ms": self.duration_ms,
            "icon": self.icon,
        }


def severity_from_score(score: int) -> Severity:
    if score >= 90:
        return Severity.HEALTHY
    if score >= 70:
        return Severity.WARNING
    return Severity.CRITICAL


def linear_score(value: float, healthy_at: float, critical_at: float) -> int:
    """Map a metric to 0..100 linearly between two thresholds.

    `healthy_at` is the value that scores 100 (and anything better also 100).
    `critical_at` is the value that scores 0 (and anything worse also 0).
    Direction is inferred from which threshold is larger.
    """
    if healthy_at == critical_at:
        return 100 if value == healthy_at else 0
    if critical_at > healthy_at:
        if value <= healthy_at:
            return 100
        if value >= critical_at:
            return 0
        ratio = (value - healthy_at) / (critical_at - healthy_at)
        return max(0, min(100, int(round(100 * (1 - ratio)))))
    if value >= healthy_at:
        return 100
    if value <= critical_at:
        return 0
    ratio = (healthy_at - value) / (healthy_at - critical_at)
    return max(0, min(100, int(round(100 * (1 - ratio)))))


class Check:
    key: str = ""
    title: str = ""
    weight: float = 1.0
    quick: bool = True
    icon: str = ""

    def run(self) -> CheckResult:  # pragma: no cover - subclasses override
        raise NotImplementedError

    def measure(self) -> CheckResult:
        start = time.perf_counter()
        try:
            result = self.run()
        except Exception as exc:  # noqa: BLE001 — surface failure as UNKNOWN
            result = CheckResult(
                key=self.key,
                title=self.title,
                score=0,
                severity=Severity.UNKNOWN,
                summary=f"검진 실패: {exc}",
                icon=self.icon,
            )
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        if not result.icon:
            result.icon = self.icon
        return result
