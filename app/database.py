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
_UPDATE_ISSUE_SQL = (
    "UPDATE issues"
    " SET title = ?, description = ?, priority = ?, assignee_id = ?"
    " WHERE id = ?"
)
_UPDATE_STATUS_SQL = "UPDATE issues SET status = ? WHERE id = ?"
_INSERT_COMMENT_SQL = (
    "INSERT INTO comments (issue_id, author_id, text, created_at)"
    " VALUES (?, ?, ?, ?)"
)
_GET_COMMENT_SQL = (
    "SELECT id, issue_id, author_id, text, created_at"
    " FROM comments WHERE id = ?"
)
_LIST_COMMENTS_SQL = (
    "SELECT id, issue_id, author_id, text, created_at"
    " FROM comments WHERE issue_id = ? ORDER BY created_at, id"
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


def update_issue(conn, issue_id, title, description, priority, assignee_id):
    """Записує всі редаговані поля одним UPDATE: одна транзакція, атомарно."""
    with conn:
        conn.execute(
            _UPDATE_ISSUE_SQL,
            (title, description, priority, assignee_id, issue_id),
        )


def update_status(conn, issue_id, status):
    """Записує новий статус заявки."""
    with conn:
        conn.execute(_UPDATE_STATUS_SQL, (status, issue_id))


def insert_comment(conn, issue_id, author_id, text, created_at):
    """Зберігає коментар до наявної заявки й повертає його id."""
    with conn:
        cur = conn.execute(
            _INSERT_COMMENT_SQL, (issue_id, author_id, text, created_at)
        )
    return cur.lastrowid


def get_comment(conn, comment_id):
    """Повертає коментар як dict або None."""
    row = conn.execute(_GET_COMMENT_SQL, (comment_id,)).fetchone()
    return dict(row) if row else None


def list_comments(conn, issue_id):
    """Коментарі заявки: created_at за зростанням, за однакового часу id (D-03)."""
    rows = conn.execute(_LIST_COMMENTS_SQL, (issue_id,)).fetchall()
    return [dict(r) for r in rows]