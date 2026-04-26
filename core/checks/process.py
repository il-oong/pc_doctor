"""Top resource-consuming processes."""
from __future__ import annotations

import psutil

from .base import Check, CheckResult, Recommendation, Severity, linear_score, severity_from_score


class ProcessCheck(Check):
    key = "process"
    title = "프로세스"
    weight = 0.05
    quick = False
    icon = "⚙"

    def run(self) -> CheckResult:
        procs = []
        zombies = 0
        # Prime cpu_percent so it doesn't return 0 for everyone
        for p in psutil.process_iter(["pid", "name", "status"]):
            try:
                p.cpu_percent(None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Brief settle to get meaningful CPU reading
        psutil.cpu_percent(interval=0.3)

        for p in psutil.process_iter(["pid", "name", "username", "status"]):
            try:
                cpu = p.cpu_percent(None)
                mem = p.memory_percent()
                status = p.info.get("status")
                if status == psutil.STATUS_ZOMBIE:
                    zombies += 1
                procs.append({
                    "pid": p.info["pid"],
                    "name": p.info.get("name") or "?",
                    "user": p.info.get("username") or "",
                    "cpu": cpu,
                    "memory": mem,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        top_cpu = sorted(procs, key=lambda x: x["cpu"], reverse=True)[:5]
        top_mem = sorted(procs, key=lambda x: x["memory"], reverse=True)[:5]

        # Score based on the heaviest single process (CPU + memory)
        heaviest_cpu = top_cpu[0]["cpu"] if top_cpu else 0
        heaviest_mem = top_mem[0]["memory"] if top_mem else 0
        cpu_score = linear_score(heaviest_cpu, healthy_at=40.0, critical_at=200.0)
        mem_score = linear_score(heaviest_mem, healthy_at=20.0, critical_at=70.0)
        score = int(round((cpu_score + mem_score) / 2))
        if zombies > 5:
            score = min(score, 60)
        severity = severity_from_score(score)

        recs: list[Recommendation] = []
        if heaviest_cpu >= 100:
            recs.append(Recommendation(
                text=f"`{top_cpu[0]['name']}` 프로세스가 CPU를 많이 사용합니다.",
                action="open_task_manager",
                action_label="작업 관리자 열기",
            ))
        if heaviest_mem >= 30:
            recs.append(Recommendation(
                text=f"`{top_mem[0]['name']}` 프로세스가 메모리를 많이 사용합니다.",
                action="open_task_manager",
                action_label="작업 관리자 열기",
            ))
        if zombies > 5:
            recs.append(Recommendation(
                text=f"좀비 프로세스가 {zombies}개 있습니다. 시스템 재시작을 고려해 주세요.",
                action="restart_pc",
                action_label="지금 재시작",
                confirm="60초 후 PC를 재시작합니다. 진행할까요?",
                action_args={"delay_sec": 60},
            ))

        if top_cpu:
            summary = f"총 {len(procs)}개 · 최상위 {top_cpu[0]['name']} ({top_cpu[0]['cpu']:.0f}% CPU)"
        else:
            summary = f"총 {len(procs)}개 프로세스"
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
            },
            recommendations=recs,
            icon=self.icon,
        )
