"""One-click remediation actions invoked from the prescription panel.

Each action is a callable that performs a fix and returns an `ActionResult`
describing what happened. Actions are intentionally cross-platform: when a
particular fix has no equivalent on the current OS, the handler returns a
`status="skipped"` result with an explanation rather than raising.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from utils.platform import IS_LINUX, IS_MACOS, IS_WINDOWS


@dataclass
class ActionResult:
    status: str        # "ok" | "skipped" | "error"
    message: str

    @property
    def ok(self) -> bool:
        return self.status == "ok"


ActionFn = Callable[[dict[str, Any]], ActionResult]
_REGISTRY: dict[str, ActionFn] = {}


def register(key: str) -> Callable[[ActionFn], ActionFn]:
    def deco(fn: ActionFn) -> ActionFn:
        _REGISTRY[key] = fn
        return fn
    return deco


def run(key: str, args: dict[str, Any] | None = None) -> ActionResult:
    fn = _REGISTRY.get(key)
    if fn is None:
        return ActionResult("error", f"알 수 없는 조치: {key}")
    try:
        return fn(args or {})
    except Exception as exc:  # noqa: BLE001
        return ActionResult("error", f"조치 실행 중 오류: {exc}")


def has(key: str) -> bool:
    return key in _REGISTRY


# ── Helpers ──────────────────────────────────────────────────────────────────

def _spawn(cmd: list[str] | str, *, shell: bool = False) -> ActionResult:
    """Spawn a process detached so the UI doesn't block on it."""
    try:
        kwargs: dict[str, Any] = {"close_fds": True}
        if IS_WINDOWS:
            kwargs["creationflags"] = 0x00000008  # DETACHED_PROCESS
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(cmd, shell=shell, **kwargs)
        return ActionResult("ok", "실행했습니다.")
    except FileNotFoundError as exc:
        return ActionResult("error", f"명령을 찾을 수 없습니다: {exc.filename or cmd}")
    except OSError as exc:
        return ActionResult("error", f"실행 실패: {exc}")


_NO_WINDOW = {"creationflags": 0x08000000} if IS_WINDOWS else {}


def _run_and_capture(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=False,
        **_NO_WINDOW,
    )
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    return proc.returncode, out, err


def _open_url(url: str) -> ActionResult:
    if IS_WINDOWS:
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return ActionResult("ok", "열었습니다.")
        except OSError as exc:
            return ActionResult("error", f"열기 실패: {exc}")
    if IS_MACOS:
        return _spawn(["open", url])
    if IS_LINUX and shutil.which("xdg-open"):
        return _spawn(["xdg-open", url])
    return ActionResult("skipped", "이 OS에서는 자동으로 열 수 없습니다.")


def _open_path(path: str | Path) -> ActionResult:
    p = str(path)
    if IS_WINDOWS:
        try:
            os.startfile(p)  # type: ignore[attr-defined]
            return ActionResult("ok", f"열었습니다: {p}")
        except OSError as exc:
            return ActionResult("error", f"열기 실패: {exc}")
    if IS_MACOS:
        return _spawn(["open", p])
    if IS_LINUX and shutil.which("xdg-open"):
        return _spawn(["xdg-open", p])
    return ActionResult("skipped", "이 OS에서는 자동으로 열 수 없습니다.")


# ── General actions ──────────────────────────────────────────────────────────

@register("open_url")
def _action_open_url(args: dict) -> ActionResult:
    url = str(args.get("url") or "").strip()
    if not url:
        return ActionResult("error", "URL이 지정되지 않았습니다.")
    if not (url.startswith("http://") or url.startswith("https://")):
        return ActionResult("error", "허용되지 않은 URL 형식입니다.")
    return _open_url(url)


@register("open_task_manager")
def _open_task_manager(_: dict) -> ActionResult:
    if IS_WINDOWS:
        return _spawn(["taskmgr"])
    if IS_MACOS:
        return _spawn(["open", "-a", "Activity Monitor"])
    if IS_LINUX:
        for candidate in ("gnome-system-monitor", "ksysguard", "plasma-systemmonitor", "xfce4-taskmanager"):
            if shutil.which(candidate):
                return _spawn([candidate])
        if shutil.which("x-terminal-emulator") and shutil.which("htop"):
            return _spawn(["x-terminal-emulator", "-e", "htop"])
        return ActionResult("skipped", "GUI 작업 관리자를 찾지 못했습니다. 터미널에서 `top` 또는 `htop`을 실행하세요.")
    return ActionResult("skipped", "지원하지 않는 OS")


@register("open_resource_monitor")
def _open_resource_monitor(_: dict) -> ActionResult:
    if IS_WINDOWS:
        return _spawn(["resmon"])
    return _open_task_manager({})


@register("kill_process")
def _kill_process(args: dict) -> ActionResult:
    """Terminate a specific process by PID, verifying name to avoid PID reuse."""
    import psutil  # local import keeps actions importable on systems without it

    try:
        pid = int(args.get("pid", 0))
    except (TypeError, ValueError):
        pid = 0
    expected_name = (args.get("name") or "").strip()
    if pid <= 0:
        return ActionResult("error", "PID가 지정되지 않았습니다.")

    try:
        p = psutil.Process(pid)
        actual = p.name() or ""
        if expected_name and actual.lower() != expected_name.lower():
            return ActionResult(
                "error",
                f"PID {pid}의 프로세스 이름이 다릅니다 (기대: {expected_name}, 실제: {actual}). "
                "안전을 위해 종료를 취소했습니다.",
            )
        p.terminate()
        try:
            p.wait(timeout=3)
        except psutil.TimeoutExpired:
            p.kill()
            p.wait(timeout=2)
        return ActionResult("ok", f"`{actual}` (PID {pid}) 프로세스를 종료했습니다.")
    except psutil.NoSuchProcess:
        return ActionResult("ok", "이미 종료된 프로세스입니다.")
    except psutil.AccessDenied:
        return ActionResult(
            "error",
            "권한이 부족합니다. PC Doctor를 관리자(우클릭 → 관리자 권한으로 실행)로 실행해 주세요.",
        )


