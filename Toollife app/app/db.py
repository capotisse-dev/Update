# app/db.py
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional

from .config import DB_PATH


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    schema = """
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        line TEXT NOT NULL DEFAULT 'Both',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_number TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL DEFAULT '',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS part_lines (
        part_id INTEGER NOT NULL,
        line_id INTEGER NOT NULL,
        PRIMARY KEY(part_id, line_id),
        FOREIGN KEY(part_id) REFERENCES parts(id) ON DELETE CASCADE,
        FOREIGN KEY(line_id) REFERENCES lines(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS tools (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tool_num TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL DEFAULT '',
        unit_cost REAL NOT NULL DEFAULT 0.0,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS part_costs (
        part_id INTEGER NOT NULL UNIQUE,
        scrap_cost REAL NOT NULL DEFAULT 0.0,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY(part_id) REFERENCES parts(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_parts_active ON parts(is_active);
    CREATE INDEX IF NOT EXISTS idx_tools_active ON tools(is_active);
    """
    with connect() as conn:
        conn.executescript(schema)
        conn.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version','1')")


def seed_default_users(default_users: Dict[str, Dict[str, Any]]) -> None:
    with connect() as conn:
        for username, u in default_users.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO users(username, password, role, name, line)
                VALUES(?,?,?,?,?)
                """,
                (
                    username,
                    u.get("password", ""),
                    u.get("role", "User"),
                    u.get("name", ""),
                    u.get("line", "Both"),
                ),
            )


def ensure_lines(names: Iterable[str]) -> None:
    with connect() as conn:
        for n in names:
            n = (n or "").strip()
            if n:
                conn.execute("INSERT OR IGNORE INTO lines(name) VALUES(?)", (n,))


def upsert_part(part_number: str, name: str = "", lines: Optional[List[str]] = None) -> None:
    lines = lines or []
    with connect() as conn:
        # ensure lines
        for ln in lines:
            ln = (ln or "").strip()
            if ln:
                conn.execute("INSERT OR IGNORE INTO lines(name) VALUES(?)", (ln,))

        conn.execute(
            """
            INSERT INTO parts(part_number, name, is_active)
            VALUES(?, ?, 1)
            ON CONFLICT(part_number) DO UPDATE SET
              name=excluded.name,
              updated_at=datetime('now')
            """,
            (part_number, name),
        )

        part_id = conn.execute(
            "SELECT id FROM parts WHERE part_number=?",
            (part_number,),
        ).fetchone()["id"]

        # rewrite mappings
        conn.execute("DELETE FROM part_lines WHERE part_id=?", (part_id,))
        for ln in lines:
            ln = (ln or "").strip()
            if not ln:
                continue
            line_id = conn.execute("SELECT id FROM lines WHERE name=?", (ln,)).fetchone()["id"]
            conn.execute("INSERT OR IGNORE INTO part_lines(part_id,line_id) VALUES(?,?)", (part_id, line_id))


def upsert_tool(tool_num: str, name: str = "", unit_cost: float = 0.0) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO tools(tool_num, name, unit_cost, is_active)
            VALUES(?, ?, ?, 1)
            ON CONFLICT(tool_num) DO UPDATE SET
              name=excluded.name,
              unit_cost=excluded.unit_cost,
              updated_at=datetime('now')
            """,
            (tool_num, name, float(unit_cost)),
        )


def set_scrap_cost(part_number: str, scrap_cost: float) -> None:
    with connect() as conn:
        row = conn.execute("SELECT id FROM parts WHERE part_number=?", (part_number,)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO parts(part_number, name, is_active) VALUES(?, '', 1)",
                (part_number,),
            )
            row = conn.execute("SELECT id FROM parts WHERE part_number=?", (part_number,)).fetchone()

        part_id = row["id"]
        conn.execute(
            """
            INSERT INTO part_costs(part_id, scrap_cost)
            VALUES(?, ?)
            ON CONFLICT(part_id) DO UPDATE SET
              scrap_cost=excluded.scrap_cost,
              updated_at=datetime('now')
            """,
            (part_id, float(scrap_cost)),
        )
def list_parts_with_lines():
    with connect() as conn:
        parts = conn.execute(
            "SELECT id, part_number, name FROM parts WHERE is_active=1 ORDER BY part_number"
        ).fetchall()

        out = []
        for p in parts:
            lines = conn.execute(
                """
                SELECT l.name
                FROM part_lines pl
                JOIN lines l ON l.id = pl.line_id
                WHERE pl.part_id=?
                ORDER BY l.name
                """,
                (p["id"],),
            ).fetchall()
            out.append({
                "id": p["id"],
                "part_number": p["part_number"],
                "name": p["name"],
                "lines": [r["name"] for r in lines],
            })
        return out


def list_tools_simple():
    with connect() as conn:
        rows = conn.execute(
            "SELECT tool_num, name, unit_cost FROM tools WHERE is_active=1 ORDER BY tool_num"
        ).fetchall()
        return [dict(r) for r in rows]


def get_scrap_costs_simple():
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT p.part_number, pc.scrap_cost
            FROM part_costs pc
            JOIN parts p ON p.id = pc.part_id
            ORDER BY p.part_number
            """
        ).fetchall()
        return {r["part_number"]: float(r["scrap_cost"]) for r in rows}
