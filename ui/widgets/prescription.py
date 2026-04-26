"""Prescription panel — medical chart style recommendation list with actions."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ui.theme import (
    BG_SURFACE,
    DIVIDER,
    FONT_FAMILY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    severity_color,
)


ActionCallback = Callable[[str, str | None, dict, str], None]
# (action_key, confirm_msg, action_args, action_label)


class PrescriptionPanel(tk.Frame):
    """Shows all active recommendations with one-click action buttons."""

    def __init__(
        self,
        parent: tk.Widget,
        on_action: ActionCallback | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(parent, bg=BG_SURFACE,
                         highlightbackground=DIVIDER, highlightthickness=1,
                         **kwargs)
        self._on_action = on_action
        self._build()

    def _build(self) -> None:
        self.configure(padx=16, pady=14)
        header = tk.Label(
            self, text="\U0001f48a  처방전  (Prescription)",
            font=(FONT_FAMILY, 13, "bold"),
            bg=BG_SURFACE, fg=TEXT_PRIMARY, anchor="w",
        )
        header.pack(fill="x", pady=(0, 10))

        self._list_frame = tk.Frame(self, bg=BG_SURFACE)
        self._list_frame.pack(fill="both", expand=True)

        self._render_empty()

    def _render_empty(self) -> None:
        tk.Label(
            self._list_frame,
            text="✅  이상 없음 — 모든 항목이 정상입니다.",
            font=(FONT_FAMILY, 12),
            bg=BG_SURFACE, fg="#2BB673", anchor="w",
        ).pack(fill="x")

    def update_results(self, results: list) -> None:
        for child in self._list_frame.winfo_children():
            child.destroy()

        items = [
            (r.title, rec, r.severity)
            for r in results
            for rec in r.recommendations
        ]
        if not items:
            self._render_empty()
            return

        for title, rec, severity in items:
            self._render_row(title, rec, severity)

    def _render_row(self, title: str, rec, severity) -> None:
        from core import actions  # local import to avoid cycle on init
        color = severity_color(severity.value)

        row = tk.Frame(self._list_frame, bg=BG_SURFACE)
        row.pack(fill="x", pady=4)

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
            inner, text=rec.text,
            font=(FONT_FAMILY, 11),
            bg=BG_SURFACE, fg=TEXT_SECONDARY, anchor="w",
            wraplength=560, justify="left",
        ).pack(fill="x")

        # Action button (only when an action is bound and registered)
        if rec.action and actions.has(rec.action) and self._on_action:
            btn_row = tk.Frame(inner, bg=BG_SURFACE)
            btn_row.pack(fill="x", pady=(4, 0))
            label = rec.action_label or "조치 실행"
            btn = ttk.Button(
                btn_row,
                text=f"▶  {label}",
                style="Ghost.TButton",
                command=lambda r=rec, lbl=label: self._on_action(
                    r.action, r.confirm, r.action_args, lbl,
                ),
            )
            btn.pack(side="left")
