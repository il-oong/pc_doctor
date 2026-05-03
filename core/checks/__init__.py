"""Check registry — order here also defines the dashboard display order."""
from __future__ import annotations

from .base import Check, CheckResult, Recommendation, Severity
from .battery import BatteryCheck
from .cpu import CPUCheck
from .disk import DiskCheck
from .eventlog import EventLogCheck
from .graphics import GraphicsCheck
from .hardware import HardwareCheck
from .memory import MemoryCheck
from .network import NetworkCheck
from .os_info import OSInfoCheck
from .process import ProcessCheck
from .temperature import TemperatureCheck
from .uptime import UptimeCheck
from .windows import WindowsCheck


def all_checks() -> list[Check]:
    return [
        CPUCheck(),
        MemoryCheck(),
        DiskCheck(),
        HardwareCheck(),
        GraphicsCheck(),
        WindowsCheck(),
        EventLogCheck(),
        NetworkCheck(),
        BatteryCheck(),
        TemperatureCheck(),
        ProcessCheck(),
        UptimeCheck(),
        OSInfoCheck(),
    ]


__all__ = ["Check", "CheckResult", "Recommendation", "Severity", "all_checks"]
