"""Windows Event Log health check.

Reads System and Application event logs for the past 24 hours and surfaces
errors / critical events with categorised recommendations.

On non-Windows platforms this returns a HEALTHY result and does not affect
the overall score.
"""
from __future__ import annotations

import json
import subprocess
from typing import Any

from utils.platform import IS_WINDOWS

from .base import Check, CheckResult, Recommendation, Severity


import sys as _sys
_NO_WINDOW = {"creationflags": 0x08000000} if _sys.platform == "win32" else {}


def _powershell(script: str, timeout: int = 30) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=timeout, check=False,
            **_NO_WINDOW,
        )
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return -1, "", "powershell unavailable"


_PS_QUERY = r"""
$cutoff = (Get-Date).AddHours(-24);
$all = [System.Collections.ArrayList]@();
try {
    $s = Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2; StartTime=$cutoff} `
         -MaxEvents 100 -ErrorAction SilentlyContinue;
    if ($s) { $all.AddRange($s) | Out-Null }
} catch {}
try {
    $a = Get-WinEvent -FilterHashtable @{LogName='Application'; Level=1,2; StartTime=$cutoff} `
         -MaxEvents 50 -ErrorAction SilentlyContinue;
    if ($a) { $all.AddRange($a) | Out-Null }
} catch {}
if ($all.Count -eq 0) { '[]'; exit }
$out = $all | ForEach-Object {
    $msg = if ($_.Message) { $_.Message.Substring(0, [Math]::Min(150, $_.Message.Length)) } else { '' }
    [PSCustomObject]@{
        L = [int]$_.Level
        S = $_.ProviderName
        I = [int]$_.Id
        T = $_.TimeCreated.ToString('MM-dd HH:mm')
        M = ($msg -replace '[\r\n]+',' ')
    }
}
($out | ConvertTo-Json -Compress -Depth 2)
"""

# Source names that indicate disk-level problems
_DISK_SOURCES = frozenset({
    "disk", "ntfs", "volsnap", "storahci", "nvme", "atapi",
    "stornvme", "cdrom", "iaStorA", "iaStorAV",
})

# Source names / IDs that indicate driver issues
_DRIVER_SOURCES = frozenset({
    "ndis", "tcpip", "bugcheck", "whea-logger", "wdf01000",
})

# Service Control Manager event IDs meaning service crashed / failed
_SCM_CRASH_IDS = frozenset({7031, 7032, 7034, 7023, 7001, 7003, 7009})

# Kernel-Power / EventLog IDs meaning unexpected shutdown or BSOD
_CRASH_IDS: dict[str, frozenset[int]] = {
    "microsoft-windows-kernel-power": frozenset({41}),
    "eventlog": frozenset({6008}),
}


def _categorise(events: list[dict]) -> dict[str, list[dict]]:
    """Group raw event dicts into named categories."""
    cats: dict[str, list[dict]] = {
        "crash": [],       # BSOD / 예상치 못한 종료
        "disk": [],        # 디스크 / 파일시스템 오류
        "driver": [],      # 드라이버 오류
        "service": [],     # 서비스 실패
        "app": [],         # 앱 오류 (EventID 1000)
        "other": [],       # 기타 오류
    }
    for ev in events:
        src = (ev.get("S") or "").lower()
        eid = ev.get("I", 0)

        # Crash / BSOD
        if any(src == k and eid in v for k, v in _CRASH_IDS.items()):
            cats["crash"].append(ev)
            continue

        # Disk
        if any(ds in src for ds in _DISK_SOURCES):
            cats["disk"].append(ev)
            continue

        # Driver
        if any(ds in src for ds in _DRIVER_SOURCES):
            cats["driver"].append(ev)
            continue

        # Service Control Manager crashes
        if "service control manager" in src and eid in _SCM_CRASH_IDS:
            cats["service"].append(ev)
            continue

        # Application Error / Windows Error Reporting
        if src in {"application error", "windows error reporting"} or eid == 1000:
            cats["app"].append(ev)
            continue

        cats["other"].append(ev)

    return cats


def _fetch_events() -> list[dict[str, Any]]:
    rc, out, _ = _powershell(_PS_QUERY, timeout=35)
    if rc != 0 or not out or out == "[]":
        return []
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        return [d for d in data if isinstance(d, dict)]
    except (json.JSONDecodeError, ValueError):
        return []


