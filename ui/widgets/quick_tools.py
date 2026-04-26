"""Quick Tools panel — always-visible maintenance buttons.

Hosts one-click shortcuts for cleanup tasks the user wants to run anytime,
not only when the diagnostic check raised them as recommendations.
"""
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
)


ActionCallback = Callable[[str, str | None, dict, str], None]


# (icon, label, action_key, action_args, confirm)
_TOOLS = [
    ("🗑", "임시 파일 정리",
     "clear_windows_temp", {"older_than_days": 1},
     "1일 이상 된 임시 파일을 모두 삭제합니다. 진행할까요?"),
    ("🌐", "브라우저 캐시 정리",
     "clear_browser_cache", {},
     "Chrome / Edge / Firefox 캐시를 비웁니다.\n"
     "(가능하면 브라우저를 먼저 종료해 주세요) 진행할까요?"),
    ("🗂", "휴지통 비우기",
     "empty_recycle_bin", {},
     "휴지통의 모든 항목을 영구 삭제합니다. 진행할까요?"),
    ("💾", "디스크 정리 도구",
     "open_disk_cleanup", {},
     None),
    ("📊", "사용하지 않는 앱 확인",
     "find_old_apps", {},
     None),
    ("🔧", "드라이브 최적화",
     "open_optimize_drives", {},
     None),
    ("🛡", "관리자 권한으로 재시작",
     "restart_as_admin", {},
     "PC Doctor를 관리자 권한으로 다시 시작합니다.\n"
     "(C:\\Windows\\Temp 같은 보호된 폴더 정리에 필요) 진행할까요?"),
    ("🎮", "GPU 드라이버 다운로드",
     "open_gpu_driver_page", {},
     None),
]


class QuickToolsPanel(tk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        on_action: ActionCallback | None = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, bg=BG_SURFACE,
                         highlightbackground=DIVIDER, highlightthickness=1,
                         **kwargs)
        self._on_action = on_action
        self._build()

    def _build(self) -> None:
        from core import actions
        self.configure(padx=16, pady=14)

        header = tk.Label(
            self, text="🧰  빠른 도구",
            font=(FONT_FAMILY, 13, "bold"),
            bg=BG_SURFACE, fg=TEXT_PRIMARY, anchor="w",
        )
        header.pack(fill="x", pady=(0, 4))

        sub = tk.Label(
            self, text="처방 없이도 바로 실행할 수 있는 정리 도구",
            font=(FONT_FAMILY, 11),
            bg=BG_SURFACE, fg=TEXT_SECONDARY, anchor="w",
        )
        sub.pack(fill="x", pady=(0, 10))

        grid = tk.Frame(self, bg=BG_SURFACE)
        grid.pack(fill="x")

        for idx, (icon, label, action_key, args, confirm) in enumerate(_TOOLS):
            if not actions.has(action_key):
                continue
            col = idx % 3
            row = idx // 3
            btn = ttk.Button(
                grid,
                text=f"{icon}  {label}",
                style="Ghost.TButton",
                command=lambda k=action_key, c=confirm, a=args, l=label:
                    self._dispatch(k, c, a, l),
            )
            btn.grid(row=row, column=col, padx=4, pady=4, sticky="ew")
            grid.columnconfigure(col, weight=1)

    def _dispatch(self, key: str, confirm: str | None, args: dict, label: str) -> None:
        if self._on_action:
            self._on_action(key, confirm, args, label)
