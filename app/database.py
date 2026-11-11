import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = "data/app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN', 'IN_PROGRESS', 'CLOSED')),
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high')),
    assignee_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id INTEGER NOT NULL REFERENCES issues(id),
    author_id INTEGER NOT NULL REFERENCES users(id),
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

USERS = [(1, "Agent A"), (2, "Agent B")]

_GET_ISSUE_SQL = (
    "SELECT id, title, description, status, priority, assignee_id, created_at"
    " FROM issues WHERE id = ?"
)
_LIST_ISSUES_SQL = (
    "SELECT id, title, description, status, priority, assignee_id, created_at"
    " FROM issues ORDER BY created_at, id"
)


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        with conn:
            conn.executescript(SCHEMA)
            conn.executemany(
                "INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)", USERS
            )
    finally:
        conn.close()


def insert_issue(conn, title, description, priority, created_at):
    """Зберігає нову заявку (статус OPEN, без виконавця) і повертає її id."""
    with conn:
        cur = conn.execute(
            "INSERT INTO issues"
            " (title, description, status, priority, assignee_id, created_at)"
            " VALUES (?, ?, 'OPEN', ?, NULL, ?)",
            (title, description, priority, created_at),
        )
    return cur.lastrowid


def get_issue(conn, issue_id):
    """Повертає заявку як dict або None."""
    row = conn.execute(
        _GET_ISSUE_SQL, (issue_id,)
    ).fetchone()
    return dict(row) if row else None


def list_issues(conn):
    """Усі заявки: created_at за зростанням, за однакового часу id (D-03)."""
    rows = conn.execute(
        _LIST_ISSUES_SQL
    ).fetchall()
    return [dict(r) for r in rows]