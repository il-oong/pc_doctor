"""Network connectivity check."""
from __future__ import annotations

import socket
import time

import psutil

from .base import Check, CheckResult, Severity, linear_score, severity_from_score


PROBE_HOSTS = [("1.1.1.1", 53), ("8.8.8.8", 53)]
DNS_PROBE = "example.com"


class NetworkCheck(Check):
    key = "network"
    title = "네트워크"
    weight = 0.10
    quick = False
    icon = "🌐"

    def run(self) -> CheckResult:
        rtts: list[float] = []
        reachable = False
        for host, port in PROBE_HOSTS:
            start = time.perf_counter()
            try:
                with socket.create_connection((host, port), timeout=1.5):
                    rtts.append((time.perf_counter() - start) * 1000)
                    reachable = True
            except OSError:
                continue

        dns_ms: float | None = None
        try:
            t = time.perf_counter()
            socket.gethostbyname(DNS_PROBE)
            dns_ms = (time.perf_counter() - t) * 1000
        except OSError:
            dns_ms = None

        if_stats = {}
        try:
            for name, stats in psutil.net_if_stats().items():
                if_stats[name] = {
                    "isup": stats.isup,
                    "speed": stats.speed,
                }
        except (AttributeError, OSError):
            pass

        if not reachable:
            return CheckResult(
                key=self.key,
                title=self.title,
                score=20,
                severity=Severity.CRITICAL,
                summary="인터넷에 연결할 수 없습니다.",
                metrics={"reachable": False, "interfaces": if_stats},
                recommendations=[
                    "네트워크 케이블 또는 Wi-Fi 연결을 확인해 주세요.",
                    "라우터 재시작 후 다시 시도해 주세요.",
                ],
                icon=self.icon,
            )

        avg_rtt = sum(rtts) / len(rtts) if rtts else 0.0
        rtt_score = linear_score(avg_rtt, healthy_at=40.0, critical_at=400.0)
        dns_score = 100 if dns_ms is None else linear_score(dns_ms, healthy_at=80.0, critical_at=600.0)
        score = int(round(rtt_score * 0.7 + dns_score * 0.3))
        severity = severity_from_score(score)

        recs: list[str] = []
        if avg_rtt >= 200:
            recs.append("응답 지연이 큽니다. 무선 신호 또는 회선 상태를 확인해 주세요.")
        if dns_ms is not None and dns_ms >= 400:
            recs.append("DNS 응답이 느립니다. DNS 서버를 변경해 보세요.")

        return CheckResult(
            key=self.key,
            title=self.title,
            score=score,
            severity=severity,
            summary=f"평균 {avg_rtt:.0f} ms · DNS {('-' if dns_ms is None else f'{dns_ms:.0f} ms')}",
            metrics={
                "reachable": True,
                "avg_rtt_ms": avg_rtt,
                "dns_ms": dns_ms,
                "interfaces": if_stats,
            },
            recommendations=recs,
            icon=self.icon,
        )
