"""SQLite persistence for scan history."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .score import HealthSummary

_DB_PATH = Path.home() / ".pc_doctor" / "history.db"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(_DB_PATH)
    c.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            ts      REAL    NOT NULL,
            score   INTEGER NOT NULL,
            kind    TEXT    NOT NULL DEFAULT 'full',
            payload TEXT    NOT NULL
        )
    """)
    c.commit()
    return c


def save(summary: HealthSummary, kind: str = "full") -> None:
    payload = json.dumps({
        "score": summary.score,
        "severity": summary.severity.value,
        "headline": summary.headline,
        "results": [r.to_dict() for r in summary.results],
        "duration_ms": summary.duration_ms,
    })
    with _conn() as c:
        c.execute(
            "INSERT INTO scans (ts, score, kind, payload) VALUES (?,?,?,?)",
            (summary.finished_at, summary.score, kind, payload),
        )


def load_recent(limit: int = 30) -> list[dict]:
    try:
        c = _conn()
        rows = c.execute(
            "SELECT id, ts, score, kind, payload FROM scans ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"id": r[0], "ts": r[1], "score": r[2], "kind": r[3], **json.loads(r[4])}
            for r in rows
        ]
    except sqlite3.Error:
        return []


def delete_old(keep_days: int = 30) -> int:
    cutoff = time.time() - keep_days * 86400
    try:
        with _conn() as c:
            c.execute("DELETE FROM scans WHERE ts < ?", (cutoff,))
            return c.total_changes
    except sqlite3.Error:
        return 0
