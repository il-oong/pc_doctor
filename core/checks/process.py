"""Top resource-consuming processes (excluding kernel/idle)."""
from __future__ import annotations

import psutil

from core import process_baseline

from .base import Check, CheckResult, Recommendation, Severity, linear_score, severity_from_score


# Processes that report inflated CPU% but represent the system being idle
# or kernel work — they should not count as "heavy" processes.
_IGNORE_NAMES = {
    # Windows
    "system idle process",
    "idle",
    "system",
    "registry",
    "memory compression",
    "secure system",
    # macOS
    "kernel_task",
    # Linux: kthreads have empty/bracketed names — filtered separately
}
_IGNORE_PIDS = {0}  # Windows System Idle = 0; Linux pid 0 doesn't appear


def _is_kernel_or_idle(name: str, pid: int) -> bool:
    if pid in _IGNORE_PIDS:
        return True
    n = (name or "").strip().lower()
    if not n or n in _IGNORE_NAMES:
        return True
    # Linux kernel threads usually surface with bracketed names ([kworker/...]),
    # but psutil strips the brackets — fall back to status check.
    return False


class ProcessCheck(Check):
    key = "process"
    title = "프로세스"
    weight = 0.05
    quick = False
    icon = "⚙"

    def run(self) -> CheckResult:
        cpu_count = psutil.cpu_count(logical=True) or 1

        # Prime cpu_percent so it doesn't return 0 for everyone
        for p in psutil.process_iter(["pid", "name", "status"]):
            try:
                p.cpu_percent(None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Brief settle to get meaningful CPU reading
        psutil.cpu_percent(interval=0.3)

        procs: list[dict] = []
        zombies = 0
        for p in psutil.process_iter(["pid", "name", "username", "status"]):
            try:
                pid = p.info["pid"]
                name = p.info.get("name") or "?"
                # Linux kernel threads commonly have ppid=2 — filter those too
                if pid != 0:
                    try:
                        if p.ppid() == 2 and not psutil.WINDOWS:
                            continue
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                if _is_kernel_or_idle(name, pid):
                    continue

                cpu = p.cpu_percent(None)
                mem = p.memory_percent()
                status = p.info.get("status")
                if status == psutil.STATUS_ZOMBIE:
                    zombies += 1
                try:
                    exe = p.exe() or ""
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    exe = ""
                # Normalize CPU% so 100% means "one full core" — comparable across machines
                cpu_per_core = cpu / cpu_count
                procs.append({
                    "pid": pid,
                    "name": name,
                    "exe": exe,
                    "user": p.info.get("username") or "",
                    "cpu": cpu,
                    "cpu_per_core": cpu_per_core,
                    "memory": mem,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        top_cpu = sorted(procs, key=lambda x: x["cpu"], reverse=True)[:5]
        top_mem = sorted(procs, key=lambda x: x["memory"], reverse=True)[:5]

        heaviest_cpu = top_cpu[0]["cpu"] if top_cpu else 0
        heaviest_cpu_pc = top_cpu[0]["cpu_per_core"] if top_cpu else 0
        heaviest_mem = top_mem[0]["memory"] if top_mem else 0

        # Score against system-relative load (per-core), not absolute multi-core %.
        cpu_score = linear_score(heaviest_cpu_pc, healthy_at=40.0, critical_at=95.0)
        mem_score = linear_score(heaviest_mem, healthy_at=20.0, critical_at=70.0)
        score = int(round((cpu_score + mem_score) / 2))
        if zombies > 5:
            score = min(score, 60)
        severity = severity_from_score(score)

        recs: list[Recommendation] = []
        if heaviest_cpu_pc >= 80 and top_cpu:
            top = top_cpu[0]
            recs.append(Recommendation(
                text=f"`{top['name']}` (PID {top['pid']}) 프로세스가 CPU를 많이 사용합니다.",
                action="kill_process",
                action_label=f"`{top['name']}` 종료",
                confirm=f"`{top['name']}` (PID {top['pid']}) 프로세스를 강제 종료합니다. 진행할까요?\n저장하지 않은 작업은 사라질 수 있습니다.",
                action_args={"pid": top["pid"], "name": top["name"]},
            ))
            recs.append(Recommendation(
                text="작업 관리자에서 다른 프로세스도 함께 확인하세요.",
                action="open_task_manager",
                action_label="작업 관리자 열기",
            ))
        if heaviest_mem >= 30 and top_mem:
            top = top_mem[0]
            recs.append(Recommendation(
                text=f"`{top['name']}` (PID {top['pid']}) 프로세스가 메모리를 많이 사용합니다.",
                action="kill_process",
                action_label=f"`{top['name']}` 종료",
                confirm=f"`{top['name']}` (PID {top['pid']}) 프로세스를 강제 종료합니다. 진행할까요?\n저장하지 않은 작업은 사라질 수 있습니다.",
                action_args={"pid": top["pid"], "name": top["name"]},
            ))
        if zombies > 5:
            recs.append(Recommendation(
                text=f"좀비 프로세스가 {zombies}개 있습니다. 시스템 재시작을 고려해 주세요.",
                action="restart_pc",
                action_label="지금 재시작",
                confirm="60초 후 PC를 재시작합니다. 진행할까요?",
                action_args={"delay_sec": 60},
            ))

        # ── First-time-seen process detection ────────────────────────────────
        new_procs, first_run = process_baseline.diff(procs)
        if first_run:
            recs.append(Recommendation(
                text=(
                    "프로세스 baseline을 처음 기록했습니다. "
                    "다음 검진부터는 새로 등장한 프로세스를 자동으로 알려드립니다."
                ),
            ))
        for np in new_procs[:8]:  # cap to keep UI tidy
            exe_short = np.get("exe") or "(경로 미확인)"
            recs.append(Recommendation(
                text=(
                    f"⚠ 이전에 보지 못했던 프로세스: `{np['name']}` "
                    f"(PID {np['pid']})\n경로: {exe_short}"
                ),
                action="kill_process",
                action_label=f"`{np['name']}` 종료",
                confirm=(
                    f"`{np['name']}` (PID {np['pid']}) 를 종료합니다.\n"
                    "정상 프로세스라면 '신뢰' 버튼을 누르세요. 진행할까요?"
                ),
                action_args={"pid": np["pid"], "name": np["name"]},
            ))
            recs.append(Recommendation(
                text=f"`{np['name']}` 가 정상이라면 신뢰 목록에 추가해 다시 알리지 않기.",
                action="trust_process",
                action_label="신뢰 (다시 알리지 않음)",
                action_args={"name": np["name"], "exe": np.get("exe", "")},
            ))
        if len(new_procs) > 8:
            recs.append(Recommendation(
                text=f"...외 {len(new_procs) - 8}개 새 프로세스 더 있음. "
                     "'리포트 저장'으로 전체 목록을 확인하세요.",
            ))

        if top_cpu:
            top = top_cpu[0]
            summary = (
                f"총 {len(procs)}개 · 최상위 {top['name']} "
                f"(코어당 {top['cpu_per_core']:.0f}%)"
            )
        else:
            summary = "사용자 프로세스를 찾지 못했습니다."
            severity = Severity.UNKNOWN

        return CheckResult(
            key=self.key,
            title=self.title,
            score=score,
            severity=severity,
            summary=summary,
            metrics={
                "total": len(procs),
                "zombies": zombies,
                "top_cpu": top_cpu,
                "top_memory": top_mem,
                "logical_cores": cpu_count,
            },
            recommendations=recs,
            icon=self.icon,
        )