@register("restart_pc")
def _restart_pc(args: dict) -> ActionResult:
    delay = int(args.get("delay_sec", 60))
    if IS_WINDOWS:
        return _spawn(["shutdown", "/r", "/t", str(delay), "/c", "PC Doctor 권장에 따른 재시작"])
    if IS_MACOS:
        # Requires admin auth; we surface a nice message either way.
        try:
            subprocess.Popen(["osascript", "-e", 'tell app "System Events" to restart'])
            return ActionResult("ok", "재시작 요청을 보냈습니다.")
        except OSError as exc:
            return ActionResult("error", f"재시작 실패: {exc}")
    if IS_LINUX:
        if shutil.which("systemctl"):
            return _spawn(["systemctl", "reboot"])
        if shutil.which("shutdown"):
            return _spawn(["shutdown", "-r", f"+{max(1, delay // 60)}"])
        return ActionResult("skipped", "재시작 명령을 찾지 못했습니다.")
    return ActionResult("skipped", "지원하지 않는 OS")


@register("cancel_restart")
def _cancel_restart(_: dict) -> ActionResult:
    if IS_WINDOWS:
        return _spawn(["shutdown", "/a"])
    if IS_LINUX and shutil.which("shutdown"):
        return _spawn(["shutdown", "-c"])
    return ActionResult("skipped", "취소할 재시작 예약이 없거나 지원하지 않습니다.")


# ── Storage / disk actions ───────────────────────────────────────────────────

@register("open_disk_cleanup")
def _open_disk_cleanup(_: dict) -> ActionResult:
    if IS_WINDOWS:
        return _spawn(["cleanmgr"])
    if IS_MACOS:
        return _spawn(["open", "-a", "Storage Management"])
    if IS_LINUX:
        for candidate in ("baobab", "gnome-disks", "filelight"):
            if shutil.which(candidate):
                return _spawn([candidate])
        return ActionResult("skipped", "디스크 정리 도구를 찾지 못했습니다.")
    return ActionResult("skipped", "지원하지 않는 OS")


@register("open_storage_settings")
def _open_storage_settings(_: dict) -> ActionResult:
    if IS_WINDOWS:
        return _open_url("ms-settings:storagesense")
    if IS_MACOS:
        return _spawn(["open", "x-apple.systempreferences:com.apple.settings.Storage"])
    return ActionResult("skipped", "이 OS에서는 저장소 설정을 자동으로 열 수 없습니다.")


@register("clear_temp_files")
def _clear_temp_files(args: dict) -> ActionResult:
    """Remove files older than `older_than_days` from the temp directory.

    Defaults to 7 days. Skips files we can't touch (in-use, permissions).
    """
    older_than_days = int(args.get("older_than_days", 7))
    cutoff = time.time() - older_than_days * 86400
    temp_dir = Path(tempfile.gettempdir())
    if not temp_dir.exists():
        return ActionResult("skipped", "임시 폴더를 찾지 못했습니다.")

    try:
        entries = list(temp_dir.iterdir())
    except (PermissionError, OSError) as exc:
        return ActionResult("error", f"임시 폴더 접근 거부: {exc}")

    removed = 0
    freed = 0
    skipped = 0
    for entry in entries:
        try:
            stat = entry.stat()
            if stat.st_mtime > cutoff:
                continue
            if entry.is_file() or entry.is_symlink():
                size = stat.st_size if entry.is_file() else 0
                entry.unlink()
                removed += 1
                freed += size
            elif entry.is_dir():
                size = sum(p.stat().st_size for p in entry.rglob("*") if p.is_file())
                shutil.rmtree(entry, ignore_errors=True)
                removed += 1
                freed += size
        except (PermissionError, OSError):
            skipped += 1
            continue

    mb = freed / (1024 * 1024)
    msg = f"{removed}개 항목 삭제 · 약 {mb:.1f} MB 확보"
    if skipped:
        msg += f" · 사용 중 {skipped}개 건너뜀"
    return ActionResult("ok", msg)


@register("clear_browser_cache")
def _clear_browser_cache(_: dict) -> ActionResult:
    """Remove cache directories of common browsers.

    Skips files that are locked (browser running) — the browser will
    rebuild any in-use cache on next launch.
    """
    targets: list[Path] = []
    home = Path.home()
    if IS_WINDOWS:
        local = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")))
        roaming = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
        targets += [
            local / "Google" / "Chrome" / "User Data" / "Default" / "Cache",
            local / "Google" / "Chrome" / "User Data" / "Default" / "Code Cache",
            local / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache",
            local / "Microsoft" / "Edge" / "User Data" / "Default" / "Code Cache",
            local / "BraveSoftware" / "Brave-Browser" / "User Data" / "Default" / "Cache",
            local / "Mozilla" / "Firefox" / "Profiles",  # special-cased below
            roaming / "Mozilla" / "Firefox" / "Profiles",
        ]
    elif IS_MACOS:
        targets += [
            home / "Library" / "Caches" / "Google" / "Chrome" / "Default" / "Cache",
            home / "Library" / "Caches" / "com.apple.Safari",
            home / "Library" / "Caches" / "Firefox" / "Profiles",
        ]
    else:  # Linux
        targets += [
            home / ".cache" / "google-chrome" / "Default" / "Cache",
            home / ".cache" / "chromium" / "Default" / "Cache",
            home / ".cache" / "mozilla" / "firefox",
        ]

    removed_dirs = 0
    freed = 0
    skipped = 0

    def _purge_dir(d: Path) -> None:
        nonlocal removed_dirs, freed, skipped
        if not d.exists():
            return
        for entry in d.iterdir():
            try:
                if entry.is_file() or entry.is_symlink():
                    size = entry.stat().st_size if entry.is_file() else 0
                    entry.unlink()
                    freed += size
                elif entry.is_dir():
                    size = sum(p.stat().st_size for p in entry.rglob("*") if p.is_file())
                    shutil.rmtree(entry, ignore_errors=True)
                    freed += size
                    removed_dirs += 1
            except (PermissionError, OSError):
                skipped += 1

    for t in targets:
        if not t.exists():
            continue
        if t.name == "Profiles":  # Firefox: clear `cache2` of each profile
            try:
                for prof in t.iterdir():
                    if prof.is_dir():
                        _purge_dir(prof / "cache2")
            except OSError:
                pass
        else:
            _purge_dir(t)

    if freed == 0 and skipped == 0:
        return ActionResult("ok", "정리할 브라우저 캐시가 없습니다.")
    mb = freed / (1024 * 1024)
    msg = f"브라우저 캐시 약 {mb:.1f} MB 정리"
    if skipped:
        msg += f" · 사용 중 {skipped}개 건너뜀 (브라우저 종료 후 재시도 권장)"
    return ActionResult("ok", msg)


