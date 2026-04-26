"""Semi-circular health score gauge drawn on a Canvas."""
from __future__ import annotations

import math
import tkinter as tk

from ui.theme import (
    BG_SUBTLE,
    FONT_FAMILY,
    STATE_CRITICAL,
    STATE_HEALTHY,
    STATE_WARNING,
    score_color,
)


class ScoreGauge(tk.Canvas):
    """Arc gauge: 0-100 health score displayed as a semi-circle."""

    _WIDTH = 220
    _HEIGHT = 130
    _R = 85
    _CX = _WIDTH // 2
    _CY = _HEIGHT - 20

    def __init__(self, parent: tk.Widget, bg: str = "#FFFFFF", **kwargs: object) -> None:
        super().__init__(
            parent,
            width=self._WIDTH,
            height=self._HEIGHT,
            bg=bg,
            highlightthickness=0,
            relief="flat",
            **kwargs,
        )
        self._score = 0
        self._draw(0)

    def set_score(self, score: int) -> None:
        if score == self._score:
            return
        self._score = score
        self._draw(score)

    def _draw(self, score: int) -> None:
        self.delete("all")
        cx, cy, r = self._CX, self._CY, self._R

        # Track (grey arc)
        self._arc(cx, cy, r, 180, 180, BG_SUBTLE, width=16)

        # Value arc
        span = int(score / 100 * 180)
        color = score_color(score)
        if span > 0:
            self._arc(cx, cy, r, 180, span, color, width=16)

        # Needle
        angle_deg = 180 - span
        angle_rad = math.radians(angle_deg)
        nx = cx + (r - 8) * math.cos(angle_rad)
        ny = cy - (r - 8) * math.sin(angle_rad)
        self.create_oval(nx - 5, ny - 5, nx + 5, ny + 5, fill=color, outline="")
        self.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill=color, outline="")

        # Score text
        self.create_text(
            cx, cy - 16,
            text=str(score),
            font=(FONT_FAMILY, 36, "bold"),
            fill=color,
        )
        self.create_text(
            cx, cy + 6,
            text="/ 100",
            font=(FONT_FAMILY, 11),
            fill="#8FA0B0",
        )

    def _arc(
        self, cx: int, cy: int, r: int, start: int, extent: int, color: str, width: int
    ) -> None:
        x0, y0 = cx - r, cy - r
        x1, y1 = cx + r, cy + r
        self.create_arc(
            x0, y0, x1, y1,
            start=start, extent=-extent,
            style=tk.ARC,
            outline=color,
            width=width,
        )
