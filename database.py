"""
database.py - Lightweight SQLite storage for device check history.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent / "monitoring.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ip TEXT NOT NULL,
            device_type TEXT,
            is_up INTEGER NOT NULL,
            latency_ms REAL,
            checked_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_checks_name ON checks(name)")
    conn.commit()
    conn.close()


def record_check(name: str, ip: str, device_type: str, is_up: bool, latency_ms: Optional[float]):
    conn = get_connection()
    conn.execute(
        "INSERT INTO checks (name, ip, device_type, is_up, latency_ms, checked_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, ip, device_type, int(is_up), latency_ms, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_latest_status():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT c.name, c.ip, c.device_type, c.is_up, c.latency_ms, c.checked_at
        FROM checks c
        WHERE c.id IN (SELECT MAX(id) FROM checks GROUP BY name)
        ORDER BY c.name
        """
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_history(name: str, limit: int = 100):
    conn = get_connection()
    rows = conn.execute(
        "SELECT name, ip, is_up, latency_ms, checked_at FROM checks "
        "WHERE name = ? ORDER BY id DESC LIMIT ?",
        (name, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_summary():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT name,
               COUNT(*) AS total_checks,
               SUM(is_up) AS up_checks,
               AVG(CASE WHEN is_up = 1 THEN latency_ms END) AS avg_latency_ms
        FROM checks
        GROUP BY name
        """
    ).fetchall()
    conn.close()
    summary = []
    for row in rows:
        total = row["total_checks"]
        up = row["up_checks"] or 0
        summary.append(
            {
                "name": row["name"],
                "total_checks": total,
                "uptime_pct": round((up / total) * 100, 2) if total else 0,
                "avg_latency_ms": round(row["avg_latency_ms"], 2) if row["avg_latency_ms"] else None,
            }
        )
    return summary