@register("clear_windows_temp")
def _clear_windows_temp(args: dict) -> ActionResult:
    """Cleanup: %TEMP% always, %WINDIR%\\Temp if accessible (admin)."""
    older_than_days = int(args.get("older_than_days", 1))
    cutoff = time.time() - older_than_days * 86400

    temps: list[Path] = [Path(tempfile.gettempdir())]
    if IS_WINDOWS:
        windir = os.environ.get("WINDIR", r"C:\Windows")
        temps.append(Path(windir) / "Temp")

    removed = 0
    freed = 0
    skipped = 0
    locked_dirs: list[str] = []

    for tdir in temps:
        if not tdir.exists():
            continue
        try:
            entries = list(tdir.iterdir())
        except (PermissionError, OSError):
            # 일반 권한으로는 listing 자체가 불가 — 관리자 권한 필요
            locked_dirs.append(str(tdir))
            continue

        for entry in entries:
            try:
                stat = entry.stat()
                if stat.st_mtime > cutoff:
                    continue
                if entry.is_file() or entry.is_symlink():
                    size = stat.st_size if entry.is_file() else 0
                    entry.unlink()
                    removed += 1
                    freed += size
                elif entry.is_dir():
                    size = sum(p.stat().st_size for p in entry.rglob("*") if p.is_file())
                    shutil.rmtree(entry, ignore_errors=True)
                    removed += 1
                    freed += size
            except (PermissionError, OSError):
                skipped += 1
                continue

    mb = freed / (1024 * 1024)
    msg = f"임시 파일 {removed}개 정리 · 약 {mb:.1f} MB 확보"
    if skipped:
        msg += f" · 사용 중 {skipped}개 건너뜀"
    if locked_dirs:
        msg += (
            f"\n\n관리자 권한이 필요한 폴더 {len(locked_dirs)}개를 건너뛰었습니다: "
            f"{', '.join(locked_dirs)}\n"
            "전체 정리를 원하면 '관리자 권한으로 재시작' 후 다시 실행하세요."
        )
    return ActionResult("ok", msg)


@register("restart_as_admin")
def _restart_as_admin(_: dict) -> ActionResult:
    """Relaunch the current PC Doctor process with UAC elevation (Windows)."""
    if not IS_WINDOWS:
        return ActionResult("skipped", "Windows에서만 사용 가능합니다.")
    try:
        import ctypes
        # 현재 실행 중인 .py 또는 main.py 경로
        script = sys.argv[0] if sys.argv and sys.argv[0] else ""
        if not script or not Path(script).exists():
            # fallback: project root main.py
            script = str(Path(__file__).resolve().parent.parent / "main.py")

        # Quote args properly
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        full_params = f'"{script}" {params}'.strip()

        # ShellExecuteW with "runas" verb triggers UAC
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, full_params, None, 1,
        )
        # 32 이하면 실패 (대표값: 0=메모리부족, 5=거부)
        if ret <= 32:
            if ret == 5:
                return ActionResult("error", "UAC 승인이 거부되었습니다.")
            return ActionResult("error", f"재시작 실패 (code {ret})")

        # 성공 — 잠시 후 현재 프로세스 종료
        def _exit_soon() -> None:
            time.sleep(0.5)
            os._exit(0)
        import threading
        threading.Thread(target=_exit_soon, daemon=True).start()
        return ActionResult("ok", "관리자 권한으로 재시작하는 중… 현재 창은 곧 닫힙니다.")
    except Exception as exc:  # noqa: BLE001
        return ActionResult("error", f"재시작 실패: {exc}")


@register("find_old_apps")
def _find_old_apps(_: dict) -> ActionResult:
    """Open Windows 'Apps & Features' (sortable by install date / size).

    Native Settings already exposes the 'least used' / 'oldest install'
    information per app — we just open it.
    """
    if IS_WINDOWS:
        return _open_url("ms-settings:appsfeatures")
    if IS_MACOS:
        return _spawn(["open", "/Applications"])
    if IS_LINUX:
        for candidate in ("gnome-software", "plasma-discover"):
            if shutil.which(candidate):
                return _spawn([candidate])
    return ActionResult("skipped", "이 OS에서는 자동으로 열 수 없습니다.")


@register("open_recycle_bin")
def _open_recycle_bin(_: dict) -> ActionResult:
    if IS_WINDOWS:
        return _open_url("shell:RecycleBinFolder")
    if IS_MACOS:
        return _spawn(["open", str(Path.home() / ".Trash")])
    if IS_LINUX:
        trash = Path.home() / ".local" / "share" / "Trash" / "files"
        if trash.exists():
            return _open_path(trash)
    return ActionResult("skipped", "휴지통을 찾지 못했습니다.")


