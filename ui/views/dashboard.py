"""Main dashboard view."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from core.checks.base import CheckResult, Severity
from core.score import HealthSummary
from ui.theme import (
    ACCENT_PRIMARY,
    BG_CANVAS,
    BG_SURFACE,
    DIVIDER,
    FONT_FAMILY,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    score_color,
    severity_color,
)
from ui.widgets.prescription import PrescriptionPanel
from ui.widgets.score_gauge import ScoreGauge
from ui.widgets.vital_card import VitalCard


class DashboardView(ttk.Frame):
    """Scrollable dashboard: gauge → vital cards grid → prescription."""

    def __init__(self, parent: tk.Widget, **kwargs: object) -> None:
        super().__init__(parent, style="TFrame", **kwargs)
        self._cards: dict[str, VitalCard] = {}
        self._build()

    def _build(self) -> None:
        # Scrollable canvas
        self._canvas = tk.Canvas(self, bg=BG_CANVAS, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=BG_CANVAS)
        self._window_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind_all("<Button-4>", self._on_mousewheel)
        self._canvas.bind_all("<Button-5>", self._on_mousewheel)

        self._build_inner()

    def _build_inner(self) -> None:
        p = self._inner

        # ── Score header card ────────────────────────────────────────────
        header = tk.Frame(p, bg=BG_SURFACE, bd=0)
        header.pack(fill="x", padx=16, pady=(16, 8))
        _card_border(header)

        gauge_frame = tk.Frame(header, bg=BG_SURFACE)
        gauge_frame.pack(side="left", padx=16, pady=16)

        self._gauge = ScoreGauge(gauge_frame, bg=BG_SURFACE)
        self._gauge.pack()

        info = tk.Frame(header, bg=BG_SURFACE)
        info.pack(side="left", fill="both", expand=True, padx=(0, 16), pady=16)

        self._headline_lbl = tk.Label(
            info, text="검진 준비 중…",
            font=(FONT_FAMILY, 16, "bold"),
            bg=BG_SURFACE, fg=TEXT_PRIMARY, anchor="w",
        )
        self._headline_lbl.pack(fill="x")

        self._status_lbl = tk.Label(
            info, text="",
            font=(FONT_FAMILY, 12),
            bg=BG_SURFACE, fg=TEXT_SECONDARY, anchor="w",
        )
        self._status_lbl.pack(fill="x", pady=(4, 0))

        self._last_lbl = tk.Label(
            info, text="",
            font=(FONT_FAMILY, 11),
            bg=BG_SURFACE, fg=TEXT_MUTED, anchor="w",
        )
        self._last_lbl.pack(fill="x", pady=(2, 0))

        # ── Vital cards grid ─────────────────────────────────────────────
        section_lbl = tk.Label(
            p, text="바이탈 사인",
            font=(FONT_FAMILY, 13, "bold"),
            bg=BG_CANVAS, fg=TEXT_SECONDARY, anchor="w",
        )
        section_lbl.pack(fill="x", padx=20, pady=(8, 4))

        self._grid = tk.Frame(p, bg=BG_CANVAS, padx=4, pady=4)
        self._grid.pack(fill="x", padx=16, pady=(0, 8))

        # ── Prescription ─────────────────────────────────────────────────
        section_lbl2 = tk.Label(
            p, text="처방전",
            font=(FONT_FAMILY, 13, "bold"),
            bg=BG_CANVAS, fg=TEXT_SECONDARY, anchor="w",
        )
        section_lbl2.pack(fill="x", padx=20, pady=(8, 4))

        self._prescription = PrescriptionPanel(p)
        self._prescription.pack(fill="x", padx=16, pady=(0, 16))
        _card_border(self._prescription)

    # ── Public update methods ────────────────────────────────────────────────

    def update_summary(self, summary: HealthSummary) -> None:
        from utils.format import time_only
        self._gauge.set_score(summary.score)
        self._headline_lbl.configure(text=summary.headline)
        self._status_lbl.configure(
            text=f"{'정상' if summary.severity == Severity.HEALTHY else summary.severity.label_ko} · 점수 {summary.score} / 100",
            fg=severity_color(summary.severity.value),
        )
        self._last_lbl.configure(text=f"마지막 검진: {time_only(summary.finished_at)}")
        self._prescription.update_results(summary.results)

    def upsert_card(self, result: CheckResult) -> None:
        if result.key not in self._cards:
            card = VitalCard(self._grid)
            col = len(self._cards) % 3
            row = len(self._cards) // 3
            card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            self._grid.columnconfigure(col, weight=1)
            self._cards[result.key] = card
        self._cards[result.key].update_result(result)

    def set_headline(self, text: str) -> None:
        self._headline_lbl.configure(text=text)

    # ── Scroll helpers ───────────────────────────────────────────────────────

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event: tk.Event) -> None:
        self._canvas.itemconfig(self._window_id, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            self._canvas.yview_scroll(int(-event.delta / 120), "units")


def _card_border(widget: tk.Widget) -> None:
    widget.configure(highlightbackground=DIVIDER, highlightthickness=1)
