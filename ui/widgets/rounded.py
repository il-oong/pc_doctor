"""Canvas-based rounded-rectangle card helper (Tkinter doesn't support border-radius natively)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.theme import BG_SURFACE, DIVIDER


class RoundedFrame(tk.Canvas):
    """A Canvas that draws itself as a rounded-corner card."""

    def __init__(
        self,
        parent: tk.Widget,
        radius: int = 12,
        bg: str = BG_SURFACE,
        border: str = DIVIDER,
        **kwargs: object,
    ) -> None:
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("relief", "flat")
        super().__init__(parent, bg=bg, **kwargs)
        self._radius = radius
        self._bg = bg
        self._border = border
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event: tk.Event) -> None:
        self._redraw(event.width, event.height)

    def _redraw(self, w: int, h: int) -> None:
        self.delete("bg_rect")
        r = self._radius
        self.create_polygon(
            r, 0,
            w - r, 0,
            w, 0, w, r,
            w, h - r,
            w, h, w - r, h,
            r, h,
            0, h, 0, h - r,
            0, r,
            0, 0, r, 0,
            smooth=True,
            fill=self._bg,
            outline=self._border,
            tags="bg_rect",
        )
        self.tag_lower("bg_rect")

    def create_window_centered(self, widget: tk.Widget) -> None:
        self.create_window(
            int(self.winfo_reqwidth() / 2),
            int(self.winfo_reqheight() / 2),
            window=widget,
        )
