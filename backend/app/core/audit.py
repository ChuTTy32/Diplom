"""
SQLite аудит-лог инцидентов.
Отдельная БД — не TimescaleDB, чтобы аудит был изолирован от основных данных.
Append-only: записи никогда не удаляются и не изменяются.
"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional

SQLITE_PATH = os.getenv("SQLITE_PATH", "/app/data/audit.db")


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                time        TEXT    NOT NULL,
                severity    TEXT    NOT NULL,  -- 'critical' | 'warning'
                trigger_file TEXT,
                entropy     REAL,
                alert_count INTEGER,
                action_taken TEXT,             -- 'lockdown' | 'emergency_backup' | 'logged'
                host        TEXT,
                resolved    INTEGER DEFAULT 0  -- 0/1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                time    TEXT NOT NULL,
                event   TEXT NOT NULL,
                detail  TEXT,
                host    TEXT
            )
        """)
        conn.commit()


def log_incident(
    severity: str,
    trigger_file: str,
    entropy: float,
    alert_count: int,
    action_taken: str,
    host: str,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO incidents
               (time, severity, trigger_file, entropy, alert_count, action_taken, host)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                severity,
                trigger_file,
                entropy,
                alert_count,
                action_taken,
                host,
            ),
        )
        conn.commit()
        return cur.lastrowid


def log_audit(event: str, detail: str = "", host: str = "system"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (time, event, detail, host) VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), event, detail, host),
        )
        conn.commit()


def get_incidents(limit: int = 50) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_audit_log(limit: int = 100) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
