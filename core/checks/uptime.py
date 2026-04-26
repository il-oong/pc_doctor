"""System uptime / boot time check."""
from __future__ import annotations

import time

import psutil

from utils.format import duration

from .base import Check, CheckResult, linear_score, severity_from_score


class UptimeCheck(Check):
    key = "uptime"
    title = "가동 시간"
    weight = 0.05
    quick = True
    icon = "⏱"

    def run(self) -> CheckResult:
        boot = psutil.boot_time()
        uptime_sec = max(0, time.time() - boot)
        days = uptime_sec / 86400.0

        # Long uptime is fine until ~14 days, then suggest reboot
        score = linear_score(days, healthy_at=14.0, critical_at=60.0)
        severity = severity_from_score(score)

        recs: list[str] = []
        if days >= 30:
            recs.append("가동 시간이 매우 깁니다. 보안/안정성을 위해 재시작을 권장합니다.")
        elif days >= 14:
            recs.append("재시작한 지 오래됐습니다. 시간이 될 때 재부팅을 권장합니다.")

        return CheckResult(
            key=self.key,
            title=self.title,
            score=score,
            severity=severity,
            summary=f"가동 {duration(uptime_sec)}",
            metrics={
                "boot_time": boot,
                "uptime_sec": uptime_sec,
            },
            recommendations=recs,
            icon=self.icon,
        )
