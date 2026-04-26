"""VitalCard widget — one health check item displayed as a card tile."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.theme import (
    BG_SURFACE,
    DIVIDER,
    FONT_FAMILY,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    severity_color,
    score_color,
)


class VitalCard(ttk.Frame):
    """Displays a single CheckResult as a white card with status badge."""

    def __init__(self, parent: tk.Widget, on_click=None, **kwargs: object) -> None:
        super().__init__(parent, style="Surface.TFrame", **kwargs)
        self._on_click = on_click
        self._build()
        if on_click:
            self._bind_click(self)

    def _build(self) -> None:
        self.configure(padding=(16, 14))

        # Row 1: icon + title + badge
        top = ttk.Frame(self, style="Surface.TFrame")
        top.pack(fill="x")

        self._icon_lbl = tk.Label(top, text="", font=(FONT_FAMILY, 18),
                                   bg=BG_SURFACE, fg=TEXT_PRIMARY)
        self._icon_lbl.pack(side="left")

        self._title_lbl = tk.Label(top, text="", font=(FONT_FAMILY, 12, "bold"),
                                    bg=BG_SURFACE, fg=TEXT_PRIMARY)
        self._title_lbl.pack(side="left", padx=(6, 0))

        self._badge = tk.Label(top, text="", font=(FONT_FAMILY, 10, "bold"),
                                bg="#E6F0FB", fg="#2E7DD7",
                                padx=6, pady=1)
        self._badge.pack(side="right")

        # Row 2: score big
        self._score_lbl = tk.Label(self, text="—", font=(FONT_FAMILY, 26, "bold"),
                                    bg=BG_SURFACE, fg=TEXT_PRIMARY, anchor="w")
        self._score_lbl.pack(fill="x", pady=(8, 0))

        # Row 3: summary
        self._summary_lbl = tk.Label(self, text="", font=(FONT_FAMILY, 11),
                                      bg=BG_SURFACE, fg=TEXT_SECONDARY,
                                      anchor="w", wraplength=180, justify="left")
        self._summary_lbl.pack(fill="x", pady=(2, 0))

        # Bottom border line
        tk.Frame(self, bg=DIVIDER, height=1).pack(fill="x", side="bottom")

    def update_result(self, result) -> None:
        from core.checks.base import Severity
        color = severity_color(result.severity.value)
        sc_color = score_color(result.score)

        self._icon_lbl.configure(text=result.icon or "●")
        self._title_lbl.configure(text=result.title)
        self._score_lbl.configure(text=str(result.score), fg=sc_color)
        self._summary_lbl.configure(text=result.summary)

        badge_text = result.severity.label_ko
        self._badge.configure(
            text=badge_text,
            bg=_badge_bg(result.severity),
            fg=color,
        )

    def _bind_click(self, widget: tk.Widget) -> None:
        if self._on_click:
            widget.bind("<Button-1>", lambda e: self._on_click())
            for child in widget.winfo_children():
                self._bind_click(child)


def _badge_bg(severity) -> str:
    from core.checks.base import Severity
    return {
        Severity.HEALTHY: "#E8F8EF",
        Severity.WARNING: "#FEF3E2",
        Severity.CRITICAL: "#FEE9E9",
        Severity.UNKNOWN: "#EEF3F7",
    }.get(severity, "#EEF3F7")
