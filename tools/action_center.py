from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class ActionCenter:
    def __init__(self, database_path: Path = Path("data/friday_actions.db")) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS actions (id INTEGER PRIMARY KEY, title TEXT NOT NULL, details TEXT NOT NULL DEFAULT '', due_at TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'Friday', status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )

    def add_action(self, title: str, details: str = "", due_at: str = "", source: str = "Friday") -> dict[str, Any]:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Action title is required.")
        now = datetime.now().astimezone().isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO actions(title, details, due_at, source, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'pending', ?, ?)",
                (clean_title, details.strip(), due_at.strip(), source.strip() or "Friday", now, now),
            )
            action_id = cursor.lastrowid
        return {"id": action_id, "title": clean_title, "status": "pending"}

    def list_actions(self, status: str = "pending", limit: int = 50) -> list[dict[str, Any]]:
        clean_status = status.strip().lower()
        if clean_status not in {"pending", "completed", "dismissed", "all"}:
            raise ValueError("Status must be pending, completed, dismissed, or all.")
        where = "" if clean_status == "all" else "WHERE status = ?"
        parameters = () if clean_status == "all" else (clean_status,)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT id, title, details, due_at, source, status, created_at, updated_at FROM actions {where} ORDER BY CASE WHEN due_at = '' THEN 1 ELSE 0 END, due_at, id DESC LIMIT ?",
                (*parameters, max(1, min(int(limit), 200))),
            ).fetchall()
        return [dict(row) for row in rows]

    def complete_action(self, action_id: int) -> dict[str, Any]:
        return self._set_status(action_id, "completed")

    def dismiss_action(self, action_id: int) -> dict[str, Any]:
        return self._set_status(action_id, "dismissed")

    def _set_status(self, action_id: int, status: str) -> dict[str, Any]:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE actions SET status = ?, updated_at = ? WHERE id = ?",
                (status, datetime.now().astimezone().isoformat(), int(action_id)),
            )
        if not cursor.rowcount:
            raise ValueError(f"Action {action_id} was not found.")
        return {"id": int(action_id), "status": status}

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection
