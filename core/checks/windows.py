"""Windows-specific health check: pending updates, Defender, system files.

On non-Windows platforms this returns a HEALTHY result with a short note —
it doesn't drag down the overall score, since the user can't act on it.
"""
from __future__ import annotations

import subprocess
from typing import Any

from utils.platform import IS_WINDOWS

from .base import Check, CheckResult, Recommendation, Severity


def _powershell(script: str, timeout: int = 25) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        return proc.returncode, out, err
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return -1, "", "powershell unavailable"


def _check_defender() -> dict[str, Any]:
    """Returns dict: { available, realtime, signature_age_days, last_scan_days }."""
    ps = (
        "$s = Get-MpComputerStatus -ErrorAction SilentlyContinue;"
        " if ($s) {"
        "  '{0}|{1}|{2}|{3}' -f"
        "  $s.RealTimeProtectionEnabled,"
        "  ([int]((Get-Date) - $s.AntivirusSignatureLastUpdated).TotalDays),"
        "  ([int]((Get-Date) - $s.QuickScanEndTime).TotalDays),"
        "  $s.AntivirusEnabled"
        " }"
    )
    rc, out, _ = _powershell(ps, timeout=15)
    if rc != 0 or not out:
        return {"available": False}
    try:
        rt, sig_age, scan_age, av_on = out.split("|")
        return {
            "available": True,
            "realtime": rt.strip().lower() == "true",
            "av_enabled": av_on.strip().lower() == "true",
            "signature_age_days": int(sig_age),
            "last_scan_days": int(scan_age),
        }
    except (ValueError, IndexError):
        return {"available": False}


def _check_pending_reboot() -> bool:
    """Detects the well-known registry markers for pending reboots."""
    ps = (
        "$paths = @("
        " 'HKLM:Software\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending',"
        " 'HKLM:Software\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired'"
        ");"
        " $found = $false;"
        " foreach ($p in $paths) { if (Test-Path $p) { $found = $true } };"
        " if ($found) { 'YES' } else { 'NO' }"
    )
    rc, out, _ = _powershell(ps, timeout=10)
    return rc == 0 and out.strip().upper() == "YES"


def _check_pending_updates() -> int | None:
    """Best-effort: count pending Windows Updates.

    Querying WUA can be slow; we cap with a timeout and return None on
    failure so the check still produces a useful result.
    """
    ps = (
        "$s = New-Object -ComObject Microsoft.Update.Session;"
        " $u = $s.CreateUpdateSearcher();"
        " ($u.Search('IsInstalled=0 and Type=\\'Software\\'')).Updates.Count"
    )
    rc, out, _ = _powershell(ps, timeout=20)
    if rc != 0:
        return None
    try:
        return int(out.strip())
    except (ValueError, TypeError):
        return None


def _check_failed_updates() -> int | None:
    """Count Windows Update install failures in the last 30 days."""
    ps = (
        "$s = New-Object -ComObject Microsoft.Update.Session;"
        " $h = $s.QueryHistory(0, 50);"
        " $cutoff = (Get-Date).AddDays(-30);"
        " ($h | Where-Object { $_.ResultCode -ne 2 -and $_.Date -gt $cutoff }).Count"
    )
    rc, out, _ = _powershell(ps, timeout=15)
    if rc != 0:
        return None
    try:
        return int(out.strip())
    except (ValueError, TypeError):
        return None


