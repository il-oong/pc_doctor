"""History view — past scan results."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.theme import (
    BG_CANVAS,
    BG_SURFACE,
    DIVIDER,
    FONT_FAMILY,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    score_color,
)
from utils.format import timestamp


class HistoryView(ttk.Frame):
    def __init__(self, parent: tk.Widget, **kwargs: object) -> None:
        super().__init__(parent, style="TFrame", **kwargs)
        self._build()

    def _build(self) -> None:
        title = tk.Label(
            self, text="검진 히스토리",
            font=(FONT_FAMILY, 18, "bold"),
            bg=BG_CANVAS, fg=TEXT_PRIMARY,
        )
        title.pack(anchor="w", padx=20, pady=(16, 8))

        cols = ("ts", "score", "severity", "kind")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=20)
        self._tree.heading("ts", text="검진 시각")
        self._tree.heading("score", text="점수")
        self._tree.heading("severity", text="상태")
        self._tree.heading("kind", text="종류")
        self._tree.column("ts", width=200)
        self._tree.column("score", width=80, anchor="center")
        self._tree.column("severity", width=100, anchor="center")
        self._tree.column("kind", width=80, anchor="center")
        self._tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        sb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)

    def load(self) -> None:
        from core import storage
        rows = storage.load_recent(50)
        for item in self._tree.get_children():
            self._tree.delete(item)
        for row in rows:
            sc = row.get("score", 0)
            ts = timestamp(row.get("ts", 0))
            self._tree.insert("", "end", values=(
                ts,
                sc,
                row.get("severity", "—"),
                row.get("kind", "full"),
            ))
