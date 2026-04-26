"""Main application window."""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox, ttk

from core import storage
from core.checks.base import Severity
from core.report import save_html
from core.scheduler import Scanner, ScanProgress
from core.score import HealthSummary
from ui import theme
from ui.views.dashboard import DashboardView
from ui.views.history import HistoryView
from ui.views.settings import SettingsView
from utils.format import time_only
from utils.notify import notify


class App(tk.Tk):
    _POLL_MS = 80  # event-queue poll interval

    def __init__(self) -> None:
        super().__init__()
        self.title("PC Doctor")
        self.geometry("1000x720")
        self.minsize(800, 580)

        theme.apply(self)
        self._scanner = Scanner()
        self._last_summary: HealthSummary | None = None
        self._scanning = False
        self._notify_enabled = True

        self._build()
        self._start_poll()
        self.after(200, self._quick_scan)

    # ── Build UI ─────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self._build_header()
        self._build_sidebar()
        self._build_main()
        self._build_footer()

    def _build_header(self) -> None:
        hdr = tk.Frame(self, bg="#FFFFFF",
                        highlightbackground=theme.DIVIDER, highlightthickness=1,
                        height=56)
        hdr.pack(side="top", fill="x")
        hdr.pack_propagate(False)

        logo = tk.Label(hdr, text="🩺  PC Doctor",
                         font=(theme.FONT_FAMILY, 16, "bold"),
                         bg="#FFFFFF", fg=theme.ACCENT_PRIMARY)
        logo.pack(side="left", padx=20)

        btn_frame = tk.Frame(hdr, bg="#FFFFFF")
        btn_frame.pack(side="right", padx=12)

        self._scan_btn = ttk.Button(btn_frame, text="⟳  검진 시작",
                                     style="Accent.TButton",
                                     command=self._full_scan)
        self._scan_btn.pack(side="left", padx=4)

        ttk.Button(btn_frame, text="리포트 저장",
                    style="Ghost.TButton",
                    command=self._save_report).pack(side="left", padx=4)

        self._progress = ttk.Progressbar(
            hdr, style="Scan.Horizontal.TProgressbar",
            orient="horizontal", length=180, mode="determinate",
        )
        self._progress.pack(side="right", padx=12)
        self._progress.pack_forget()

        self._host_lbl = tk.Label(hdr, text="",
                                   font=(theme.FONT_FAMILY, 11),
                                   bg="#FFFFFF", fg=theme.TEXT_MUTED)
        self._host_lbl.pack(side="left", padx=8)
        try:
            from utils.platform import hostname
            self._host_lbl.configure(text=hostname())
        except Exception:  # noqa: BLE001
            pass

    def _build_sidebar(self) -> None:
        self._sidebar = tk.Frame(self, bg="#FFFFFF", width=160,
                                  highlightbackground=theme.DIVIDER, highlightthickness=1)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        self._nav_btns: dict[str, tk.Label] = {}
        self._current_view = tk.StringVar(value="dashboard")

        nav_items = [
            ("dashboard", "🏠  대시보드"),
            ("history",   "📋  히스토리"),
            ("settings",  "⚙  설정"),
        ]
        for key, label in nav_items:
            lbl = tk.Label(self._sidebar, text=label,
                            font=(theme.FONT_FAMILY, 12),
                            bg="#FFFFFF", fg=theme.TEXT_PRIMARY,
                            anchor="w", padx=16, pady=10, cursor="hand2")
            lbl.pack(fill="x")
            lbl.bind("<Button-1>", lambda e, k=key: self._navigate(k))
            self._nav_btns[key] = lbl

        self._highlight_nav("dashboard")

    def _build_main(self) -> None:
        self._main = tk.Frame(self, bg=theme.BG_CANVAS)
        self._main.pack(side="left", fill="both", expand=True)

        self._dashboard = DashboardView(self._main)
        self._history = HistoryView(self._main)
        self._settings = SettingsView(self._main, on_apply=self._on_settings_apply)

        self._dashboard.pack(fill="both", expand=True)

    def _build_footer(self) -> None:
        self._footer = tk.Frame(self, bg="#FFFFFF", height=32,
                                 highlightbackground=theme.DIVIDER, highlightthickness=1)
        self._footer.pack(side="bottom", fill="x")
        self._footer.pack_propagate(False)

        self._footer_lbl = tk.Label(
            self._footer, text="대기 중",
            font=(theme.FONT_FAMILY, 11),
            bg="#FFFFFF", fg=theme.TEXT_MUTED,
        )
        self._footer_lbl.pack(side="left", padx=16)

        self._footer_right = tk.Label(
            self._footer, text="",
            font=(theme.FONT_FAMILY, 11),
            bg="#FFFFFF", fg=theme.TEXT_MUTED,
        )
        self._footer_right.pack(side="right", padx=16)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _navigate(self, view: str) -> None:
        for v in (self._dashboard, self._history, self._settings):
            v.pack_forget()

        if view == "dashboard":
            self._dashboard.pack(fill="both", expand=True)
        elif view == "history":
            self._history.pack(fill="both", expand=True)
            self._history.load()
        elif view == "settings":
            self._settings.pack(fill="both", expand=True)

        self._highlight_nav(view)
        self._current_view.set(view)

    def _highlight_nav(self, active: str) -> None:
        for key, lbl in self._nav_btns.items():
            if key == active:
                lbl.configure(bg=theme.ACCENT_SOFT, fg=theme.ACCENT_PRIMARY,
                               font=(theme.FONT_FAMILY, 12, "bold"))
            else:
                lbl.configure(bg="#FFFFFF", fg=theme.TEXT_PRIMARY,
                               font=(theme.FONT_FAMILY, 12))

    # ── Scanning ─────────────────────────────────────────────────────────────

    def _quick_scan(self) -> None:
        self._scanner.quick_scan()

    def _full_scan(self) -> None:
        self._scanner.full_scan()

    def _start_poll(self) -> None:
        self._scanner.drain(self._on_event)
        self.after(self._POLL_MS, self._start_poll)

    def _on_event(self, kind: str, payload: object) -> None:
        if kind == "scan_started":
            info = payload  # type: ignore[assignment]
            total = info.get("total", 0) if isinstance(info, dict) else 0
            self._scanning = True
            self._scan_btn.configure(state="disabled")
            self._progress["maximum"] = total
            self._progress["value"] = 0
            self._progress.pack(side="right", padx=12)
            self._dashboard.set_headline("검진 중…")
            self._footer_lbl.configure(text="검진 중…", fg=theme.ACCENT_PRIMARY)

        elif kind == "progress":
            prog: ScanProgress = payload  # type: ignore[assignment]
            self._progress["value"] = prog.completed
            self._footer_lbl.configure(
                text=f"검진 중: {prog.current}  ({prog.completed}/{prog.total})",
                fg=theme.ACCENT_PRIMARY,
            )

        elif kind == "result":
            self._dashboard.upsert_card(payload)  # type: ignore[arg-type]

        elif kind == "scan_done":
            summary: HealthSummary = payload  # type: ignore[assignment]
            self._last_summary = summary
            self._scanning = False
            self._scan_btn.configure(state="normal")
            self._progress.pack_forget()
            self._dashboard.update_summary(summary)
            self._footer_lbl.configure(
                text=f"마지막 검진 완료: {time_only(summary.finished_at)}",
                fg=theme.TEXT_MUTED,
            )
            self._footer_right.configure(
                text=f"점수 {summary.score} / 100  ·  소요 {summary.duration_ms}ms",
            )
            storage.save(summary, kind="full")
            storage.delete_old()
            if self._notify_enabled and summary.severity == Severity.CRITICAL:
                notify("PC Doctor", f"위험 항목 발견! 헬스 점수: {summary.score}/100")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _save_report(self) -> None:
        if not self._last_summary:
            messagebox.showinfo("PC Doctor", "먼저 검진을 실행해 주세요.")
            return
        path = save_html(self._last_summary)
        import subprocess, sys
        opener = {"win32": "start", "darwin": "open"}.get(sys.platform, "xdg-open")
        subprocess.Popen([opener, str(path)], shell=(sys.platform == "win32"))
        self._footer_lbl.configure(text=f"리포트 저장: {path}")

    def _on_settings_apply(self, interval_min: int, notify: bool) -> None:
        self._notify_enabled = notify
        interval_sec = interval_min * 60
        self._scanner.start_periodic(interval_sec)
        self._footer_lbl.configure(
            text=f"설정 적용: {interval_min}분 주기 자동 검진",
            fg=theme.TEXT_MUTED,
        )

    def on_close(self) -> None:
        self._scanner.shutdown()
        self.destroy()


def run() -> None:
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
