"""Graphics adapter & driver health check.

On Windows the driver date/version is read via WMI (`Win32_VideoController`)
and an old driver triggers a recommendation to update via Device Manager or
the vendor's tool (NVIDIA / AMD / Intel).

On macOS / Linux the check is informational — drivers are managed by the OS
package manager, so we just surface the GPU model.
"""
from __future__ import annotations

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
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return -1, "", "command failed"


def _parse_wmi_date(raw: str) -> datetime | None:
    """WMI dates look like 20240115000000.000000+540 — keep first 14 digits."""
    if not raw or not raw[:8].isdigit():
        return None
    try:
        return datetime.strptime(raw[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _windows_gpus() -> list[dict[str, Any]]:
    ps = (
        "Get-CimInstance Win32_VideoController |"
        " Select-Object Name, DriverVersion, DriverDate, AdapterRAM, Status, VideoProcessor |"
        " ConvertTo-Csv -NoTypeInformation"
    )
    rc, out, _ = _capture(["powershell", "-NoProfile", "-Command", ps], timeout=15)
    gpus: list[dict[str, Any]] = []
    if rc != 0 or not out:
        return gpus

    lines = [ln for ln in out.splitlines() if ln.strip()]
    if len(lines) < 2:
        return gpus
    header = [h.strip().strip('"') for h in lines[0].split(",")]
    for line in lines[1:]:
        # Crude CSV split — values shouldn't contain commas in our selected fields
        parts = [p.strip().strip('"') for p in line.split(",")]
        if len(parts) != len(header):
            continue
        row = dict(zip(header, parts))
        date = _parse_wmi_date(row.get("DriverDate", ""))
        try:
            ram = int(row.get("AdapterRAM") or 0)
        except ValueError:
            ram = 0
        gpus.append({
            "name": row.get("Name") or "Unknown GPU",
            "driver_version": row.get("DriverVersion") or "",
            "driver_date": date.isoformat() if date else None,
            "driver_age_days": (datetime.now(timezone.utc) - date).days if date else None,
            "adapter_ram": ram,
            "status": row.get("Status") or "",
            "processor": row.get("VideoProcessor") or "",
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
                    # Extract vendor/model with regex tolerance
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
        if line.endswith(":") and "Chipset Model" not in line and current is None:
            continue
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
    n = name.lower()
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

        # ── Score & recommendations ──────────────────────────────────────────
        score = 100
        recs: list[Recommendation] = []
        problems: list[str] = []

        for g in gpus:
            name = g.get("name", "GPU")
            status = (g.get("status") or "").lower()
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
        summary_parts = [first.get("name", "GPU")]
        if first.get("driver_version"):
            summary_parts.append(f"드라이버 {first['driver_version']}")
        if first.get("driver_age_days") is not None:
            summary_parts.append(f"{first['driver_age_days']}일 경과")
        summary = " · ".join(summary_parts)

        # Always offer the manual paths as fallback actions
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
