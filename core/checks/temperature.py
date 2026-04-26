"""CPU/GPU temperature check (best-effort, OS dependent)."""
from __future__ import annotations

import psutil

from .base import Check, CheckResult, Severity, linear_score, severity_from_score


class TemperatureCheck(Check):
    key = "temperature"
    title = "온도"
    weight = 0.05
    quick = False
    icon = "🌡"

    def run(self) -> CheckResult:
        temps: dict[str, list[dict]] = {}
        try:
            raw = psutil.sensors_temperatures(fahrenheit=False) or {}
            for name, entries in raw.items():
                temps[name] = [
                    {
                        "label": e.label or name,
                        "current": e.current,
                        "high": e.high,
                        "critical": e.critical,
                    }
                    for e in entries
                ]
        except (AttributeError, NotImplementedError, OSError):
            temps = {}

        readings = [
            entry["current"]
            for entries in temps.values()
            for entry in entries
            if entry["current"] is not None
        ]

        if not readings:
            return CheckResult(
                key=self.key,
                title=self.title,
                score=100,
                severity=Severity.UNKNOWN,
                summary="센서 정보 없음",
                metrics={"sensors": temps},
                icon=self.icon,
            )

        peak = max(readings)
        score = linear_score(peak, healthy_at=65.0, critical_at=95.0)
        severity = severity_from_score(score)

        recs: list[str] = []
        if peak >= 90:
            recs.append("온도가 매우 높습니다. 환기/먼지 제거를 점검해 주세요.")
        elif peak >= 80:
            recs.append("온도가 높습니다. 무거운 작업을 잠시 멈춰 주세요.")

        return CheckResult(
            key=self.key,
            title=self.title,
            score=score,
            severity=severity,
            summary=f"피크 {peak:.0f}℃ · 센서 {len(readings)}개",
            metrics={"peak": peak, "sensors": temps},
            recommendations=recs,
            icon=self.icon,
        )
