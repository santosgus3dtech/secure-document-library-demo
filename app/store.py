from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY,
  filename TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  category TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'deleted')),
  uploaded_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY,
  actor_role TEXT NOT NULL,
  action TEXT NOT NULL,
  document_id INTEGER,
  details TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = str(path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


def add_document(connection: sqlite3.Connection, filename: str, title: str, category: str, size: int, actor: str) -> int:
    cursor = connection.execute(
        "INSERT INTO documents (filename, title, category, size_bytes, uploaded_by) VALUES (?, ?, ?, ?, ?)",
        (filename, title, category, size, actor),
    )
    document_id = int(cursor.lastrowid)
    connection.execute(
        "INSERT INTO audit_log (actor_role, action, document_id, details) VALUES (?, 'uploaded', ?, ?)",
        (actor, document_id, filename),
    )
    connection.commit()
    return document_id