def _check_install_conflicts() -> dict[str, Any]:
    """Detect installer conflicts: pending MSI lock, hung Windows Installer service.

    Returns: {
       'msi_inprogress': bool,   # HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Installer\\InProgress
       'rename_pending': bool,   # PendingFileRenameOperations registry key
       'wuauserv_status': str,   # service state for Windows Update
    }
    """
    ps = (
        "$msi = Test-Path 'HKLM:Software\\Microsoft\\Windows\\CurrentVersion\\Installer\\InProgress';"
        " $rename = $false;"
        " try {"
        "  $val = Get-ItemProperty 'HKLM:SYSTEM\\CurrentControlSet\\Control\\Session Manager'"
        "         -Name PendingFileRenameOperations -ErrorAction Stop;"
        "  if ($val.PendingFileRenameOperations) { $rename = $true }"
        " } catch { }"
        " $svc = (Get-Service wuauserv -ErrorAction SilentlyContinue).Status;"
        " '{0}|{1}|{2}' -f $msi, $rename, $svc"
    )
    rc, out, _ = _powershell(ps, timeout=10)
    if rc != 0 or not out or "|" not in out:
        return {"msi_inprogress": False, "rename_pending": False, "wuauserv_status": ""}
    try:
        msi, rename, svc = out.split("|", 2)
        return {
            "msi_inprogress": msi.strip().lower() == "true",
            "rename_pending": rename.strip().lower() == "true",
            "wuauserv_status": svc.strip(),
        }
    except ValueError:
        return {"msi_inprogress": False, "rename_pending": False, "wuauserv_status": ""}


def _check_firewall() -> dict[str, bool] | None:
    ps = (
        "(Get-NetFirewallProfile -ErrorAction SilentlyContinue) |"
        " ForEach-Object { '{0}={1}' -f $_.Name, $_.Enabled } | Out-String"
    )
    rc, out, _ = _powershell(ps, timeout=10)
    if rc != 0 or not out:
        return None
    profiles: dict[str, bool] = {}
    for line in out.splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        name, val = line.split("=", 1)
        profiles[name.strip()] = val.strip().lower() == "true"
    return profiles or None


