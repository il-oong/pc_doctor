"""Memory check (RAM + swap)."""
from __future__ import annotations

import psutil

from utils.format import bytes_human

from .base import Check, CheckResult, linear_score, severity_from_score


class MemoryCheck(Check):
    key = "memory"
    title = "메모리"
    weight = 0.20
    quick = True
    icon = "🧠"

    def run(self) -> CheckResult:
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()

        ram_score = linear_score(vm.percent, healthy_at=60.0, critical_at=95.0)
        swap_score = linear_score(sw.percent, healthy_at=10.0, critical_at=80.0) if sw.total else 100
        score = int(round(ram_score * 0.8 + swap_score * 0.2))
        severity = severity_from_score(score)

        recs: list[str] = []
        if vm.percent >= 90:
            recs.append("메모리가 거의 가득 찼습니다. 사용하지 않는 앱을 종료해 주세요.")
        elif vm.percent >= 80:
            recs.append("메모리 사용량이 많습니다. 브라우저 탭이나 백그라운드 앱을 정리해 주세요.")
        if sw.total and sw.percent >= 50:
            recs.append("스왑 사용량이 큽니다. 물리 메모리 증설 또는 앱 종료를 권장합니다.")

        return CheckResult(
            key=self.key,
            title=self.title,
            score=score,
            severity=severity,
            summary=f"{vm.percent:.0f}% · {bytes_human(vm.used)} / {bytes_human(vm.total)}",
            metrics={
                "ram_percent": vm.percent,
                "ram_used": vm.used,
                "ram_total": vm.total,
                "ram_available": vm.available,
                "swap_percent": sw.percent,
                "swap_used": sw.used,
                "swap_total": sw.total,
            },
            recommendations=recs,
            icon=self.icon,
        )