@register("empty_recycle_bin")
def _empty_recycle_bin(_: dict) -> ActionResult:
    if IS_WINDOWS:
        # Windows API SHEmptyRecycleBinW — 일반 권한으로 동작, PowerShell
        # 실행 정책의 영향을 받지 않음.
        try:
            import ctypes
            fn = ctypes.windll.shell32.SHEmptyRecycleBinW
            fn.restype = ctypes.c_int  # 명시적 HRESULT 타입 지정
            SHERB_NOCONFIRMATION = 0x00000001
            SHERB_NOPROGRESSUI   = 0x00000002
            SHERB_NOSOUND        = 0x00000004
            flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
            hr = fn(None, None, flags)
            # S_OK (0): 성공
            # 0x8000FFFF / -2147418113: E_UNEXPECTED — 일부 빌드에서 이미 비어 있을 때
            # 0x80070002 / -2147024894: ERROR_FILE_NOT_FOUND — 비어 있을 때
            # 0x80070057 / -2147024809: E_INVALIDARG — 일부 구형 빌드
            # S_FALSE (1): 비어 있거나 작업 없음
            _ALREADY_EMPTY = {-2147418113, -2147024894, -2147024809, 1}
            if hr == 0:
                return ActionResult("ok", "휴지통을 비웠습니다.")
            if hr in _ALREADY_EMPTY or (hr & 0xFFFFFFFF) in {0x8000FFFF, 0x80070002, 0x80070057}:
                return ActionResult("ok", "휴지통이 이미 비어 있습니다.")
            return ActionResult("error", f"휴지통 비우기 실패 (HRESULT 0x{hr & 0xFFFFFFFF:08X})")
        except Exception as exc:  # noqa: BLE001
            return ActionResult("error", f"휴지통 비우기 실패: {exc}")
    if IS_MACOS:
        rc, _, err = _run_and_capture(["osascript", "-e", 'tell application "Finder" to empty trash'])
        return ActionResult("ok", "휴지통을 비웠습니다.") if rc == 0 else ActionResult("error", err or "실패")
    if IS_LINUX:
        trash = Path.home() / ".local" / "share" / "Trash"
        if not trash.exists():
            return ActionResult("skipped", "휴지통이 비어 있거나 없습니다.")
        try:
            shutil.rmtree(trash / "files", ignore_errors=True)
            shutil.rmtree(trash / "info", ignore_errors=True)
            (trash / "files").mkdir(exist_ok=True)
            (trash / "info").mkdir(exist_ok=True)
            return ActionResult("ok", "휴지통을 비웠습니다.")
        except OSError as exc:
            return ActionResult("error", f"실패: {exc}")
    return ActionResult("skipped", "지원하지 않는 OS")


@register("open_startup_manager")
def _open_startup_manager(_: dict) -> ActionResult:
    """Open Task Manager directly to the Startup Apps tab (Windows 11/10)."""
    if IS_WINDOWS:
        # taskmgr /0 /startup opens the Startup tab on Windows 10/11
        result = _spawn(["taskmgr", "/0", "/startup"])
        if result.ok:
            return ActionResult("ok", "작업 관리자 → 시작 프로그램 탭을 열었습니다.")
        # Fallback: just open taskmgr
        return _spawn(["taskmgr"])
    return ActionResult("skipped", "Windows에서만 사용 가능합니다.")


@register("open_optimize_drives")
def _open_optimize_drives(_: dict) -> ActionResult:
    if IS_WINDOWS:
        return _spawn(["dfrgui"])
    return ActionResult("skipped", "Windows에서만 사용 가능합니다.")


@register("run_chkdsk")
def _run_chkdsk(args: dict) -> ActionResult:
    """Run chkdsk with UAC elevation via ShellExecuteW runas verb."""
    if not IS_WINDOWS:
        return ActionResult("skipped", "Windows에서만 사용 가능합니다.")
    drive = str(args.get("drive", "C:"))
    try:
        import ctypes
        # ShellExecuteW with "runas" directly triggers UAC — no PowerShell middleman.
        # /f: 오류 수정 (드라이브 사용 중이면 다음 부팅 시 예약됨)
        # /r: 불량 섹터 복구 (/f 포함)
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "cmd.exe",
            f'/k echo 디스크 검사 시작 중... && chkdsk {drive} /f /r && pause',
            None, 1,
        )
        if ret > 32:
            return ActionResult(
                "ok",
                f"{drive} 디스크 검사 창이 열립니다.\n"
                "UAC 승인 후 검사가 시작됩니다.\n"
                "C: 드라이브는 사용 중이므로 '예'를 누르면 다음 재부팅 때 자동 검사됩니다.",
            )
        if ret == 5:
            return ActionResult("error", "UAC 승인이 거부되었습니다.")
        return ActionResult("error", f"실행 실패 (코드 {ret})")
    except OSError as exc:
        return ActionResult("error", f"실행 실패: {exc}")


# ── Network actions ──────────────────────────────────────────────────────────

@register("flush_dns")
def _flush_dns(_: dict) -> ActionResult:
    if IS_WINDOWS:
        rc, out, err = _run_and_capture(["ipconfig", "/flushdns"], timeout=15)
        if rc == 0:
            return ActionResult("ok", "DNS 캐시를 비웠습니다.")
        return ActionResult("error", err or out or "실패")
    if IS_MACOS:
        rc, _, err = _run_and_capture(["sudo", "-n", "dscacheutil", "-flushcache"], timeout=10)
        if rc == 0:
            return ActionResult("ok", "DNS 캐시를 비웠습니다.")
        return ActionResult("error", "sudo 권한이 필요합니다. 터미널에서 실행하세요: sudo dscacheutil -flushcache")
    if IS_LINUX:
        if shutil.which("resolvectl"):
            rc, _, err = _run_and_capture(["resolvectl", "flush-caches"])
            if rc == 0:
                return ActionResult("ok", "DNS 캐시를 비웠습니다.")
            return ActionResult("error", err or "실패")
        return ActionResult("skipped", "systemd-resolved가 없습니다. NetworkManager 재시작을 시도하세요.")
    return ActionResult("skipped", "지원하지 않는 OS")


@register("open_network_settings")
def _open_network_settings(_: dict) -> ActionResult:
    if IS_WINDOWS:
        return _open_url("ms-settings:network")
    if IS_MACOS:
        return _spawn(["open", "x-apple.systempreferences:com.apple.preference.network"])
    if IS_LINUX and shutil.which("nm-connection-editor"):
        return _spawn(["nm-connection-editor"])
    return ActionResult("skipped", "네트워크 설정을 자동으로 열 수 없습니다.")


