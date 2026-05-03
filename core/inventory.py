"""System inventory — installed apps, startup programs, hotfixes, large files.

Each function returns a list of plain dicts so the UI layer can render rows
without OS-specific knowledge. All Windows lookups go through PowerShell
JSON to avoid CSV parsing bugs.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.platform import IS_WINDOWS


_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}


def _ps_json(script: str, timeout: int = 30) -> Any:
    if not IS_WINDOWS:
        return None
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=timeout, check=False,
            **_NO_WINDOW,
        )
        out = (proc.stdout or "").strip()
        if proc.returncode != 0 or not out:
            return None
        return json.loads(out)
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
        return None


def _as_list(data: Any) -> list:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return [data]


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def _parse_install_date(raw: Any) -> datetime | None:
    """Uninstall registry stores InstallDate as 'YYYYMMDD'."""
    s = _safe_str(raw).strip()
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return datetime.strptime(s, "%Y%m%d")
    except ValueError:
        return None


# ── Installed applications ───────────────────────────────────────────────────

def list_installed_apps() -> list[dict[str, Any]]:
    """Return apps from both 32-bit and 64-bit Uninstall registry hives.

    Each entry: {name, publisher, version, install_date, install_date_iso,
    age_days, size_bytes, size_human, uninstall_string, source}.
    """
    if not IS_WINDOWS:
        return []

    script = r"""
