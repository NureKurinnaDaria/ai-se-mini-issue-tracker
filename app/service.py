"""Бізнес-правила зрізу A: створення й читання заявок."""

from contextlib import contextmanager
from datetime import datetime, timezone

from app import database
from app.schemas import IssueCreate, validate_body

_MAX_SQLITE_INT = 2**63 - 1


class NotFoundError(Exception):
    """Заявку не знайдено (також для некоректного id у шляху, D-10)."""


@contextmanager
def _connection(db_path):
    conn = database.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def _now():
    """Час у UTC, ISO 8601 із суфіксом Z (D-11)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_issue_id(raw):
    """Додатне ціле з рядка шляху або None (D-10)."""
    if isinstance(raw, str) and raw.isascii() and raw.isdigit():
        value = int(raw)
        if 0 < value <= _MAX_SQLITE_INT:
            return value
    return None


def _not_found(raw_id):
    return NotFoundError(f"Заявку з id {raw_id} не знайдено")


def create_issue(db_path, data):
    payload = validate_body(IssueCreate, data)
    with _connection(db_path) as conn:
        issue_id = database.insert_issue(
            conn,
            payload.title,
            payload.description,
            payload.priority,
            _now(),
        )
        return database.get_issue(conn, issue_id)


def get_issue(db_path, raw_id):
    issue_id = _parse_issue_id(raw_id)
    if issue_id is None:
        raise _not_found(raw_id)
    with _connection(db_path) as conn:
        issue = database.get_issue(conn, issue_id)
    if issue is None:
        raise _not_found(raw_id)
    return issue


def list_issues(db_path):
    with _connection(db_path) as conn:
        return database.list_issues(conn)