@register("reset_network_adapter")
def _reset_network_adapter(_: dict) -> ActionResult:
    if IS_WINDOWS:
        rc1, _, _ = _run_and_capture(["ipconfig", "/release"], timeout=20)
        rc2, _, _ = _run_and_capture(["ipconfig", "/renew"], timeout=30)
        if rc1 == 0 and rc2 == 0:
            return ActionResult("ok", "네트워크 어댑터를 재설정했습니다.")
        return ActionResult("error", "네트워크 재설정 실패 — 관리자 권한이 필요할 수 있습니다.")
    return ActionResult("skipped", "Windows에서만 사용 가능합니다.")


# ── Windows-specific actions ────────────────────────────────────────────────

@register("open_windows_update")
def _open_windows_update(_: dict) -> ActionResult:
    if IS_WINDOWS:
        return _open_url("ms-settings:windowsupdate")
    return ActionResult("skipped", "Windows에서만 사용 가능합니다.")


@register("run_defender_scan")
def _run_defender_scan(args: dict) -> ActionResult:
    if not IS_WINDOWS:
        return ActionResult("skipped", "Windows Defender는 Windows에서만 사용 가능합니다.")
    scan_type = str(args.get("scan_type", "QuickScan"))
    ps = f"Start-MpScan -ScanType {scan_type}"
    return _spawn(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps])


@register("update_defender_signatures")
def _update_defender_signatures(_: dict) -> ActionResult:
    if not IS_WINDOWS:
        return ActionResult("skipped", "Windows에서만 사용 가능합니다.")
    rc, _, err = _run_and_capture(
        ["powershell", "-NoProfile", "-Command", "Update-MpSignature"], timeout=120,
    )
    if rc == 0:
        return ActionResult("ok", "Windows Defender 정의를 업데이트했습니다.")
    return ActionResult("error", err or "업데이트 실패 — 관리자 권한이 필요할 수 있습니다.")


@register("open_defender")
def _open_defender(_: dict) -> ActionResult:
    if IS_WINDOWS:
        return _open_url("windowsdefender:")
    return ActionResult("skipped", "Windows에서만 사용 가능합니다.")


@register("run_sfc_scan")
def _run_sfc_scan(_: dict) -> ActionResult:
    if not IS_WINDOWS:
        return ActionResult("skipped", "Windows에서만 사용 가능합니다.")
    # SFC needs an elevated console — open one for the user.
    return _spawn(["cmd", "/c", "start", "cmd", "/k", "sfc /scannow"])


@register("run_dism_repair")
def _run_dism_repair(_: dict) -> ActionResult:
    if not IS_WINDOWS:
        return ActionResult("skipped", "Windows에서만 사용 가능합니다.")
    return _spawn(["cmd", "/c", "start", "cmd", "/k", "DISM /Online /Cleanup-Image /RestoreHealth"])


# ── Hardware actions ────────────────────────────────────────────────────────

@register("open_device_manager")
def _open_device_manager(_: dict) -> ActionResult:
    if IS_WINDOWS:
        return _spawn(["devmgmt.msc"], shell=True)
    if IS_MACOS:
        return _spawn(["open", "/System/Library/CoreServices/Applications/System Information.app"])
    return ActionResult("skipped", "Windows/macOS에서만 사용 가능합니다.")


@register("open_event_viewer")
def _open_event_viewer(_: dict) -> ActionResult:
    if IS_WINDOWS:
        return _spawn(["eventvwr.msc"], shell=True)
    return ActionResult("skipped", "Windows에서만 사용 가능합니다.")


@register("open_services")
def _open_services(_: dict) -> ActionResult:
    if IS_WINDOWS:
        return _spawn(["services.msc"], shell=True)
    return ActionResult("skipped", "Windows에서만 사용 가능합니다.")


@register("open_smart_report")
def _open_smart_report(args: dict) -> ActionResult:
    if not IS_WINDOWS:
        if shutil.which("smartctl"):
            device = args.get("device") or "/dev/sda"
            rc, out, err = _run_and_capture(["smartctl", "-H", str(device)], timeout=15)
            return ActionResult("ok", out or "smartctl 출력 없음") if rc in (0, 4) else ActionResult("error", err or "smartctl 실패")
        return ActionResult("skipped", "smartctl이 설치되어 있지 않습니다.")
    # Windows: surface PowerShell physical-disk health
    ps = (
        "Get-PhysicalDisk -ErrorAction SilentlyContinue |"
        " Format-Table -AutoSize FriendlyName, HealthStatus, OperationalStatus, MediaType, Size"
    )
    rc, out, err = _run_and_capture(["powershell", "-NoProfile", "-Command", ps], timeout=15)
    if rc == 0 and out:
        return ActionResult("ok", out)
    # Fallback for very old Windows
    rc, out, err = _run_and_capture(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_DiskDrive | Format-Table -AutoSize Model, Status, Size, MediaType"],
        timeout=15,
    )
    if rc == 0 and out:
        return ActionResult("ok", out)
    return ActionResult("error", err or "디스크 상태를 읽지 못했습니다.")


# ── App self-update ─────────────────────────────────────────────────────────

