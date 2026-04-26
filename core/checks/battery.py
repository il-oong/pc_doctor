"""Battery check (laptops only)."""
from __future__ import annotations

import psutil

from .base import Check, CheckResult, Severity, linear_score, severity_from_score


class BatteryCheck(Check):
    key = "battery"
    title = "배터리"
    weight = 0.05
    quick = True
    icon = "🔋"

    def run(self) -> CheckResult:
        try:
            battery = psutil.sensors_battery()
        except (AttributeError, NotImplementedError):
            battery = None

        if battery is None:
            return CheckResult(
                key=self.key,
                title=self.title,
                score=100,
                severity=Severity.HEALTHY,
                summary="배터리 없음 (데스크톱)",
                metrics={"present": False},
                icon=self.icon,
            )

        percent = float(battery.percent)
        plugged = bool(battery.power_plugged)

        if plugged:
            score = 100
        else:
            score = linear_score(percent, healthy_at=80.0, critical_at=15.0)
        severity = severity_from_score(score)

        recs: list[str] = []
        if not plugged and percent <= 15:
            recs.append("배터리 잔량이 매우 낮습니다. 즉시 충전하세요.")
        elif not plugged and percent <= 30:
            recs.append("배터리가 부족합니다. 충전기를 연결해 주세요.")

        if battery.secsleft is not None and battery.secsleft > 0 and not plugged:
            mins = int(battery.secsleft / 60)
            time_text = f" · 약 {mins}분 남음"
        else:
            time_text = ""

        return CheckResult(
            key=self.key,
            title=self.title,
            score=score,
            severity=severity,
            summary=f"{percent:.0f}%{' · 충전 중' if plugged else ''}{time_text}",
            metrics={
                "present": True,
                "percent": percent,
                "plugged": plugged,
                "secsleft": battery.secsleft,
            },
            recommendations=recs,
            icon=self.icon,
        )
