"""Process baseline — track which executables we've seen on this machine.

Each scan, we read the baseline (set of trusted process keys), diff the
current running processes, and surface anything new as a 'first time seen'
warning so the user can decide whether to terminate it.

A process is keyed by `<name.lower()>|<exe.lower()>` so renaming an EXE on a
new path doesn't whitelist it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_BASELINE_PATH = Path.home() / ".pc_doctor" / "process_baseline.json"
_MAX_ENTRIES = 5000  # safety cap


def _key(name: str, exe: str) -> str:
    return f"{(name or '').strip().lower()}|{(exe or '').strip().lower()}"


def load() -> dict[str, Any]:
    """Returns {trusted: set[str], first_run: bool}."""
    if not _BASELINE_PATH.exists():
        return {"trusted": set(), "first_run": True}
    try:
        with _BASELINE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        trusted = set(data.get("trusted", []))
        return {"trusted": trusted, "first_run": False}
    except (json.JSONDecodeError, OSError):
        return {"trusted": set(), "first_run": True}


def save(trusted: set[str]) -> None:
    """Persist the trusted set, capped to the most recent N entries."""
    if len(trusted) > _MAX_ENTRIES:
        # Keep the first N — order is not meaningful but this prevents
        # the file from growing unbounded.
        trusted = set(list(trusted)[:_MAX_ENTRIES])
    try:
        _BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _BASELINE_PATH.open("w", encoding="utf-8") as f:
            json.dump({"trusted": sorted(trusted)}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def diff(current: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    """Returns (new_processes, is_first_run).

    On first run we don't surface anything — we just record everything as
    trusted so the very next scan can spot real changes.
    """
    state = load()
    trusted: set[str] = state["trusted"]
    first_run = state["first_run"]

    keys_now = set()
    new_procs: list[dict[str, Any]] = []
    for p in current:
        k = _key(p.get("name", ""), p.get("exe", ""))
        keys_now.add(k)
        if first_run:
            continue
        if k not in trusted:
            new_procs.append(p)

    if first_run:
        save(keys_now)
        return [], True

    # Re-save merged set so trusted grows over time
    save(trusted | keys_now)
    return new_procs, False


def trust(name: str, exe: str) -> None:
    """Add a single process key to the trusted baseline."""
    state = load()
    trusted: set[str] = state["trusted"]
    trusted.add(_key(name, exe))
    save(trusted)


def reset() -> None:
    """Wipe the baseline (next scan is treated as a fresh first-run)."""
    try:
        if _BASELINE_PATH.exists():
            _BASELINE_PATH.unlink()
    except OSError:
        pass