@register("check_for_updates")
def _check_for_updates(_: dict) -> ActionResult:
    """Run `git pull --ff-only` in the project root and report changes."""
    if not shutil.which("git"):
        return ActionResult("error", "git이 설치되어 있지 않습니다.")

    project_root = Path(__file__).resolve().parent.parent
    if not (project_root / ".git").exists():
        return ActionResult(
            "skipped",
            "이 폴더는 git 저장소가 아닙니다 (ZIP으로 받은 경우).\n"
            "자동 업데이트를 쓰려면 폴더를 지우고 git clone으로 다시 받으세요."
        )

    try:
        rc_fetch, _, err_fetch = _run_and_capture(
            ["git", "-C", str(project_root), "fetch", "origin"], timeout=30,
        )
        if rc_fetch != 0:
            return ActionResult("error", f"fetch 실패: {err_fetch}")

        # 진단 정보: 현재 commit + origin/main commit
        _, head_info, _ = _run_and_capture(
            ["git", "-C", str(project_root), "log", "-1",
             "--pretty=format:%h %s (%cs)", "HEAD"], timeout=5,
        )
        _, remote_info, _ = _run_and_capture(
            ["git", "-C", str(project_root), "log", "-1",
             "--pretty=format:%h %s (%cs)", "origin/main"], timeout=5,
        )
        diag = (
            f"\n\n📂 폴더: {project_root}"
            f"\n📌 현재: {head_info or '?'}"
            f"\n🌐 원격: {remote_info or '?'}"
        )

        rc_log, log_out, _ = _run_and_capture(
            ["git", "-C", str(project_root), "log", "HEAD..origin/main", "--oneline"],
            timeout=10,
        )
        new_commits = [ln for ln in (log_out.splitlines() if log_out else []) if ln.strip()]
        if not new_commits:
            return ActionResult(
                "ok",
                "이미 최신 버전입니다." + diag +
                "\n\n새 기능이 안 보이면 PC Doctor를 한 번 닫고 다시 실행해 주세요."
            )

        rc_pull, pull_out, err_pull = _run_and_capture(
            ["git", "-C", str(project_root), "pull", "--ff-only", "origin", "main"],
            timeout=30,
        )
        if rc_pull != 0:
            return ActionResult(
                "error",
                f"업데이트 실패: {err_pull or pull_out}\n"
                "로컬 변경 사항이 충돌했을 수 있습니다 — '강제 재설치'를 시도해 주세요."
                + diag
            )

        summary = "\n".join(f"• {c}" for c in new_commits[:10])
        more = f"\n…외 {len(new_commits) - 10}건" if len(new_commits) > 10 else ""
        return ActionResult(
            "ok",
            f"{len(new_commits)}건의 업데이트를 받았습니다:\n\n{summary}{more}\n\n"
            "변경 사항은 PC Doctor를 재시작하면 적용됩니다." + diag
        )
    except Exception as exc:  # noqa: BLE001
        return ActionResult("error", f"업데이트 중 오류: {exc}")


@register("force_reinstall")
def _force_reinstall(_: dict) -> ActionResult:
    """Aggressive update: fetch + reset --hard origin/main.

    Discards any local modifications (the user explicitly asks for this).
    Useful when the working tree got out of sync with HEAD or pulls keep
    being rejected.
    """
    if not shutil.which("git"):
        return ActionResult("error", "git이 설치되어 있지 않습니다.")

    project_root = Path(__file__).resolve().parent.parent
    if not (project_root / ".git").exists():
        return ActionResult(
            "skipped",
            "이 폴더는 git 저장소가 아닙니다.\n"
            "폴더를 지우고 git clone으로 다시 받으세요."
        )

    try:
        rc, _, err = _run_and_capture(
            ["git", "-C", str(project_root), "fetch", "origin"], timeout=30,
        )
        if rc != 0:
            return ActionResult("error", f"fetch 실패: {err}")

        rc, _, err = _run_and_capture(
            ["git", "-C", str(project_root), "reset", "--hard", "origin/main"],
            timeout=20,
        )
        if rc != 0:
            return ActionResult("error", f"reset 실패: {err}")

        return ActionResult(
            "ok",
            "강제 재설치 완료. 모든 로컬 변경 사항을 폐기하고 origin/main으로 맞췄습니다."
        )
    except Exception as exc:  # noqa: BLE001
        return ActionResult("error", f"재설치 중 오류: {exc}")



@register("restart_app")
def _restart_app(_: dict) -> ActionResult:
    """Relaunch the current PC Doctor process (no elevation)."""
    try:
        project_root = Path(__file__).resolve().parent.parent
        main_py = project_root / "main.py"
        if not main_py.exists():
            return ActionResult("error", "main.py를 찾지 못했습니다.")

        kwargs: dict[str, Any] = {"close_fds": True}
        if IS_WINDOWS:
            kwargs["creationflags"] = 0x00000010  # CREATE_NEW_CONSOLE
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([sys.executable, str(main_py)], **kwargs)

        import threading
        def _exit_soon() -> None:
            time.sleep(0.4)
            os._exit(0)
        threading.Thread(target=_exit_soon, daemon=True).start()
        return ActionResult("ok", "재시작 중…")
    except Exception as exc:  # noqa: BLE001
        return ActionResult("error", f"재시작 실패: {exc}")


# ── Inventory-driven maintenance actions ────────────────────────────────────

@register("uninstall_app")
def _uninstall_app(args: dict) -> ActionResult:
    """Run an installed program's uninstaller string.

    Caller passes `uninstall_string` (and optional `quiet_uninstall_string`).
    We prefer the quiet version if available. The uninstaller itself decides
    whether to prompt the user; we just spawn it detached.
    """
    if not IS_WINDOWS:
        return ActionResult("skipped", "Windows에서만 사용 가능합니다.")
    cmd = (args.get("quiet_uninstall_string") or args.get("uninstall_string") or "").strip()
    name = (args.get("name") or "프로그램").strip()
    if not cmd:
        return ActionResult("error", "제거 명령어가 없습니다.")
    try:
        # Use cmd /c so registry uninstall strings with quotes/args work uniformly.
        subprocess.Popen(f'cmd /c "{cmd}"', shell=True, close_fds=True)
        return ActionResult("ok", f"`{name}` 제거 마법사를 실행했습니다.")
    except OSError as exc:
        return ActionResult("error", f"제거 실행 실패: {exc}")


