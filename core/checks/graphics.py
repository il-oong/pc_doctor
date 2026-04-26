"""Graphics adapter & driver health check.

Sources:
  - Windows: PowerShell `Get-CimInstance Win32_VideoController` → JSON
  - macOS:   `system_profiler SPDisplaysDataType`
  - Linux:   `lspci`

Empty / null fields and embedded commas are handled by parsing JSON instead
of CSV. All field accesses go through helpers that coerce None → safe defaults.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any

from utils.platform import IS_LINUX, IS_MACOS, IS_WINDOWS

from .base import Check, CheckResult, Recommendation, Severity


def _capture(cmd: list[str], timeout: int = 15) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        return proc.returncode, out, err
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return -1, "", "command failed"


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _parse_wmi_date(raw: Any) -> datetime | None:
    """WMI dates look like 20240115000000.000000+540 — keep first 14 digits.

    Also handles `/Date(1717286400000)/` JSON form returned by some
    PowerShell versions when serializing CIM datetime objects.
    """
    s = _safe_str(raw).strip()
    if not s:
        return None

    # /Date(epoch_ms)/
    m = re.match(r"/Date\((-?\d+)\)/", s)
    if m:
        try:
            return datetime.fromtimestamp(int(m.group(1)) / 1000.0, tz=timezone.utc)
        except (ValueError, OSError):
            return None

    # WMI string form
    if s[:8].isdigit():
        try:
            return datetime.strptime(s[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _windows_gpus() -> list[dict[str, Any]]:
    ps = (
        "Get-CimInstance Win32_VideoController |"
        " Select-Object Name, DriverVersion, DriverDate, AdapterRAM, Status, VideoProcessor |"
        " ConvertTo-Json -Compress"
    )
    rc, out, _ = _capture(["powershell", "-NoProfile", "-Command", ps], timeout=15)
    gpus: list[dict[str, Any]] = []
    if rc != 0 or not out:
        return gpus

    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return gpus

    # Single object → wrap; multiple → already list
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return gpus

    for row in data:
        if not isinstance(row, dict):
            continue
        date = _parse_wmi_date(row.get("DriverDate"))
        try:
            ram = int(row.get("AdapterRAM") or 0)
        except (TypeError, ValueError):
            ram = 0
        gpus.append({
            "name": _safe_str(row.get("Name")) or "Unknown GPU",
            "driver_version": _safe_str(row.get("DriverVersion")),
            "driver_date": date.isoformat() if date else None,
            "driver_age_days": (datetime.now(timezone.utc) - date).days if date else None,
            "adapter_ram": ram,
            "status": _safe_str(row.get("Status")),
            "processor": _safe_str(row.get("VideoProcessor")),
        })
    return gpus


def _linux_gpus() -> list[dict[str, Any]]:
    gpus: list[dict[str, Any]] = []
    if shutil.which("lspci"):
        rc, out, _ = _capture(["lspci", "-mm"], timeout=10)
        if rc == 0:
            for line in out.splitlines():
                low = line.lower()
                if "vga" in low or "3d" in low or "display" in low:
                    m = re.findall(r'"([^"]+)"', line)
                    if len(m) >= 4:
                        gpus.append({
                            "name": f"{m[2]} {m[3]}",
                            "driver_version": "",
                            "driver_date": None,
                            "driver_age_days": None,
                        })
    return gpus


def _macos_gpus() -> list[dict[str, Any]]:
    rc, out, _ = _capture(["system_profiler", "SPDisplaysDataType"], timeout=15)
    gpus: list[dict[str, Any]] = []
    if rc != 0 or not out:
        return gpus
    current: dict[str, Any] | None = None
    for raw in out.splitlines():
        line = raw.strip()
        if line.startswith("Chipset Model:"):
            if current:
                gpus.append(current)
            current = {
                "name": line.split(":", 1)[1].strip(),
                "driver_version": "",
                "driver_date": None,
                "driver_age_days": None,
            }
    if current:
        gpus.append(current)
    return gpus


def _vendor_of(name: str) -> str:
    n = (name or "").lower()
    if "nvidia" in n or "geforce" in n or "rtx" in n or "gtx" in n or "quadro" in n:
        return "nvidia"
    if "amd" in n or "radeon" in n or "ryzen" in n:
        return "amd"
    if "intel" in n or "uhd" in n or "iris" in n:
        return "intel"
    return "unknown"


class GraphicsCheck(Check):
    key = "graphics"
    title = "그래픽"
    weight = 0.05
    quick = False
    icon = "🎮"

    def run(self) -> CheckResult:
        if IS_WINDOWS:
            gpus = _windows_gpus()
        elif IS_MACOS:
            gpus = _macos_gpus()
        elif IS_LINUX:
            gpus = _linux_gpus()
        else:
            gpus = []

        if not gpus:
            return CheckResult(
                key=self.key,
                title=self.title,
                score=100,
                severity=Severity.UNKNOWN,
                summary="GPU 정보를 가져올 수 없습니다.",
                metrics={"gpus": []},
                recommendations=[Recommendation(
                    text="장치 관리자에서 그래픽 어댑터 상태를 직접 확인하세요.",
                    action="open_device_manager",
                    action_label="장치 관리자 열기",
                )],
                icon=self.icon,
            )

        score = 100
        recs: list[Recommendation] = []
        problems: list[str] = []

        for g in gpus:
            name = _safe_str(g.get("name")) or "GPU"
            status = _safe_str(g.get("status")).lower()
            if status and status not in ("ok", ""):
                score -= 30
                problems.append(f"{name} 이상 ({status})")
                recs.append(Recommendation(
                    text=f"{name}의 상태가 비정상입니다 ({status}). 장치 관리자에서 확인하세요.",
                    action="open_device_manager",
                    action_label="장치 관리자 열기",
                ))

            age = g.get("driver_age_days")
            if isinstance(age, int):
                if age >= 365:
                    score -= 20
                    problems.append(f"{name} 드라이버 {age}일 경과")
                    recs.append(_driver_update_rec(name, age))
                elif age >= 180:
                    score -= 10
                    problems.append(f"{name} 드라이버 노화")
                    recs.append(_driver_update_rec(name, age))

        score = max(0, min(100, score))
        if score >= 90:
            severity = Severity.HEALTHY
        elif score >= 70:
            severity = Severity.WARNING
        else:
            severity = Severity.CRITICAL

        first = gpus[0]
        summary_parts = [_safe_str(first.get("name")) or "GPU"]
        ver = _safe_str(first.get("driver_version"))
        if ver:
            summary_parts.append(f"드라이버 {ver}")
        age = first.get("driver_age_days")
        if isinstance(age, int):
            summary_parts.append(f"{age}일 경과")
        summary = " · ".join(summary_parts)

        if not recs:
            recs.append(Recommendation(
                text="그래픽 드라이버를 최신 상태로 유지하면 안정성과 성능이 향상됩니다.",
                action="open_device_manager",
                action_label="장치 관리자 열기",
            ))

        return CheckResult(
            key=self.key,
            title=self.title,
            score=score,
            severity=severity,
            summary=summary,
            metrics={"gpus": gpus, "problems": problems},
            recommendations=recs,
            icon=self.icon,
        )


def _driver_update_rec(name: str, age_days: int) -> Recommendation:
    vendor = _vendor_of(name)
    if vendor == "nvidia":
        return Recommendation(
            text=f"{name} 드라이버가 {age_days}일 동안 업데이트되지 않았습니다. NVIDIA 드라이버 페이지를 엽니다.",
            action="open_url",
            action_label="NVIDIA 드라이버 다운로드",
            action_args={"url": "https://www.nvidia.co.kr/Download/index.aspx?lang=kr"},
        )
    if vendor == "amd":
        return Recommendation(
            text=f"{name} 드라이버가 {age_days}일 동안 업데이트되지 않았습니다. AMD 드라이버 페이지를 엽니다.",
            action="open_url",
            action_label="AMD 드라이버 다운로드",
            action_args={"url": "https://www.amd.com/ko/support"},
        )
    if vendor == "intel":
        return Recommendation(
            text=f"{name} 드라이버가 {age_days}일 동안 업데이트되지 않았습니다. Intel 드라이버 도우미를 엽니다.",
            action="open_url",
            action_label="Intel 드라이버 도우미",
            action_args={"url": "https://www.intel.co.kr/content/www/kr/ko/support/detect.html"},
        )
    return Recommendation(
        text=f"{name} 드라이버가 {age_days}일 동안 업데이트되지 않았습니다. 장치 관리자에서 업데이트를 시도하세요.",
        action="open_device_manager",
        action_label="장치 관리자 열기",
    )
