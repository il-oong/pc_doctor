"""Check registry — order here also defines the dashboard display order."""
from __future__ import annotations

from .base import Check, CheckResult, Severity
from .battery import BatteryCheck
from .cpu import CPUCheck
from .disk import DiskCheck
from .memory import MemoryCheck
from .network import NetworkCheck
from .os_info import OSInfoCheck
from .process import ProcessCheck
from .temperature import TemperatureCheck
from .uptime import UptimeCheck


def all_checks() -> list[Check]:
    return [
        CPUCheck(),
        MemoryCheck(),
        DiskCheck(),
        NetworkCheck(),
        BatteryCheck(),
        TemperatureCheck(),
        ProcessCheck(),
        UptimeCheck(),
        OSInfoCheck(),
    ]


__all__ = ["Check", "CheckResult", "Severity", "all_checks"]