@register("disable_startup")
def _disable_startup(args: dict) -> ActionResult:
    """Disable a startup program using the StartupApproved registry key (non-destructive).

    If ApprovedPath is provided, writes a disabled byte-flag so the program
    can be re-enabled later (same approach as Task Manager). Falls back to
    removing the Run key value for RunOnce entries that have no ApprovedPath.

    Args: reg_path, approved_path, name.
    """
    if not IS_WINDOWS:
        return ActionResult("skipped", "Windows에서만 사용 가능합니다.")
    reg_path     = (args.get("reg_path") or "").strip()
    approved_path = (args.get("approved_path") or "").strip()
    name         = (args.get("name") or "").strip()
    if not name:
        return ActionResult("error", "프로그램 이름이 비어 있습니다.")

    safe_name = name.replace("'", "''")

    # Preferred: write disabled flag to StartupApproved (recoverable)
    if approved_path:
        safe_ap = approved_path.replace("'", "''")
        ps = (
            f"$p='{safe_ap}';"
            " $d=[byte[]](3,0,0,0,0,0,0,0,0,0,0,0);"
            " if(-not(Test-Path $p)){New-Item -Path $p -Force|Out-Null};"
            f" Set-ItemProperty -Path $p -Name '{safe_name}' -Value $d -Type Binary -ErrorAction Stop;"
            " 'OK'"
        )
        rc, out, err = _run_and_capture(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", ps],
            timeout=15,
        )
        if rc == 0 and "OK" in out:
            return ActionResult("ok", f"`{name}` 비활성화됨 (다음 부팅부터 적용, 언제든 재활성화 가능)")
        if "denied" in (err or "").lower() or "access" in (err or "").lower():
            return ActionResult("error",
                "권한이 부족합니다 (HKLM 항목은 관리자 필요). "
                "빠른 도구 → 관리자 권한으로 재시작 후 다시 시도해 주세요.")

    # Fallback: remove from Run key (RunOnce or no ApprovedPath)
    if not reg_path:
        return ActionResult("error", "레지스트리 경로가 비어 있습니다.")
    safe_path = reg_path.replace("'", "''")
    ps = f"Remove-ItemProperty -Path '{safe_path}' -Name '{safe_name}' -ErrorAction Stop"
    rc, out, err = _run_and_capture(
        ["powershell", "-NoProfile", "-NonInteractive",
         "-ExecutionPolicy", "Bypass", "-Command", ps],
        timeout=15,
    )
    if rc == 0:
        return ActionResult("ok", f"`{name}` 시작 프로그램에서 제거됨")
    if "denied" in (err or "").lower() or "access" in (err or "").lower():
        return ActionResult("error",
            "권한이 부족합니다 (HKLM의 시작 프로그램은 관리자 필요). "
            "빠른 도구 → 관리자 권한으로 재시작 후 다시 시도해 주세요.")
    return ActionResult("error", err or out or "제거 실패")


@register("enable_startup")
def _enable_startup(args: dict) -> ActionResult:
    """Re-enable a previously disabled startup program via StartupApproved key.

    Args: approved_path, name.
    """
    if not IS_WINDOWS:
        return ActionResult("skipped", "Windows에서만 사용 가능합니다.")
    approved_path = (args.get("approved_path") or "").strip()
    name          = (args.get("name") or "").strip()
    if not approved_path or not name:
        return ActionResult("error", "StartupApproved 경로 또는 이름이 비어 있습니다.")
    safe_ap   = approved_path.replace("'", "''")
    safe_name = name.replace("'", "''")
    ps = (
        f"$p='{safe_ap}';"
        " $d=[byte[]](2,0,0,0,0,0,0,0,0,0,0,0);"
        " if(-not(Test-Path $p)){New-Item -Path $p -Force|Out-Null};"
        f" Set-ItemProperty -Path $p -Name '{safe_name}' -Value $d -Type Binary -ErrorAction Stop;"
        " 'OK'"
    )
    rc, out, err = _run_and_capture(
        ["powershell", "-NoProfile", "-NonInteractive",
         "-ExecutionPolicy", "Bypass", "-Command", ps],
        timeout=15,
    )
    if rc == 0 and "OK" in out:
        return ActionResult("ok", f"`{name}` 활성화됨 (다음 부팅부터 적용)")
    if "denied" in (err or "").lower() or "access" in (err or "").lower():
        return ActionResult("error",
            "권한이 부족합니다 (HKLM 항목은 관리자 필요). "
            "빠른 도구 → 관리자 권한으로 재시작 후 다시 시도해 주세요.")
    return ActionResult("error", err or out or "활성화 실패")


@register("uninstall_hotfix")
def _uninstall_hotfix(args: dict) -> ActionResult:
    """Uninstall a Windows update by KB id (admin required)."""
    if not IS_WINDOWS:
        return ActionResult("skipped", "Windows에서만 사용 가능합니다.")
    kb = (args.get("kb") or "").strip().upper()
    if not kb.startswith("KB"):
        return ActionResult("error", "KB ID 형식이 잘못되었습니다.")
    kb_num = kb[2:]
    # wusa /uninstall /kb:NNN /quiet /norestart
    try:
        subprocess.Popen(
            ["wusa.exe", "/uninstall", f"/kb:{kb_num}", "/quiet", "/norestart"],
            close_fds=True,
        )
        return ActionResult(
            "ok",
            f"{kb} 제거를 시작했습니다.\n"
            "관리자 권한 + 일부 업데이트는 영구 (제거 불가) — UAC 거절/실패는 백그라운드에서 일어납니다."
        )
    except OSError as exc:
        return ActionResult("error", f"wusa 실행 실패: {exc}")


@register("show_in_explorer")
def _show_in_explorer(args: dict) -> ActionResult:
    """Open Windows Explorer with the file selected (or open folder)."""
    p = (args.get("path") or "").strip()
    if not p:
        return ActionResult("error", "경로가 비어 있습니다.")
    target = Path(p)
    if not target.exists():
        return ActionResult("error", f"경로를 찾을 수 없습니다: {p}")
    if IS_WINDOWS:
        if target.is_file():
            return _spawn(["explorer.exe", "/select,", str(target)])
        return _spawn(["explorer.exe", str(target)])
    if IS_MACOS:
        return _spawn(["open", "-R", str(target)] if target.is_file() else ["open", str(target)])
    if IS_LINUX:
        return _open_path(target.parent if target.is_file() else target)
    return ActionResult("skipped", "지원하지 않는 OS")


