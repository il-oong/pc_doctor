"""CPU load check."""
from __future__ import annotations

import os

import psutil

from .base import Check, CheckResult, Recommendation, linear_score, severity_from_score


class CPUCheck(Check):
    key = "cpu"
    title = "CPU 부하"
    weight = 0.20
    quick = True
    icon = "💻"

    def run(self) -> CheckResult:
        usage = psutil.cpu_percent(interval=0.4)
        per_core = psutil.cpu_percent(interval=None, percpu=True)
        logical = psutil.cpu_count(logical=True) or 1
        physical = psutil.cpu_count(logical=False) or logical

        load: tuple[float, float, float] | None = None
        if hasattr(os, "getloadavg"):
            try:
                load = os.getloadavg()
            except OSError:
                load = None

        score = linear_score(usage, healthy_at=60.0, critical_at=95.0)
        severity = severity_from_score(score)

        recs: list[Recommendation] = []
        if usage >= 95:
            recs.append(Recommendation(
                text="CPU가 매우 바쁩니다. 자원을 많이 쓰는 프로세스를 종료해 주세요.",
                action="open_task_manager",
                action_label="작업 관리자 열기",
            ))
        elif usage >= 80:
            recs.append(Recommendation(
                text="CPU 사용률이 높습니다. 백그라운드 작업을 확인해 주세요.",
                action="open_task_manager",
                action_label="작업 관리자 열기",
            ))

        if load and logical:
            ratio = load[0] / logical
            if ratio > 1.5:
                recs.append(Recommendation(
                    text=(
                        f"1분 평균 부하가 코어 수 대비 {ratio:.1f}배입니다. "
                        "과부하 상태일 수 있습니다."
                    ),
                    action="open_resource_monitor",
                    action_label="리소스 모니터 열기",
                ))

        return CheckResult(
            key=self.key,
            title=self.title,
            score=score,
            severity=severity,
            summary=f"사용률 {usage:.0f}% · {physical}코어 / {logical}스레드",
            metrics={
                "usage_percent": usage,
                "per_core": per_core,
                "logical_cores": logical,
                "physical_cores": physical,
                "load_avg": list(load) if load else None,
            },
            recommendations=recs,
            icon=self.icon,
        )
