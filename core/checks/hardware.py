"""Hard drive health check — SMART status & physical disk diagnostics.

This check goes beyond `disk.py` (which looks at free space). It inspects the
physical drive's predictive failure status using whatever facility the OS
makes available: Windows WMI (`wmic diskdrive`), or `smartctl` on
macOS/Linux when installed.

If no health source is available, the result is reported as UNKNOWN with a
helpful recommendation for installing `smartmontools`.
"""
from __future__ import annotations

import shutil
import subprocess
from typing import Any

import psutil

from utils.format import bytes_human
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


def _windows_disk_status() -> list[dict[str, Any]]:
    """Use WMIC to fetch per-physical-disk SMART predictive status."""
    rc, out, _ = _capture(
        ["wmic", "diskdrive", "get", "Model,Status,Size,MediaType", "/format:csv"],
        timeout=15,
    )
    drives: list[dict[str, Any]] = []
    if rc != 0 or not out:
        return drives
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if len(lines) < 2:
        return drives
    header = [h.strip() for h in lines[0].split(",")]
    for line in lines[1:]:
        cells = [c.strip() for c in line.split(",")]
        if len(cells) != len(header):
            continue
        row = dict(zip(header, cells))
        try:
            size = int(row.get("Size") or 0)
        except ValueError:
            size = 0
        drives.append({
            "model": row.get("Model") or "Unknown",
            "status": row.get("Status") or "Unknown",
            "media": row.get("MediaType") or "",
            "size": size,
            "size_human": bytes_human(size) if size else "",
        })
    return drives


def _smartctl_status(device: str) -> dict[str, Any] | None:
    rc, out, _ = _capture(["smartctl", "-H", device], timeout=10)
    if rc < 0 or not out:
        return None
    healthy = "PASSED" in out.upper() or "OK" in out.upper()
    failed = "FAILED" in out.upper() or "FAILING" in out.upper()
    return {
        "device": device,
        "healthy": healthy,
        "failed": failed,
        "raw": out,
    }


def _unix_disk_devices() -> list[str]:
    """Return distinct physical device paths from psutil partitions."""
    seen: list[str] = []
    for part in psutil.disk_partitions(all=False):
        dev = part.device
        if not dev or not dev.startswith("/dev/"):
            continue
        # /dev/sda1 -> /dev/sda; /dev/nvme0n1p1 -> /dev/nvme0n1
        base = dev.rstrip("0123456789")
        if base.endswith("p"):
            base = base[:-1]
        if base not in seen:
            seen.append(base)
    return seen


class HardwareCheck(Check):
    key = "hardware"
    title = "하드웨어"
    weight = 0.10
    quick = False
    icon = "🛠"

    def run(self) -> CheckResult:
        drives: list[dict[str, Any]] = []
        unhealthy: list[str] = []
        unknown_source = False

        if IS_WINDOWS:
            drives = _windows_disk_status()
            if not drives:
                unknown_source = True
            else:
                for d in drives:
                    status = (d.get("status") or "").lower()
                    if status and status != "ok":
                        unhealthy.append(f"{d['model']} ({status})")

        elif IS_LINUX or IS_MACOS:
            if shutil.which("smartctl"):
                for dev in _unix_disk_devices() or ["/dev/sda"]:
                    info = _smartctl_status(dev)
                    if info is None:
                        continue
                    drives.append({
                        "model": dev,
                        "status": "FAILED" if info["failed"] else ("OK" if info["healthy"] else "UNKNOWN"),
                        "device": dev,
                        "size": 0,
                        "size_human": "",
                    })
                    if info["failed"]:
                        unhealthy.append(dev)
                if not drives:
                    unknown_source = True
            else:
                unknown_source = True
        else:
            unknown_source = True

        # ── Build result ─────────────────────────────────────────────────────
        if unknown_source:
            recs: list[Recommendation] = []
            if not IS_WINDOWS:
                recs.append(Recommendation(
                    text="`smartmontools`(smartctl)를 설치하면 디스크 SMART 상태를 점검할 수 있습니다.",
                ))
            recs.append(Recommendation(
                text="현재 하드웨어 보고서를 확인합니다.",
                action="open_smart_report",
                action_label="하드웨어 보고서 보기",
            ))
            return CheckResult(
                key=self.key,
                title=self.title,
                score=100,
                severity=Severity.UNKNOWN,
                summary="하드웨어 상태 정보를 가져올 수 없습니다.",
                metrics={"drives": drives, "source": "none"},
                recommendations=recs,
                icon=self.icon,
            )

        if unhealthy:
            recs = [
                Recommendation(
                    text=f"디스크 이상 신호: {', '.join(unhealthy)}. 즉시 백업 후 교체를 검토하세요.",
                ),
                Recommendation(
                    text="디스크 검사(chkdsk)를 실행해 파일시스템 오류를 확인합니다.",
                    action="run_chkdsk",
                    action_label="디스크 검사 실행",
                ),
                Recommendation(
                    text="장치 관리자에서 드라이브 상세 상태를 확인합니다.",
                    action="open_device_manager",
                    action_label="장치 관리자 열기",
                ),
            ]
            return CheckResult(
                key=self.key,
                title=self.title,
                score=20,
                severity=Severity.CRITICAL,
                summary=f"이상 디스크 {len(unhealthy)}개 / 총 {len(drives)}개",
                metrics={"drives": drives, "unhealthy": unhealthy},
                recommendations=recs,
                icon=self.icon,
            )

        # All healthy — but still expose the optimize/check actions for SSDs/HDDs.
        recs = []
        if IS_WINDOWS:
            recs.append(Recommendation(
                text="정기적으로 드라이브 최적화(트림/조각모음)를 실행하면 수명에 도움이 됩니다.",
                action="open_optimize_drives",
                action_label="드라이브 최적화 열기",
            ))

        return CheckResult(
            key=self.key,
            title=self.title,
            score=100,
            severity=Severity.HEALTHY,
            summary=f"모든 디스크 정상 · {len(drives)}개 드라이브",
            metrics={"drives": drives},
            recommendations=recs,
            icon=self.icon,
        )
