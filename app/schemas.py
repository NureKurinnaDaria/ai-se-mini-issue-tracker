"""Схеми запитів і відповідей. Правила полів: docs/requirements.md, «Модель даних»."""

from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    StringConstraints,
    ValidationError,
)
from pydantic_core import PydanticCustomError

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)
]
Description = Annotated[str, StringConstraints(max_length=2000)]
Priority = Literal["low", "medium", "high"]
Status = Literal["OPEN", "IN_PROGRESS", "CLOSED"]
CommentText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]


def _known_user(value: int) -> int:
    if value not in (1, 2):
        raise PydanticCustomError("unknown_user", "допустимі значення: 1 або 2")
    return value


UserId = Annotated[int, AfterValidator(_known_user)]


class StrictInput(BaseModel):
    """Спільні правила входу: без невідомих полів, без неявного перетворення типів."""

    model_config = ConfigDict(extra="forbid", strict=True)


class IssueCreate(StrictInput):
    title: Title
    description: Description = ""
    priority: Priority = "medium"


class IssueUpdate(StrictInput):
    # Типи без None: явний null для цих полів дає помилку валідації.
    # Відсутнє поле відрізняється від переданого через model_fields_set.
    title: Title = None
    description: Description = None
    priority: Priority = None
    assignee_id: UserId | None = None


class StatusChange(StrictInput):
    status: Status


class CommentCreate(StrictInput):
    author_id: UserId
    text: CommentText


class UserOut(BaseModel):
    id: int
    name: str


class IssueOut(BaseModel):
    id: int
    title: str
    description: str
    status: Status
    priority: Priority
    assignee_id: int | None
    created_at: str


class CommentOut(BaseModel):
    id: int
    issue_id: int
    author_id: int
    text: str
    created_at: str


class ApiValidationError(Exception):
    """Помилка валідації: details = [{"field": ..., "reason": ...}]."""

    def __init__(self, details):
        super().__init__("Запит містить некоректні дані")
        self.details = details


_LENGTH_REASON = {
    "title": "довжина після видалення крайніх пробілів має бути від 3 до 120 символів",
    "description": "довжина має бути не більше 2000 символів",
    "text": "довжина після видалення крайніх пробілів має бути від 1 до 1000 символів",
}
_ALLOWED = {
    "priority": "low, medium, high",
    "status": "OPEN, IN_PROGRESS, CLOSED",
}


def _reason(err):
    kind = err["type"]
    field = str(err["loc"][-1]) if err["loc"] else "body"
    if kind in ("string_too_short", "string_too_long") and field in _LENGTH_REASON:
        return _LENGTH_REASON[field]
    if kind == "missing":
        return "поле обов'язкове"
    if kind == "extra_forbidden":
        return "поле недозволене або невідоме"
    if kind == "string_type":
        return "значення має бути рядком"
    if kind in ("int_type", "int_parsing"):
        return "значення має бути цілим числом"
    if kind == "literal_error" and field in _ALLOWED:
        return f"допустимі значення: {_ALLOWED[field]}"
    return err["msg"]


def validate_body(model, data):
    """Перевіряє тіло запиту схемою; при помилці кидає ApiValidationError."""
    if not isinstance(data, dict):
        raise ApiValidationError(
            [{"field": "body", "reason": "тіло запиту має бути JSON-об'єктом"}]
        )
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        details = [
            {
                "field": ".".join(str(p) for p in err["loc"]) or "body",
                "reason": _reason(err),
            }
            for err in exc.errors()
        ]
        raise ApiValidationError(details) from None


def validate_patch(data):
    """PATCH: порожнє тіло — помилка валідації (D-08), далі — схема."""
    if isinstance(data, dict) and not data:
        raise ApiValidationError(
            [{"field": "body", "reason": "потрібно передати хоча б одне поле"}]
        )
    return validate_body(IssueUpdate, data)