@register("delete_file")
def _delete_file(args: dict) -> ActionResult:
    """Delete a file (move to recycle bin if possible)."""
    p = (args.get("path") or "").strip()
    if not p:
        return ActionResult("error", "경로가 비어 있습니다.")
    target = Path(p)
    if not target.exists():
        return ActionResult("ok", "이미 삭제된 파일입니다.")
    try:
        # Try recycle bin first via Windows Shell on Windows
        if IS_WINDOWS:
            try:
                import ctypes
                from ctypes import wintypes
                FO_DELETE = 0x0003
                FOF_ALLOWUNDO = 0x0040
                FOF_NOCONFIRMATION = 0x0010
                FOF_SILENT = 0x0004

                class SHFILEOPSTRUCT(ctypes.Structure):
                    _fields_ = [
                        ("hwnd", wintypes.HWND),
                        ("wFunc", wintypes.UINT),
                        ("pFrom", wintypes.LPCWSTR),
                        ("pTo", wintypes.LPCWSTR),
                        ("fFlags", ctypes.c_uint16),
                        ("fAnyOperationsAborted", wintypes.BOOL),
                        ("hNameMappings", ctypes.c_void_p),
                        ("lpszProgressTitle", wintypes.LPCWSTR),
                    ]

                op = SHFILEOPSTRUCT()
                op.wFunc = FO_DELETE
                op.pFrom = str(target) + "\0\0"
                op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
                rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
                if rc == 0:
                    return ActionResult("ok", f"휴지통으로 보냄: {target.name}")
                # Fall through to direct unlink on failure
            except OSError:
                pass
        target.unlink()
        return ActionResult("ok", f"삭제됨: {target.name}")
    except PermissionError:
        return ActionResult("error", "권한이 부족합니다.")
    except OSError as exc:
        return ActionResult("error", f"삭제 실패: {exc}")


# ── Process baseline trust ──────────────────────────────────────────────────

@register("trust_process")
def _trust_process(args: dict) -> ActionResult:
    """Add a process to the trusted baseline so it isn't flagged again."""
    from core import process_baseline
    name = (args.get("name") or "").strip()
    exe = (args.get("exe") or "").strip()
    if not name:
        return ActionResult("error", "프로세스 이름이 비어 있습니다.")
    process_baseline.trust(name, exe)
    return ActionResult("ok", f"`{name}` 을(를) 신뢰 목록에 추가했습니다.")


@register("reset_process_baseline")
def _reset_process_baseline(_: dict) -> ActionResult:
    from core import process_baseline
    process_baseline.reset()
    return ActionResult("ok", "프로세스 baseline 초기화 완료. 다음 검진은 처음 실행으로 처리됩니다.")


# ── Autostart on Windows boot ────────────────────────────────────────────────

_AUTOSTART_KEY_NAME = "PCDoctor"


@register("enable_autostart")
def _enable_autostart(_: dict) -> ActionResult:
    """Register PC Doctor to start when the user logs in (Windows)."""
    if not IS_WINDOWS:
        return ActionResult("skipped", "Windows에서만 사용 가능합니다.")
    try:
        import winreg
        project_root = Path(__file__).resolve().parent.parent
        main_py = project_root / "main.py"
        if not main_py.exists():
            return ActionResult("error", "main.py를 찾지 못했습니다.")
        # pythonw 우선 (콘솔 창 없이) → 없으면 python
        pyw = Path(sys.executable).with_name("pythonw.exe")
        runner = str(pyw if pyw.exists() else sys.executable)
        cmd = f'"{runner}" "{main_py}"'
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, _AUTOSTART_KEY_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        return ActionResult("ok", "Windows 시작 시 자동 실행 등록 완료.")
    except OSError as exc:
        return ActionResult("error", f"등록 실패: {exc}")


@register("disable_autostart")
def _disable_autostart(_: dict) -> ActionResult:
    if not IS_WINDOWS:
        return ActionResult("skipped", "Windows에서만 사용 가능합니다.")
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        try:
            winreg.DeleteValue(key, _AUTOSTART_KEY_NAME)
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        return ActionResult("ok", "자동 실행을 해제했습니다.")
    except OSError as exc:
        return ActionResult("error", f"해제 실패: {exc}")


def autostart_enabled() -> bool:
    """Helper for UI to render the toggle state."""
    if not IS_WINDOWS:
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_QUERY_VALUE,
        )
        try:
            winreg.QueryValueEx(key, _AUTOSTART_KEY_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except OSError:
        return False


# ── GPU driver page (vendor-aware) ───────────────────────────────────────────

_GPU_VENDOR_URLS = {
    "nvidia": "https://www.nvidia.co.kr/Download/index.aspx?lang=kr",
    "amd":    "https://www.amd.com/ko/support",
    "intel":  "https://www.intel.co.kr/content/www/kr/ko/support/detect.html",
}


@register("open_gpu_driver_page")
def _open_gpu_driver_page(_: dict) -> ActionResult:
    """Detect installed GPU vendor and open the right driver download page."""
    try:
        from core.checks.graphics import _vendor_of, _windows_gpus, _linux_gpus, _macos_gpus
    except ImportError:
        return ActionResult("error", "graphics 모듈을 찾지 못했습니다.")

    if IS_WINDOWS:
        gpus = _windows_gpus()
    elif IS_MACOS:
        gpus = _macos_gpus()
    elif IS_LINUX:
        gpus = _linux_gpus()
    else:
        gpus = []

    if not gpus:
        # 폴백: 모든 벤더 페이지를 한꺼번에 열어버리진 않고, 통합 안내 페이지로
        return _open_url("https://www.driverpack.io/ko")

    vendors = []
    for g in gpus:
        v = _vendor_of(g.get("name", ""))
        if v != "unknown" and v not in vendors:
            vendors.append(v)

    if not vendors:
        return _open_url("https://www.driverpack.io/ko")

    # 여러 벤더가 섞여 있으면 모두 새 창으로 열어준다 (외장+내장 같은 케이스)
    opened = []
    for v in vendors:
        url = _GPU_VENDOR_URLS.get(v)
        if url:
            _open_url(url)
            opened.append(v.upper())
    return ActionResult(
        "ok",
        f"GPU 드라이버 페이지를 열었습니다: {', '.join(opened)}",
    )
