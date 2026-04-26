"""CPU/GPU temperature & thermal-throttling check.

Sources, in order of preference:
  - psutil.sensors_temperatures() — Linux/some macOS systems
  - LibreHardwareMonitor / OpenHardwareMonitor WMI namespace (Windows, opt-in)
  - MSAcpi_ThermalZoneTemperature (Windows fallback — motherboard ACPI)
"""
from __future__ import annotations

import subprocess
from typing import Any

import psutil

from utils.platform import IS_WINDOWS

from .base import Check, CheckResult, Recommendation, Severity, linear_score, severity_from_score


def _capture(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        return proc.returncode, out, err
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return -1, "", "command failed"


def _powershell_json(script: str, timeout: int = 10) -> Any:
    rc, out, _ = _capture(["powershell", "-NoProfile", "-Command", script], timeout=timeout)
    if rc != 0 or not out:
        return None
    import json
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def _as_list(data: Any) -> list:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return [data]


def _windows_acpi_temps() -> list[dict[str, Any]]:
    """Read CPU temperature via ACPI thermal zones (units: tenths of Kelvin)."""
    data = _powershell_json(
        "Get-CimInstance -Namespace 'root/wmi' -ClassName MSAcpi_ThermalZoneTemperature"
        " -ErrorAction SilentlyContinue |"
        " Select-Object InstanceName, CurrentTemperature |"
        " ConvertTo-Json -Compress"
    )
    sensors: list[dict[str, Any]] = []
    for row in _as_list(data):
        if not isinstance(row, dict):
            continue
        try:
            raw = int(row.get("CurrentTemperature") or 0)
        except (TypeError, ValueError):
            continue
        celsius = (raw / 10.0) - 273.15
        if celsius < -50 or celsius > 200:
            continue
        sensors.append({
            "label": (row.get("InstanceName") or "ACPI Thermal Zone"),
            "current": round(celsius, 1),
            "high": None,
            "critical": None,
        })
    return sensors


def _windows_lhm_temps() -> list[dict[str, Any]]:
    """Read temps from LibreHardwareMonitor / OpenHardwareMonitor if running."""
    sensors: list[dict[str, Any]] = []
    for ns in ("root/LibreHardwareMonitor", "root/OpenHardwareMonitor"):
        data = _powershell_json(
            f"Get-CimInstance -Namespace '{ns}' -ClassName Sensor"
            " -ErrorAction SilentlyContinue |"
            " Where-Object SensorType -eq 'Temperature' |"
            " Select-Object Name, Value |"
            " ConvertTo-Json -Compress",
            timeout=8,
        )
        for row in _as_list(data):
            if not isinstance(row, dict):
                continue
            try:
                value = float(row.get("Value") or 0)
            except (TypeError, ValueError):
                continue
            sensors.append({
                "label": (row.get("Name") or "LHM"),
                "current": round(value, 1),
                "high": None,
                "critical": None,
            })
        if sensors:
            break
    return sensors


class TemperatureCheck(Check):
    key = "temperature"
    title = "온도/발열"
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

        if IS_WINDOWS and not temps:
            lhm = _windows_lhm_temps()
            if lhm:
                temps["LibreHardwareMonitor"] = lhm
            acpi = _windows_acpi_temps()
            if acpi:
                temps["ACPI"] = acpi

        readings = [
            entry["current"]
            for entries in temps.values()
            for entry in entries
            if entry.get("current") is not None
        ]

        if not readings:
            recs: list[Recommendation] = []
            if IS_WINDOWS:
                recs.append(Recommendation(
                    text=(
                        "Windows는 표준 CPU 온도 API가 없습니다. "
                        "정확한 측정을 원하면 LibreHardwareMonitor를 실행하세요 — "
                        "PC Doctor가 자동으로 센서를 읽어옵니다."
                    ),
                    action="open_url",
                    action_label="LibreHardwareMonitor 받기",
                    action_args={"url": "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases"},
                ))
            return CheckResult(
                key=self.key,
                title=self.title,
                score=100,
                severity=Severity.UNKNOWN,
                summary="센서 정보 없음",
                metrics={"sensors": temps},
                recommendations=recs,
                icon=self.icon,
            )

        peak = max(readings)
        score = linear_score(peak, healthy_at=65.0, critical_at=95.0)
        severity = severity_from_score(score)

        recs = []
        if peak >= 90:
            recs.append(Recommendation(
                text=f"발열이 매우 높습니다 ({peak:.0f}℃). 무거운 작업을 멈추고 환기/먼지 제거를 점검하세요.",
                action="open_task_manager",
                action_label="작업 관리자 열기",
            ))
        elif peak >= 80:
            recs.append(Recommendation(
                text=f"온도가 높습니다 ({peak:.0f}℃). 백그라운드 부하를 확인해 주세요.",
                action="open_task_manager",
                action_label="작업 관리자 열기",
            ))

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
