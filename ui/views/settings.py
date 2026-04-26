"""Settings view."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.theme import (
    BG_CANVAS,
    BG_SURFACE,
    FONT_FAMILY,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SettingsView(ttk.Frame):
    def __init__(self, parent: tk.Widget, on_apply=None, **kwargs: object) -> None:
        super().__init__(parent, style="TFrame", **kwargs)
        self._on_apply = on_apply
        self._interval_var = tk.IntVar(value=30)
        self._notify_var = tk.BooleanVar(value=True)
        self._build()

    def _build(self) -> None:
        title = tk.Label(
            self, text="설정",
            font=(FONT_FAMILY, 18, "bold"),
            bg=BG_CANVAS, fg=TEXT_PRIMARY,
        )
        title.pack(anchor="w", padx=20, pady=(16, 12))

        card = tk.Frame(self, bg=BG_SURFACE, padx=20, pady=16,
                         highlightbackground="#E3EAF1", highlightthickness=1)
        card.pack(fill="x", padx=16, pady=(0, 12))

        # Scan interval
        tk.Label(card, text="자동 검진 주기 (분)", font=(FONT_FAMILY, 12, "bold"),
                  bg=BG_SURFACE, fg=TEXT_PRIMARY).grid(row=0, column=0, sticky="w", pady=6)
        spin = ttk.Spinbox(card, from_=5, to=120, increment=5, textvariable=self._interval_var,
                            width=6, font=(FONT_FAMILY, 12))
        spin.grid(row=0, column=1, sticky="w", padx=(12, 0))

        # Notifications
        tk.Label(card, text="위험 항목 알림", font=(FONT_FAMILY, 12, "bold"),
                  bg=BG_SURFACE, fg=TEXT_PRIMARY).grid(row=1, column=0, sticky="w", pady=6)
        chk = ttk.Checkbutton(card, variable=self._notify_var)
        chk.grid(row=1, column=1, sticky="w", padx=(12, 0))

        btn = ttk.Button(card, text="적용", style="Accent.TButton",
                          command=self._apply)
        btn.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))

        tk.Label(
            self, text="변경 후 '적용'을 누르면 다음 주기부터 반영됩니다.",
            font=(FONT_FAMILY, 11), bg=BG_CANVAS, fg=TEXT_MUTED,
        ).pack(anchor="w", padx=20)

    def _apply(self) -> None:
        if self._on_apply:
            self._on_apply(
                interval_min=self._interval_var.get(),
                notify=self._notify_var.get(),
            )

    @property
    def interval_min(self) -> int:
        return self._interval_var.get()

    @property
    def notify_enabled(self) -> bool:
        return self._notify_var.get()
