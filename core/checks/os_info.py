"""OS info — informational, always healthy."""
from __future__ import annotations

import platform

from utils.platform import architecture, hostname, os_name

from .base import Check, CheckResult, Severity


class OSInfoCheck(Check):
    key = "os"
    title = "운영체제"
    weight = 0.05
    quick = True
    icon = "🩺"

    def run(self) -> CheckResult:
        name = os_name()
        arch = architecture()
        host = hostname()
        py = platform.python_version()

        return CheckResult(
            key=self.key,
            title=self.title,
            score=100,
            severity=Severity.HEALTHY,
            summary=f"{name} · {arch}",
            metrics={
                "os": name,
                "arch": arch,
                "hostname": host,
                "python": py,
                "release": platform.release(),
                "version": platform.version(),
            },
            recommendations=[],
            icon=self.icon,
        )
