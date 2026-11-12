"""Бізнес-правила зрізів A, B і C: заявки, статуси, коментарі."""

from contextlib import contextmanager
from datetime import datetime, timezone

from app import database
from app.schemas import (
    ApiValidationError,
    CommentCreate,
    IssueCreate,
    StatusChange,
    validate_body,
    validate_patch,
)

_MAX_SQLITE_INT = 2**63 - 1

# Маршрут передає цей маркер, коли тіло запиту не є коректним JSON.
# Сервіс перетворює його на помилку валідації після перевірок 404 і 409.
INVALID_JSON = object()

# Матриця переходів (requirements.md, «Життєвий цикл заявки»).
# Повтор поточного статусу — успіх без змін (D-07).
_TRANSITIONS = {
    "OPEN": {"OPEN", "IN_PROGRESS", "CLOSED"},
    "IN_PROGRESS": {"IN_PROGRESS", "CLOSED"},
    "CLOSED": {"CLOSED"},
}


class NotFoundError(Exception):
    """Заявку не знайдено (також для некоректного id у шляху, D-10)."""


class ConflictError(Exception):
    """Операція суперечить стану заявки."""


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


def _load_issue(conn, raw_id):
    """Повертає заявку або кидає NotFoundError (перший крок усіх перевірок)."""
    issue_id = _parse_issue_id(raw_id)
    if issue_id is None:
        raise _not_found(raw_id)
    issue = database.get_issue(conn, issue_id)
    if issue is None:
        raise _not_found(raw_id)
    return issue


def _reject_invalid_json(data):
    if data is INVALID_JSON:
        raise ApiValidationError(
            [
                {
                    "field": "body",
                    "reason": "тіло запиту має бути коректним JSON-об'єктом",
                }
            ]
        )


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


def update_issue(db_path, raw_id, data):
    """PATCH /issues/{id}: 404 → 409 → 422 → застосування змін (D-01, D-08)."""
    with _connection(db_path) as conn:
        issue = _load_issue(conn, raw_id)
        if issue["status"] == "CLOSED":
            raise ConflictError("Заявка закрита, її дані не можна змінювати")
        _reject_invalid_json(data)
        payload = validate_patch(data)
        # Змінюються лише передані поля; відсутнє поле відрізняється від null.
        changes = {name: getattr(payload, name) for name in payload.model_fields_set}
        merged = {**issue, **changes}
        database.update_issue(
            conn,
            issue["id"],
            merged["title"],
            merged["description"],
            merged["priority"],
            merged["assignee_id"],
        )
        return database.get_issue(conn, issue["id"])


def change_status(db_path, raw_id, data):
    """PATCH /issues/{id}/status: 404 → 422 (значення статусу) → 409 (перехід)."""
    with _connection(db_path) as conn:
        issue = _load_issue(conn, raw_id)
        _reject_invalid_json(data)
        target = validate_body(StatusChange, data).status
        current = issue["status"]
        if target == current:
            return issue
        if target not in _TRANSITIONS[current]:
            raise ConflictError(
                f"Перехід зі статусу {current} у статус {target} заборонений"
            )
        database.update_status(conn, issue["id"], target)
        return database.get_issue(conn, issue["id"])


def create_comment(db_path, raw_id, data):
    """POST /issues/{id}/comments: 404 → 422 → створення.

    Статус заявки не перевіряється: коментувати можна й закриту (AC-06.2).
    """
    with _connection(db_path) as conn:
        issue = _load_issue(conn, raw_id)
        _reject_invalid_json(data)
        payload = validate_body(CommentCreate, data)
        comment_id = database.insert_comment(
            conn,
            issue["id"],
            payload.author_id,
            payload.text,
            _now(),
        )
        return database.get_comment(conn, comment_id)


def list_comments(db_path, raw_id):
    """GET /issues/{id}/comments: 404, якщо заявки немає; інакше список (може бути порожнім)."""
    with _connection(db_path) as conn:
        issue = _load_issue(conn, raw_id)
        return database.list_comments(conn, issue["id"])