class WindowsCheck(Check):
    key = "windows"
    title = "Windows 점검"
    weight = 0.10
    quick = False
    icon = "🪟"

    def run(self) -> CheckResult:
        if not IS_WINDOWS:
            return CheckResult(
                key=self.key,
                title=self.title,
                score=100,
                severity=Severity.HEALTHY,
                summary="Windows 전용 점검 — 이 OS에서는 비활성화됨",
                metrics={"applicable": False},
                recommendations=[],
                icon=self.icon,
            )

        defender = _check_defender()
        pending_reboot = _check_pending_reboot()
        pending_updates = _check_pending_updates()
        firewall = _check_firewall()
        failed_updates = _check_failed_updates()
        conflicts = _check_install_conflicts()

        score = 100
        recs: list[Recommendation] = []
        problems: list[str] = []

        # ── Defender ────────────────────────────────────────────────────────
        if defender.get("available"):
            if not defender.get("av_enabled", True):
                score -= 35
                problems.append("Defender 비활성")
                recs.append(Recommendation(
                    text="Windows Defender가 비활성화되어 있습니다. 보안 센터에서 활성화하세요.",
                    action="open_defender",
                    action_label="보안 센터 열기",
                ))
            elif not defender.get("realtime", True):
                score -= 20
                problems.append("실시간 보호 꺼짐")
                recs.append(Recommendation(
                    text="실시간 보호가 꺼져 있습니다. 즉시 켜는 것을 권장합니다.",
                    action="open_defender",
                    action_label="보안 센터 열기",
                ))
            sig_age = defender.get("signature_age_days", 0) or 0
            if sig_age > 7:
                score -= 15
                problems.append(f"정의 {sig_age}일 경과")
                recs.append(Recommendation(
                    text=f"바이러스 정의가 {sig_age}일 동안 업데이트되지 않았습니다.",
                    action="update_defender_signatures",
                    action_label="정의 업데이트",
                ))
            scan_age = defender.get("last_scan_days", 0) or 0
            if scan_age > 14:
                score -= 10
                problems.append(f"마지막 검사 {scan_age}일 전")
                recs.append(Recommendation(
                    text=f"마지막 빠른 검사가 {scan_age}일 전입니다. 검사를 실행하세요.",
                    action="run_defender_scan",
                    action_label="빠른 검사 실행",
                    action_args={"scan_type": "QuickScan"},
                ))

        # ── Pending updates ─────────────────────────────────────────────────
        if pending_updates is not None and pending_updates > 0:
            if pending_updates >= 10:
                score -= 25
            elif pending_updates >= 3:
                score -= 15
            else:
                score -= 5
            problems.append(f"보류 업데이트 {pending_updates}개")
            recs.append(Recommendation(
                text=f"설치되지 않은 Windows 업데이트가 {pending_updates}개 있습니다.",
                action="open_windows_update",
                action_label="Windows Update 열기",
            ))

        # ── Pending reboot ──────────────────────────────────────────────────
        if pending_reboot:
            score -= 15
            problems.append("재부팅 대기")
            recs.append(Recommendation(
                text="설치된 업데이트 적용을 위해 재부팅이 필요합니다.",
                action="restart_pc",
                action_label="지금 재시작",
                confirm="60초 후 PC를 재시작합니다. 진행할까요?",
                action_args={"delay_sec": 60},
            ))

        # ── Update install failures (last 30 days) ──────────────────────────
        if failed_updates and failed_updates > 0:
            score -= min(20, failed_updates * 5)
            problems.append(f"업데이트 설치 실패 {failed_updates}건")
            recs.append(Recommendation(
                text=(
                    f"최근 30일간 업데이트 설치에 {failed_updates}건 실패했습니다. "
                    "Windows Update 진단을 시도하세요."
                ),
                action="open_windows_update",
                action_label="Windows Update 열기",
            ))

        # ── Installer / file rename conflicts ──────────────────────────────
        if conflicts.get("msi_inprogress"):
            score -= 15
            problems.append("MSI 설치 진행 중/잠김")
            recs.append(Recommendation(
                text=(
                    "다른 Windows Installer 작업이 진행 중이거나 비정상 종료된 흔적이 있습니다. "
                    "재부팅 후 다시 시도해 주세요."
                ),
                action="restart_pc",
                action_label="지금 재시작",
                confirm="60초 후 PC를 재시작합니다. 진행할까요?",
                action_args={"delay_sec": 60},
            ))
        if conflicts.get("rename_pending"):
            score -= 10
            problems.append("파일 교체 대기")
            recs.append(Recommendation(
                text=(
                    "파일 교체가 다음 부팅에 예약되어 있습니다 (PendingFileRenameOperations). "
                    "프로그램 설치/제거가 마무리되지 않은 상태일 수 있습니다."
                ),
                action="restart_pc",
                action_label="지금 재시작",
                confirm="60초 후 PC를 재시작합니다. 진행할까요?",
                action_args={"delay_sec": 60},
            ))
        wu_status = (conflicts.get("wuauserv_status") or "").lower()
        if wu_status and wu_status not in ("running", "stoppending", "startpending", ""):
            score -= 5
            problems.append(f"Windows Update 서비스 {wu_status}")

        # ── Firewall ────────────────────────────────────────────────────────
        if firewall is not None:
            disabled = [name for name, enabled in firewall.items() if not enabled]
            if disabled:
                score -= 10
                problems.append(f"방화벽 비활성: {', '.join(disabled)}")
                recs.append(Recommendation(
                    text=f"Windows 방화벽 프로필이 비활성화되어 있습니다: {', '.join(disabled)}",
                    action="open_defender",
                    action_label="보안 센터 열기",
                ))

        score = max(0, min(100, score))
        if score >= 90:
            severity = Severity.HEALTHY
            summary = "Windows 상태 양호"
        elif score >= 70:
            severity = Severity.WARNING
            summary = " · ".join(problems) if problems else "주의 필요"
        else:
            severity = Severity.CRITICAL
            summary = " · ".join(problems) if problems else "위험"

        # Always offer quick maintenance shortcuts even when healthy
        if not recs:
            recs.append(Recommendation(
                text="시스템 파일 무결성을 점검합니다 (관리자 권한 필요).",
                action="run_sfc_scan",
                action_label="SFC 검사 실행",
            ))

        return CheckResult(
            key=self.key,
            title=self.title,
            score=score,
            severity=severity,
            summary=summary,
            metrics={
                "applicable": True,
                "defender": defender,
                "pending_reboot": pending_reboot,
                "pending_updates": pending_updates,
                "failed_updates": failed_updates,
                "conflicts": conflicts,
                "firewall": firewall,
            },
            recommendations=recs,
            icon=self.icon,
        )