class EventLogCheck(Check):
    key = "eventlog"
    title = "이벤트 로그"
    weight = 0.08
    quick = False
    icon = "📋"

    def run(self) -> CheckResult:
        if not IS_WINDOWS:
            return CheckResult(
                key=self.key, title=self.title,
                score=100, severity=Severity.HEALTHY,
                summary="Windows 전용 점검 — 이 OS에서는 비활성화됨",
                metrics={"applicable": False}, recommendations=[],
                icon=self.icon,
            )

        events = _fetch_events()
        cats = _categorise(events)

        critical_count = sum(1 for e in events if e.get("L") == 1)
        error_count    = sum(1 for e in events if e.get("L") == 2)
        total          = len(events)

        score = 100
        recs: list[Recommendation] = []
        problems: list[str] = []

        # ── BSOD / 예상치 못한 종료 ────────────────────────────────────────
        if cats["crash"]:
            score -= 35
            problems.append(f"시스템 충돌 {len(cats['crash'])}건")
            sample = cats["crash"][0]
            recs.append(Recommendation(
                text=(
                    f"최근 24시간 내 예상치 못한 종료/충돌이 {len(cats['crash'])}건 감지됐습니다 "
                    f"(이벤트 ID {sample.get('I')}, {sample.get('T')}). "
                    "메모리·온도·드라이버를 확인하세요."
                ),
                action="open_event_viewer",
                action_label="이벤트 뷰어 열기",
            ))

        # ── 디스크 오류 ────────────────────────────────────────────────────
        if cats["disk"]:
            penalty = min(30, len(cats["disk"]) * 8)
            score -= penalty
            problems.append(f"디스크 오류 {len(cats['disk'])}건")
            recs.append(Recommendation(
                text=(
                    f"디스크/파일시스템 오류 {len(cats['disk'])}건 감지. "
                    "데이터 손실 위험 — 중요 파일을 백업하고 디스크 검사를 실행하세요."
                ),
                action="run_chkdsk",
                action_label="온라인 디스크 검사",
                action_args={"drive": "C:"},
            ))
            recs.append(Recommendation(
                text="오류 수정이 필요하면 다음 재부팅 시 자동 검사를 예약하세요.",
                action="schedule_chkdsk",
                action_label="재부팅 시 검사 예약",
                action_args={"drive": "C:"},
            ))

        # ── 드라이버 오류 ──────────────────────────────────────────────────
        if cats["driver"]:
            penalty = min(20, len(cats["driver"]) * 5)
            score -= penalty
            problems.append(f"드라이버 오류 {len(cats['driver'])}건")
            recs.append(Recommendation(
                text=(
                    f"드라이버 관련 오류 {len(cats['driver'])}건. "
                    "Windows Update 또는 제조사 사이트에서 드라이버를 업데이트하세요."
                ),
                action="open_device_manager",
                action_label="장치 관리자 열기",
            ))

        # ── 서비스 실패 ────────────────────────────────────────────────────
        if cats["service"]:
            penalty = min(15, len(cats["service"]) * 4)
            score -= penalty
            problems.append(f"서비스 실패 {len(cats['service'])}건")
            sample = cats["service"][0]
            recs.append(Recommendation(
                text=(
                    f"서비스 비정상 종료 {len(cats['service'])}건 "
                    f"(최근: {sample.get('T')}, {sample.get('M', '')[:60]}). "
                    "서비스 관리자에서 상태를 확인하세요."
                ),
                action="open_services",
                action_label="서비스 관리자 열기",
            ))

        # ── 앱 오류 ────────────────────────────────────────────────────────
        if cats["app"]:
            penalty = min(10, len(cats["app"]) * 2)
            score -= penalty
            if len(cats["app"]) >= 3:
                problems.append(f"앱 오류 {len(cats['app'])}건")
                recs.append(Recommendation(
                    text=(
                        f"응용 프로그램 오류 {len(cats['app'])}건. "
                        "해당 앱을 재설치하거나 업데이트하세요."
                    ),
                    action="open_event_viewer",
                    action_label="이벤트 뷰어 열기",
                ))

        # ── 기타 오류 (다수일 때만 표시) ──────────────────────────────────
        if cats["other"] and len(cats["other"]) >= 5:
            score -= min(10, len(cats["other"]) * 1)

        # Critical events 추가 감점
        if critical_count > 0:
            score -= min(15, critical_count * 5)

        score = max(0, min(100, score))

        if score >= 90:
            severity = Severity.HEALTHY
            summary = f"이벤트 로그 양호 (24h 오류 {error_count}건, 위험 {critical_count}건)"
        elif score >= 70:
            severity = Severity.WARNING
            summary = " · ".join(problems) if problems else f"오류 {total}건 감지"
        else:
            severity = Severity.CRITICAL
            summary = " · ".join(problems) if problems else f"심각한 오류 {total}건"

        if not recs:
            recs.append(Recommendation(
                text="이벤트 뷰어에서 전체 로그를 직접 확인할 수 있습니다.",
                action="open_event_viewer",
                action_label="이벤트 뷰어 열기",
            ))

        return CheckResult(
            key=self.key, title=self.title,
            score=score, severity=severity,
            summary=summary,
            metrics={
                "applicable": True,
                "total_24h": total,
                "critical": critical_count,
                "errors": error_count,
                "crash": len(cats["crash"]),
                "disk_errors": len(cats["disk"]),
                "driver_errors": len(cats["driver"]),
                "service_failures": len(cats["service"]),
                "app_errors": len(cats["app"]),
            },
            recommendations=recs,
            icon=self.icon,
        )
