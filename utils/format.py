"""Human-readable formatting helpers."""
from __future__ import annotations

from datetime import datetime, timedelta


def bytes_human(num: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    n = float(num)
    for unit in units:
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024.0
    return f"{n:.1f} EB"


def percent(value: float, decimals: int = 0) -> str:
    return f"{value:.{decimals}f}%"


def duration(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    td = timedelta(seconds=int(seconds))
    days, rem = divmod(int(td.total_seconds()), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}일 {hours}시간"
    if hours:
        return f"{hours}시간 {minutes}분"
    return f"{minutes}분"


def timestamp(ts: float | None = None) -> str:
    dt = datetime.fromtimestamp(ts) if ts is not None else datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def time_only(ts: float | None = None) -> str:
    dt = datetime.fromtimestamp(ts) if ts is not None else datetime.now()
    return dt.strftime("%H:%M:%S")
