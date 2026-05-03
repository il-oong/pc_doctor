"""Maintenance view — installed apps, startup, hotfixes, large files."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

from ui.theme import (
    ACCENT_PRIMARY,
    BG_CANVAS,
    BG_SURFACE,
    DIVIDER,
    FONT_FAMILY,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


ActionCallback = Callable[[str, str | None, dict, str], None]


class _ScrollableList(tk.Frame):
    """Vertically scrolling Frame for variable-height rows."""

    def __init__(self, parent: tk.Widget, **kw) -> None:
        super().__init__(parent, bg=BG_CANVAS, **kw)
        self._canvas = tk.Canvas(self, bg=BG_CANVAS, highlightthickness=0)
        self._sb = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._sb.set)
        self._sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self.body = tk.Frame(self._canvas, bg=BG_CANVAS)
        self._win = self._canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(
            self._win, width=e.width))

    def clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()


class MaintenanceView(ttk.Frame):
    def __init__(self, parent: tk.Widget, on_action: ActionCallback | None = None,
                 **kw) -> None:
        super().__init__(parent, style="TFrame", **kw)
        self._on_action = on_action
        self._build()

    def _build(self) -> None:
        title = tk.Label(
            self, text="🧹  정리 / 관리",
            font=(FONT_FAMILY, 18, "bold"),
            bg=BG_CANVAS, fg=TEXT_PRIMARY,
        )
        title.pack(anchor="w", padx=20, pady=(16, 4))

        sub = tk.Label(
            self, text="설치된 앱 · 시작 프로그램 · Windows 업데이트 · 큰 파일을 한 곳에서 관리",
            font=(FONT_FAMILY, 11),
            bg=BG_CANVAS, fg=TEXT_MUTED,
        )
        sub.pack(anchor="w", padx=20, pady=(0, 12))

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Each tab gets its own scrollable list and lazy-loads on first show
        self._tab_apps = _ScrollableList(nb)
        self._tab_startup = _ScrollableList(nb)
        self._tab_updates = _ScrollableList(nb)
        self._tab_files = _ScrollableList(nb)

        nb.add(self._tab_apps, text="설치된 앱")
        nb.add(self._tab_startup, text="시작 프로그램")
        nb.add(self._tab_updates, text="Windows 업데이트")
        nb.add(self._tab_files, text="큰 파일")

        self._loaded = {"apps": False, "startup": False, "updates": False, "files": False}
        nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        # Trigger initial load for the default-selected tab
        self.after(150, self._load_apps)

    def _on_tab_changed(self, event: tk.Event) -> None:
        idx = event.widget.index("current")
        loader = (self._load_apps, self._load_startup,
                  self._load_updates, self._load_files)[idx]
        key = ("apps", "startup", "updates", "files")[idx]
        if not self._loaded[key]:
            loader()

    # ── Loaders ──────────────────────────────────────────────────────────────

    def _async(self, work, on_result) -> None:
        def runner():
            try:
                data = work()
            except Exception as exc:  # noqa: BLE001
                data = {"_error": str(exc)}
            self.after(0, lambda: on_result(data))
        threading.Thread(target=runner, daemon=True).start()

    def _show_loading(self, container: _ScrollableList, text: str = "불러오는 중…") -> None:
        container.clear()
        tk.Label(container.body, text=text,
                 font=(FONT_FAMILY, 12), bg=BG_CANVAS, fg=TEXT_MUTED,
                 anchor="w", padx=12, pady=12).pack(fill="x")

    def _load_apps(self) -> None:
        self._loaded["apps"] = True
        self._show_loading(self._tab_apps, "설치된 앱 목록을 읽는 중…")
        from core.inventory import list_installed_apps
        self._async(list_installed_apps, self._render_apps)

    def _load_startup(self) -> None:
        self._loaded["startup"] = True
        self._show_loading(self._tab_startup, "시작 프로그램을 읽는 중…")
        from core.inventory import list_startup_programs
        self._async(list_startup_programs, self._render_startup)

    def _load_updates(self) -> None:
        self._loaded["updates"] = True
        self._show_loading(self._tab_updates, "Windows 업데이트 목록을 읽는 중…")
        from core.inventory import list_hotfixes
        self._async(list_hotfixes, self._render_updates)

    def _load_files(self) -> None:
        self._loaded["files"] = True
        self._show_loading(self._tab_files, "큰 파일을 검색하는 중… (다운로드/문서/바탕화면/비디오)")
        from core.inventory import list_large_files
        self._async(lambda: list_large_files(min_bytes=100 * 1024 * 1024, limit=50),
                    self._render_files)

    def reload_files(self) -> None:
        """대용량 파일 탭 강제 새로고침."""
        self._loaded["files"] = False
        self._tab_files.clear()
        self._load_files()

    # ── Renderers ────────────────────────────────────────────────────────────

    def _render_apps(self, data) -> None:
        c = self._tab_apps
        c.clear()
        if isinstance(data, dict) and "_error" in data:
            self._render_error(c, data["_error"])
            return
        if not data:
            self._render_empty(c, "설치된 앱 정보를 가져오지 못했습니다. (Windows에서만 동작)")
            return

        # Toolbar
        bar = tk.Frame(c.body, bg=BG_CANVAS)
        bar.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(bar, text=f"총 {len(data)}개 (오래된 설치 순)",
                 font=(FONT_FAMILY, 11), bg=BG_CANVAS, fg=TEXT_SECONDARY).pack(side="left")
        ttk.Button(bar, text="새로고침", style="Ghost.TButton",
                   command=self._load_apps).pack(side="right")

        for app in data:
            self._app_row(c.body, app)

    def _app_row(self, parent: tk.Widget, app: dict) -> None:
        row = tk.Frame(parent, bg=BG_SURFACE,
                        highlightbackground=DIVIDER, highlightthickness=1)
        row.pack(fill="x", padx=8, pady=3)

        inner = tk.Frame(row, bg=BG_SURFACE, padx=12, pady=10)
        inner.pack(fill="x")

        meta = tk.Frame(inner, bg=BG_SURFACE)
        meta.pack(fill="x")

        tk.Label(meta, text=app["name"], font=(FONT_FAMILY, 12, "bold"),
                 bg=BG_SURFACE, fg=TEXT_PRIMARY, anchor="w").pack(side="left")

        if app.get("size_human"):
            tk.Label(meta, text=app["size_human"], font=(FONT_FAMILY, 11),
                     bg=BG_SURFACE, fg=TEXT_MUTED).pack(side="right", padx=(6, 0))

        tags = []
        if app.get("publisher"):
            tags.append(app["publisher"])
        if app.get("version"):
            tags.append(f"v{app['version']}")
        if app.get("install_date_iso"):
            age = app.get("age_days")
            tags.append(
                f"{app['install_date_iso']}"
                + (f" · {age}일 경과" if isinstance(age, int) else "")
            )
        if tags:
            tk.Label(inner, text="  ·  ".join(tags),
                     font=(FONT_FAMILY, 10), bg=BG_SURFACE, fg=TEXT_SECONDARY,
                     anchor="w").pack(fill="x", pady=(2, 0))

        if app.get("uninstall_string") and self._on_action:
            ttk.Button(inner, text="🗑  제거", style="Ghost.TButton",
                       command=lambda a=app: self._on_action(
                           "uninstall_app",
                           f"`{a['name']}` 제거를 시작합니다.\n"
                           "(앱의 자체 제거 마법사가 열립니다) 진행할까요?",
                           {
                               "name": a["name"],
                               "uninstall_string": a.get("uninstall_string", ""),
                               "quiet_uninstall_string": a.get("quiet_uninstall_string", ""),
                           },
                           f"{a['name']} 제거",
                       )).pack(anchor="e", pady=(6, 0))

    def _render_startup(self, data) -> None:
        c = self._tab_startup
        c.clear()
        if isinstance(data, dict) and "_error" in data:
            self._render_error(c, data["_error"])
            return
        if not data:
            self._render_empty(c, "등록된 시작 프로그램이 없거나 권한이 부족합니다.")
            return

        enabled_cnt  = sum(1 for i in data if i.get("is_enabled", True))
        disabled_cnt = len(data) - enabled_cnt

        bar = tk.Frame(c.body, bg=BG_CANVAS)
        bar.pack(fill="x", padx=8, pady=(0, 6))
        summary = f"총 {len(data)}개  (활성 {enabled_cnt} · 비활성 {disabled_cnt})"
        tk.Label(bar, text=summary,
                 font=(FONT_FAMILY, 11), bg=BG_CANVAS, fg=TEXT_SECONDARY).pack(side="left")
        ttk.Button(bar, text="새로고침", style="Ghost.TButton",
                   command=self._reload_startup).pack(side="right")

        for item in data:
            self._startup_row(c.body, item)

    def _reload_startup(self) -> None:
        self._loaded["startup"] = False
        self._load_startup()

    def _startup_row(self, parent: tk.Widget, item: dict) -> None:
        is_enabled = item.get("is_enabled", True)
        is_folder  = item.get("is_folder", False)

        row = tk.Frame(parent, bg=BG_SURFACE,
                        highlightbackground=DIVIDER, highlightthickness=1)
        row.pack(fill="x", padx=8, pady=3)
        inner = tk.Frame(row, bg=BG_SURFACE, padx=12, pady=10)
        inner.pack(fill="x")

        head = tk.Frame(inner, bg=BG_SURFACE)
        head.pack(fill="x")

        # Name + enabled/disabled badge
        name_frame = tk.Frame(head, bg=BG_SURFACE)
        name_frame.pack(side="left", fill="x", expand=True)
        tk.Label(name_frame, text=item["name"], font=(FONT_FAMILY, 12, "bold"),
                 bg=BG_SURFACE, fg=TEXT_PRIMARY, anchor="w").pack(side="left")

        if is_folder:
            badge_text, badge_color = "📁 폴더", "#6B7280"
        elif is_enabled:
            badge_text, badge_color = "✅ 활성", "#2BB673"
        else:
            badge_text, badge_color = "⛔ 비활성", "#E5484D"

        tk.Label(name_frame, text=f"  {badge_text}",
                 font=(FONT_FAMILY, 10), bg=BG_SURFACE, fg=badge_color).pack(side="left")

        tk.Label(head,
                 text=f"{item['scope']} · {item['location']}",
                 font=(FONT_FAMILY, 10),
                 bg=BG_SURFACE, fg=TEXT_MUTED).pack(side="right")

        tk.Label(inner, text=item.get("command", ""),
                 font=(FONT_FAMILY, 10), bg=BG_SURFACE, fg=TEXT_SECONDARY,
                 anchor="w", wraplength=720, justify="left").pack(fill="x", pady=(2, 0))

        if not self._on_action:
            return

        btns = tk.Frame(inner, bg=BG_SURFACE)
        btns.pack(anchor="e", pady=(6, 0))

        if is_folder:
            # Startup folder items: just offer to open the folder
            from pathlib import Path
            folder = str(Path(item.get("command", "")).parent)
            ttk.Button(btns, text="📂  폴더 열기", style="Ghost.TButton",
                       command=lambda f=folder: self._on_action(
                           "show_in_explorer", None, {"path": f}, "폴더 열기"
                       )).pack(side="left")
        elif is_enabled:
            ttk.Button(btns, text="⛔  비활성화", style="Ghost.TButton",
                       command=lambda i=item: self._on_action(
                           "disable_startup",
                           f"`{i['name']}` 시작 프로그램을 비활성화합니다.\n"
                           "(레지스트리에서 삭제하지 않고 비활성 플래그만 설정 — 언제든 재활성화 가능)\n"
                           "다음 부팅부터 적용됩니다. 진행할까요?",
                           {
                               "reg_path":      i.get("reg_path", ""),
                               "approved_path": i.get("approved_path", ""),
                               "name":          i.get("name", ""),
                           },
                           f"{i['name']} 비활성화",
                       )).pack(side="left")
        else:
            ttk.Button(btns, text="✅  활성화", style="Ghost.TButton",
                       command=lambda i=item: self._on_action(
                           "enable_startup",
                           f"`{i['name']}` 시작 프로그램을 다시 활성화합니다.\n"
                           "다음 부팅부터 자동 실행됩니다. 진행할까요?",
                           {
                               "approved_path": i.get("approved_path", ""),
                               "name":          i.get("name", ""),
                           },
                           f"{i['name']} 활성화",
                       )).pack(side="left")

    def _render_updates(self, data) -> None:
        c = self._tab_updates
        c.clear()
        if isinstance(data, dict) and "_error" in data:
            self._render_error(c, data["_error"])
            return
        if not data:
            self._render_empty(c, "Windows 업데이트 목록이 비어 있거나 가져오지 못했습니다.")
            return

        bar = tk.Frame(c.body, bg=BG_CANVAS)
        bar.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(bar, text=f"총 {len(data)}개 (최신순)",
                 font=(FONT_FAMILY, 11), bg=BG_CANVAS, fg=TEXT_SECONDARY).pack(side="left")
        ttk.Button(bar, text="새로고침", style="Ghost.TButton",
                   command=self._load_updates).pack(side="right")

        for kb in data:
            self._update_row(c.body, kb)

    def _update_row(self, parent: tk.Widget, kb: dict) -> None:
        row = tk.Frame(parent, bg=BG_SURFACE,
                        highlightbackground=DIVIDER, highlightthickness=1)
        row.pack(fill="x", padx=8, pady=3)
        inner = tk.Frame(row, bg=BG_SURFACE, padx=12, pady=10)
        inner.pack(fill="x")

        head = tk.Frame(inner, bg=BG_SURFACE)
        head.pack(fill="x")
        tk.Label(head, text=kb["id"], font=(FONT_FAMILY, 12, "bold"),
                 bg=BG_SURFACE, fg=TEXT_PRIMARY, anchor="w").pack(side="left")
        if kb.get("installed_on"):
            tk.Label(head, text=kb["installed_on"], font=(FONT_FAMILY, 11),
                     bg=BG_SURFACE, fg=TEXT_MUTED).pack(side="right")

        if kb.get("description"):
            tk.Label(inner, text=kb["description"],
                     font=(FONT_FAMILY, 10), bg=BG_SURFACE, fg=TEXT_SECONDARY,
                     anchor="w").pack(fill="x", pady=(2, 0))

        if self._on_action:
            ttk.Button(inner, text="🗑  제거 시도",
                       style="Ghost.TButton",
                       command=lambda k=kb: self._on_action(
                           "uninstall_hotfix",
                           f"{k['id']} Windows 업데이트 제거를 시도합니다.\n"
                           "(관리자 권한 필요 · 영구 적용된 일부 업데이트는 제거 불가)\n"
                           "진행할까요?",
                           {"kb": k["id"]},
                           f"{k['id']} 제거",
                       )).pack(anchor="e", pady=(6, 0))

    def _render_files(self, data) -> None:
        c = self._tab_files
        c.clear()
        if isinstance(data, dict) and "_error" in data:
            self._render_error(c, data["_error"])
            return
        if not data:
            self._render_empty(
                c,
                "100MB 이상의 큰 파일을 찾지 못했습니다. "
                "(검색 위치: 다운로드 / 바탕화면 / 문서 / 비디오)"
            )
            return

        bar = tk.Frame(c.body, bg=BG_CANVAS)
        bar.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(bar, text=f"상위 {len(data)}개 (큰 순)",
                 font=(FONT_FAMILY, 11), bg=BG_CANVAS, fg=TEXT_SECONDARY).pack(side="left")
        ttk.Button(bar, text="새로고침", style="Ghost.TButton",
                   command=self._load_files).pack(side="right")

        for f in data:
            self._file_row(c.body, f)

    def _file_row(self, parent: tk.Widget, f: dict) -> None:
        row = tk.Frame(parent, bg=BG_SURFACE,
                        highlightbackground=DIVIDER, highlightthickness=1)
        row.pack(fill="x", padx=8, pady=3)
        inner = tk.Frame(row, bg=BG_SURFACE, padx=12, pady=10)
        inner.pack(fill="x")

        head = tk.Frame(inner, bg=BG_SURFACE)
        head.pack(fill="x")
        from pathlib import Path
        name = Path(f["path"]).name
        tk.Label(head, text=name, font=(FONT_FAMILY, 12, "bold"),
                 bg=BG_SURFACE, fg=TEXT_PRIMARY, anchor="w").pack(side="left")
        tk.Label(head, text=f["size_human"], font=(FONT_FAMILY, 11),
                 bg=BG_SURFACE, fg=ACCENT_PRIMARY).pack(side="right")

        tk.Label(inner, text=f["path"], font=(FONT_FAMILY, 10),
                 bg=BG_SURFACE, fg=TEXT_SECONDARY,
                 anchor="w", wraplength=720, justify="left").pack(fill="x", pady=(2, 0))

        meta = tk.Label(inner, text=f"수정일: {f.get('modified', '?')}",
                        font=(FONT_FAMILY, 10),
                        bg=BG_SURFACE, fg=TEXT_MUTED)
        meta.pack(anchor="w", pady=(2, 0))

        if self._on_action:
            btns = tk.Frame(inner, bg=BG_SURFACE)
            btns.pack(anchor="e", pady=(6, 0))
            ttk.Button(btns, text="📂 폴더 열기", style="Ghost.TButton",
                       command=lambda p=f["path"]: self._on_action(
                           "show_in_explorer", None, {"path": p}, "폴더 열기"
                       )).pack(side="left", padx=(0, 4))
            ttk.Button(btns, text="🗑 휴지통으로", style="Ghost.TButton",
                       command=lambda p=f["path"], n=name: self._on_action(
                           "delete_file",
                           f"`{n}` 파일을 휴지통으로 보냅니다. 진행할까요?",
                           {"path": p}, f"{n} 삭제",
                       )).pack(side="left")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _render_empty(self, container: _ScrollableList, text: str) -> None:
        tk.Label(container.body, text=text,
                 font=(FONT_FAMILY, 12), bg=BG_CANVAS, fg=TEXT_MUTED,
                 anchor="w", padx=12, pady=20).pack(fill="x")

    def _render_error(self, container: _ScrollableList, msg: str) -> None:
        tk.Label(container.body, text=f"오류: {msg}",
                 font=(FONT_FAMILY, 12), bg=BG_CANVAS, fg="#E5484D",
                 anchor="w", padx=12, pady=20).pack(fill="x")
