"""Prescription panel — medical chart style recommendation list."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.theme import (
    BG_SURFACE,
    FONT_FAMILY,
    STATE_CRITICAL,
    STATE_WARNING,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    severity_color,
)


class PrescriptionPanel(tk.Frame):
    """Shows all active recommendations in a prescription-chart style."""

    def __init__(self, parent: tk.Widget, **kwargs: object) -> None:
        super().__init__(parent, bg=BG_SURFACE, **kwargs)
        self._build()

    def _build(self) -> None:
        self.configure(padding=(16, 14))
        header = tk.Label(
            self, text="💊  처방전  (Prescription)",
            font=(FONT_FAMILY, 13, "bold"),
            bg=BG_SURFACE, fg=TEXT_PRIMARY, anchor="w",
        )
        header.pack(fill="x", pady=(0, 10))

        self._list_frame = tk.Frame(self, bg=BG_SURFACE)
        self._list_frame.pack(fill="both", expand=True)

        self._empty = tk.Label(
            self._list_frame,
            text="✅  이상 없음 — 모든 항목이 정상입니다.",
            font=(FONT_FAMILY, 12),
            bg=BG_SURFACE, fg="#2BB673", anchor="w",
        )
        self._empty.pack(fill="x")

    def update_results(self, results: list) -> None:
        for child in self._list_frame.winfo_children():
            child.destroy()

        items = [
            (r.title, rec, r.severity)
            for r in results
            for rec in r.recommendations
        ]
        if not items:
            lbl = tk.Label(
                self._list_frame,
                text="✅  이상 없음 — 모든 항목이 정상입니다.",
                font=(FONT_FAMILY, 12),
                bg=BG_SURFACE, fg="#2BB673", anchor="w",
            )
            lbl.pack(fill="x", pady=2)
            return

        for title, rec, severity in items:
            row = tk.Frame(self._list_frame, bg=BG_SURFACE)
            row.pack(fill="x", pady=3)

            color = severity_color(severity.value)

            # Left colored bar
            tk.Frame(row, bg=color, width=3).pack(side="left", fill="y", padx=(0, 10))

            inner = tk.Frame(row, bg=BG_SURFACE)
            inner.pack(side="left", fill="both", expand=True)

            tk.Label(
                inner, text=title,
                font=(FONT_FAMILY, 11, "bold"),
                bg=BG_SURFACE, fg=color, anchor="w",
            ).pack(fill="x")
            tk.Label(
                inner, text=rec,
                font=(FONT_FAMILY, 11),
                bg=BG_SURFACE, fg=TEXT_SECONDARY, anchor="w",
                wraplength=500, justify="left",
            ).pack(fill="x")
