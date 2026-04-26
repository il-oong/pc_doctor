"""Background scanner: runs checks on a worker thread and pumps results into a queue."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Callable

from .checks import Check, CheckResult, all_checks
from .score import HealthSummary, aggregate


ScanType = str  # "quick" | "full"


@dataclass
class ScanProgress:
    completed: int
    total: int
    current: str


class Scanner:
    def __init__(self, checks: list[Check] | None = None) -> None:
        self.checks = checks if checks is not None else all_checks()
        self.weights = {c.key: c.weight for c in self.checks}
        self.events: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop_periodic = threading.Event()
        self._periodic_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    # ---------- public API ----------
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def quick_scan(self) -> bool:
        return self._spawn("quick")

    def full_scan(self) -> bool:
        return self._spawn("full")

    def start_periodic(self, interval_sec: int) -> None:
        self.stop_periodic()
        self._stop_periodic.clear()
        t = threading.Thread(
            target=self._periodic_loop, args=(interval_sec,), daemon=True
        )
        self._periodic_thread = t
        t.start()

    def stop_periodic(self) -> None:
        self._stop_periodic.set()
        self._periodic_thread = None

    def shutdown(self) -> None:
        self.stop_periodic()

    # ---------- internals ----------
    def _spawn(self, kind: ScanType) -> bool:
        with self._lock:
            if self.is_running():
                return False
            t = threading.Thread(target=self._run_scan, args=(kind,), daemon=True)
            self._thread = t
            t.start()
            return True

    def _run_scan(self, kind: ScanType) -> None:
        targets = [c for c in self.checks if (kind == "full" or c.quick)]
        total = len(targets)
        self.events.put(("scan_started", {"kind": kind, "total": total}))
        results: list[CheckResult] = []
        for i, check in enumerate(targets, start=1):
            self.events.put(("progress", ScanProgress(i - 1, total, check.title)))
            res = check.measure()
            results.append(res)
            self.events.put(("result", res))
        summary = aggregate(results, self.weights)
        self.events.put(("scan_done", summary))

    def _periodic_loop(self, interval_sec: int) -> None:
        while not self._stop_periodic.wait(interval_sec):
            self.full_scan()

    def drain(self, callback: Callable[[str, object], None]) -> int:
        """Drain pending events. Call from the UI thread (e.g. via root.after)."""
        n = 0
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            callback(kind, payload)
            n += 1
        return n


__all__ = ["Scanner", "ScanProgress", "HealthSummary"]
