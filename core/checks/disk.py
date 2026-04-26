"""Disk usage check across all mounted partitions."""
from __future__ import annotations

import psutil

from utils.format import bytes_human

from .base import Check, CheckResult, Recommendation, linear_score, severity_from_score


class DiskCheck(Check):
    key = "disk"
    title = "저장소"
    weight = 0.20
    quick = True
    icon = "💾"

    def run(self) -> CheckResult:
        partitions = []
        worst_percent = 0.0
        worst_mount = None
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue
            partitions.append({
                "device": part.device,
                "mount": part.mountpoint,
                "fstype": part.fstype,
                "percent": usage.percent,
                "used": usage.used,
                "total": usage.total,
                "free": usage.free,
            })
            if usage.percent > worst_percent:
                worst_percent = usage.percent
                worst_mount = part.mountpoint

        score = linear_score(worst_percent, healthy_at=70.0, critical_at=95.0) if partitions else 100
        severity = severity_from_score(score)

        recs: list[Recommendation] = []
        if worst_percent >= 95:
            recs.append(Recommendation(
                text=f"{worst_mount} 가 거의 가득 찼습니다. 즉시 공간을 확보하세요.",
                action="open_disk_cleanup",
                action_label="디스크 정리 실행",
            ))
            recs.append(Recommendation(
                text="임시 파일을 자동으로 정리합니다 (7일 이상 된 항목).",
                action="clear_temp_files",
                action_label="임시 파일 정리",
                confirm="임시 폴더에서 7일 이상 된 파일을 모두 삭제합니다. 진행할까요?",
                action_args={"older_than_days": 7},
            ))
            recs.append(Recommendation(
                text="휴지통을 비웁니다.",
                action="empty_recycle_bin",
                action_label="휴지통 비우기",
                confirm="휴지통의 모든 항목을 영구 삭제합니다. 진행할까요?",
            ))
        elif worst_percent >= 85:
            recs.append(Recommendation(
                text=f"{worst_mount} 여유 공간이 부족합니다. 임시파일/캐시 정리를 권장합니다.",
                action="open_disk_cleanup",
                action_label="디스크 정리 실행",
            ))
            recs.append(Recommendation(
                text="임시 파일을 자동으로 정리합니다 (7일 이상 된 항목).",
                action="clear_temp_files",
                action_label="임시 파일 정리",
                confirm="임시 폴더에서 7일 이상 된 파일을 모두 삭제합니다. 진행할까요?",
                action_args={"older_than_days": 7},
            ))

        if partitions:
            summary = f"최대 {worst_percent:.0f}% · {worst_mount or '?'} · {len(partitions)}개 파티션"
        else:
            summary = "마운트된 파티션을 찾지 못했습니다."

        return CheckResult(
            key=self.key,
            title=self.title,
            score=score,
            severity=severity,
            summary=summary,
            metrics={
                "partitions": partitions,
                "worst_percent": worst_percent,
                "worst_mount": worst_mount,
                "worst_total_human": bytes_human(
                    next((p["total"] for p in partitions if p["mount"] == worst_mount), 0)
                ),
            },
            recommendations=recs,
            icon=self.icon,
        )
