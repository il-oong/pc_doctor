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


def _ps_json(script: str, timeout: int = 30) -> Any:
    if not IS_WINDOWS:
        return None
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=timeout, check=False,
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
    """Return registry-based startup programs from HKCU & HKLM Run keys.

    Each entry: {name, command, location, scope ('user'|'machine'),
    enabled (best-effort)}.
    """
    if not IS_WINDOWS:
        return []

    script = r"""
$results = @();
$runs = @(
    @{Path='HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'; Scope='user'; Loc='HKCU\\Run'},
    @{Path='HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce'; Scope='user'; Loc='HKCU\\RunOnce'},
    @{Path='HKLM:\Software\Microsoft\Windows\CurrentVersion\Run'; Scope='machine'; Loc='HKLM\\Run'},
    @{Path='HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run'; Scope='machine'; Loc='HKLM\\Run (32)'}
);
foreach ($r in $runs) {
    $key = Get-Item $r.Path -ErrorAction SilentlyContinue;
    if ($key) {
        foreach ($valName in $key.GetValueNames()) {
            $cmd = $key.GetValue($valName);
            $results += [PSCustomObject]@{
                Name     = $valName
                Command  = $cmd
                Scope    = $r.Scope
                Location = $r.Loc
                RegPath  = $r.Path
            }
        }
    }
}
$results | ConvertTo-Json -Compress -Depth 3
"""
    data = _ps_json(script, timeout=15)
    items: list[dict[str, Any]] = []
    for row in _as_list(data):
        if not isinstance(row, dict):
            continue
        items.append({
            "name": _safe_str(row.get("Name")),
            "command": _safe_str(row.get("Command")),
            "scope": _safe_str(row.get("Scope")),
            "location": _safe_str(row.get("Location")),
            "reg_path": _safe_str(row.get("RegPath")),
        })
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
