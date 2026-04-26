"""Settings view."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

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
        self._autostart_var = tk.BooleanVar(value=False)
        self._build()
        self._refresh_autostart_state()

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

        # ── Autostart card ───────────────────────────────────────────────
        card2 = tk.Frame(self, bg=BG_SURFACE, padx=20, pady=16,
                          highlightbackground="#E3EAF1", highlightthickness=1)
        card2.pack(fill="x", padx=16, pady=(12, 12))

        tk.Label(card2, text="Windows 시작 시 자동 실행",
                  font=(FONT_FAMILY, 12, "bold"),
                  bg=BG_SURFACE, fg=TEXT_PRIMARY).grid(row=0, column=0, sticky="w", pady=6)
        self._autostart_chk = ttk.Checkbutton(
            card2, variable=self._autostart_var, command=self._toggle_autostart,
        )
        self._autostart_chk.grid(row=0, column=1, sticky="w", padx=(12, 0))

        tk.Label(
            card2,
            text=(
                "켜면 PC가 부팅되어 로그인할 때 PC Doctor가 자동으로 실행되고\n"
                "Quick Scan을 한 번 돌립니다. (HKCU\\Run 레지스트리)"
            ),
            font=(FONT_FAMILY, 11), bg=BG_SURFACE, fg=TEXT_SECONDARY,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # ── Reset baseline ───────────────────────────────────────────────
        card3 = tk.Frame(self, bg=BG_SURFACE, padx=20, pady=16,
                          highlightbackground="#E3EAF1", highlightthickness=1)
        card3.pack(fill="x", padx=16, pady=(0, 12))

        tk.Label(card3, text="프로세스 신뢰 목록 초기화",
                  font=(FONT_FAMILY, 12, "bold"),
                  bg=BG_SURFACE, fg=TEXT_PRIMARY).grid(row=0, column=0, sticky="w", pady=6)
        ttk.Button(card3, text="초기화", style="Ghost.TButton",
                    command=self._reset_baseline).grid(row=0, column=1, sticky="w", padx=(12, 0))
        tk.Label(
            card3,
            text=(
                "초기화하면 다음 검진은 처음 실행으로 처리되며 모든 현재 프로세스가\n"
                "신뢰 목록에 새로 기록됩니다."
            ),
            font=(FONT_FAMILY, 11), bg=BG_SURFACE, fg=TEXT_SECONDARY,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

    def _refresh_autostart_state(self) -> None:
        try:
            from core.actions import autostart_enabled
            self._autostart_var.set(autostart_enabled())
        except Exception:  # noqa: BLE001
            self._autostart_var.set(False)

    def _toggle_autostart(self) -> None:
        from core import actions
        want = self._autostart_var.get()
        action = "enable_autostart" if want else "disable_autostart"
        result = actions.run(action, {})
        if result.ok:
            messagebox.showinfo("PC Doctor — 자동 실행", result.message)
        else:
            messagebox.showerror("PC Doctor — 자동 실행", result.message)
            # Revert toggle to actual state on failure
            self._refresh_autostart_state()

    def _reset_baseline(self) -> None:
        from core import actions
        ok = messagebox.askyesno(
            "PC Doctor",
            "프로세스 신뢰 목록을 초기화합니다.\n"
            "다음 검진은 처음 실행으로 처리되며, 현재 실행 중인 모든 프로세스가\n"
            "신뢰 목록에 다시 기록됩니다. 진행할까요?",
        )
        if not ok:
            return
        result = actions.run("reset_process_baseline", {})
        if result.ok:
            messagebox.showinfo("PC Doctor", result.message)
        else:
            messagebox.showerror("PC Doctor", result.message)

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