$paths = @(
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
);
$apps = @();
foreach ($p in $paths) {
    $items = Get-ItemProperty $p -ErrorAction SilentlyContinue;
    foreach ($i in $items) {
        if ($i.DisplayName -and -not $i.SystemComponent -and -not $i.ParentKeyName) {
            $apps += [PSCustomObject]@{
                Name           = $i.DisplayName
                Publisher      = $i.Publisher
                Version        = $i.DisplayVersion
                InstallDate    = $i.InstallDate
                EstimatedSize  = $i.EstimatedSize
                UninstallString= $i.UninstallString
                QuietUninstallString = $i.QuietUninstallString
                Source         = $p
            }
        }
    }
}
$apps | ConvertTo-Json -Compress -Depth 3
"""
    data = _ps_json(script, timeout=45)
    apps: list[dict[str, Any]] = []
    now = datetime.now()
    for row in _as_list(data):
        if not isinstance(row, dict):
            continue
        name = _safe_str(row.get("Name")).strip()
        if not name:
            continue
        date = _parse_install_date(row.get("InstallDate"))
        size_kb = row.get("EstimatedSize")
        try:
            size_bytes = int(size_kb) * 1024 if size_kb else 0
        except (TypeError, ValueError):
            size_bytes = 0
        age = (now - date).days if date else None
        apps.append({
            "name": name,
            "publisher": _safe_str(row.get("Publisher")).strip(),
            "version": _safe_str(row.get("Version")).strip(),
            "install_date": date.isoformat() if date else "",
            "install_date_iso": date.strftime("%Y-%m-%d") if date else "",
            "age_days": age,
            "size_bytes": size_bytes,
            "size_human": _bytes_to_human(size_bytes) if size_bytes else "",
            "uninstall_string": _safe_str(row.get("UninstallString")),
            "quiet_uninstall_string": _safe_str(row.get("QuietUninstallString")),
            "source": _safe_str(row.get("Source")),
        })
    # Sort by oldest install first; unknown dates at the end.
    apps.sort(key=lambda a: (a["age_days"] is None, -(a["age_days"] or 0)), reverse=False)
    return apps


# ── Startup programs ─────────────────────────────────────────────────────────

def list_startup_programs() -> list[dict[str, Any]]:
    """Return startup programs from registry Run keys and Startup folders.

    winreg 직접 사용 — PowerShell 없이 동작해 권한 오류를 방지한다.
    """
    if not IS_WINDOWS:
        return []

    import winreg

    # (hive, run_subkey, approved_subkey, scope, location_label)
    _RUN_KEYS = [
        (
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run",
            "user", "HKCU\\Run",
        ),
        (
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\RunOnce",
            "",
            "user", "HKCU\\RunOnce",
        ),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run",
            "machine", "HKLM\\Run",
        ),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32",
            "machine", "HKLM\\Run (32)",
        ),
    ]

    items: list[dict[str, Any]] = []

    for hive, run_sub, approved_sub, scope, loc in _RUN_KEYS:
        try:
            run_key = winreg.OpenKey(hive, run_sub, 0, winreg.KEY_READ)
        except OSError:
            continue

        # Read approved/disabled state
        approved_vals: dict[str, bytes] = {}
        if approved_sub:
            try:
                appr_key = winreg.OpenKey(hive, approved_sub, 0, winreg.KEY_READ)
                idx = 0
                while True:
                    try:
                        vname, vdata, vtype = winreg.EnumValue(appr_key, idx)
                        if isinstance(vdata, bytes):
                            approved_vals[vname] = vdata
                        idx += 1
                    except OSError:
                        break
                winreg.CloseKey(appr_key)
            except OSError:
                pass

        # Read Run values
        idx = 0
        while True:
            try:
                vname, vdata, _ = winreg.EnumValue(run_key, idx)
                idx += 1
            except OSError:
                break

            # byte[0] == 3 → disabled by Task Manager
            is_enabled = True
            raw = approved_vals.get(vname)
            if raw and len(raw) > 0 and raw[0] == 3:
                is_enabled = False

            hive_name = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
            reg_path = f"{hive_name}\\{run_sub}"
            appr_path = (f"{hive_name}\\{approved_sub}") if approved_sub else ""

            items.append({
                "name": str(vname),
                "command": str(vdata) if vdata else "",
                "scope": scope,
                "location": loc,
                "reg_path": reg_path,
                "approved_path": appr_path,
                "is_enabled": is_enabled,
                "is_folder": False,
            })

        winreg.CloseKey(run_key)

    # Startup shell folders
    _startup_folders = [
        (os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"), "user", "시작프로그램 폴더"),
        (os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\Startup"), "machine", "공용 시작프로그램 폴더"),
    ]
    for folder_path, scope, loc in _startup_folders:
        fp = Path(folder_path)
        if not fp.exists():
            continue
        try:
            for entry in fp.iterdir():
                if entry.is_file():
                    items.append({
                        "name": entry.stem,
                        "command": str(entry),
                        "scope": scope,
                        "location": loc,
                        "reg_path": "",
                        "approved_path": "",
                        "is_enabled": True,
                        "is_folder": True,
                    })
        except OSError:
            continue

    return items


# ── Windows updates / hotfixes ───────────────────────────────────────────────

def list_hotfixes() -> list[dict[str, Any]]:
    """Return installed Windows updates (KB articles) sorted newest first."""
    if not IS_WINDOWS:
        return []

    script = (
        "Get-HotFix | Sort-Object -Property InstalledOn -Descending |"
        " Select-Object HotFixID, Description, InstalledOn, InstalledBy |"
        " ConvertTo-Json -Compress -Depth 2"
    )
    data = _ps_json(script, timeout=20)
    items: list[dict[str, Any]] = []
    for row in _as_list(data):
        if not isinstance(row, dict):
            continue
        # Get-HotFix InstalledOn returns either a DateTime or {DateTime: '/Date(...)/}
        installed_on = row.get("InstalledOn")
        date_str = ""
        if isinstance(installed_on, dict):
            raw = installed_on.get("DateTime") or installed_on.get("value") or ""
            date_str = _safe_str(raw)
        elif installed_on:
            date_str = _safe_str(installed_on)
        items.append({
            "id": _safe_str(row.get("HotFixID")),
            "description": _safe_str(row.get("Description")),
            "installed_on": date_str[:10] if date_str else "",
            "installed_by": _safe_str(row.get("InstalledBy")),
        })
    return items


# ── Large files ──────────────────────────────────────────────────────────────

def list_large_files(roots: list[str] | None = None,
                     min_bytes: int = 100 * 1024 * 1024,
                     limit: int = 50) -> list[dict[str, Any]]:
    """Find files ≥ min_bytes in the given roots. Defaults to user profile."""
    if roots is None:
        home = Path.home()
        roots = [
            str(home / "Downloads"),
            str(home / "Desktop"),
            str(home / "Documents"),
            str(home / "Videos"),
        ]

    found: list[dict[str, Any]] = []
    for r in roots:
        root = Path(r)
        if not root.exists():
            continue
        try:
            for entry in root.rglob("*"):
                try:
                    if not entry.is_file():
                        continue
                    size = entry.stat().st_size
                    if size < min_bytes:
                        continue
                    found.append({
                        "path": str(entry),
                        "size_bytes": size,
                        "size_human": _bytes_to_human(size),
                        "modified": datetime.fromtimestamp(entry.stat().st_mtime).strftime("%Y-%m-%d"),
                    })
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            continue

    found.sort(key=lambda x: x["size_bytes"], reverse=True)
    return found[:limit]


def _bytes_to_human(n: int | float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(n)
    for u in units:
        if abs(v) < 1024.0:
            return f"{v:.1f} {u}" if u != "B" else f"{int(v)} B"
        v /= 1024.0
    return f"{v:.1f} PB"
