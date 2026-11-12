"""HTTP-шар зрізів A, B і C: маршрути перетворюють результати сервісу на відповіді."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import service
from app.schemas import ApiValidationError, CommentOut, IssueOut

router = APIRouter()


def _error(status_code, error_type, message, details=None):
    body = {"type": error_type, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status_code, content={"error": body})


def _validation_error(details):
    return _error(
        422, "validation_error", "Запит містить некоректні дані", details
    )


async def _read_json(request):
    """Сире тіло; невалідний JSON → маркер, який перевірить сервіс."""
    try:
        return await request.json()
    except ValueError:
        return service.INVALID_JSON


def _respond(call):
    """Виконує операцію сервісу й перетворює помилки на відповіді (1.1, 1.2)."""
    try:
        return call()
    except service.NotFoundError as exc:
        return _error(404, "not_found", str(exc))
    except service.ConflictError as exc:
        return _error(409, "conflict", str(exc))
    except ApiValidationError as exc:
        return _validation_error(exc.details)


@router.post("/issues", status_code=201, response_model=IssueOut)
async def create_issue(request: Request):
    # Тіло читаємо сирим, щоб невалідний JSON теж дав 422 у форматі контракту.
    try:
        data = await request.json()
    except ValueError:
        return _validation_error(
            [{"field": "body", "reason": "тіло запиту має бути коректним JSON-об'єктом"}]
        )
    try:
        return service.create_issue(request.app.state.db_path, data)
    except ApiValidationError as exc:
        return _validation_error(exc.details)


@router.get("/issues", response_model=list[IssueOut])
def list_issues(request: Request):
    # Параметри status і priority у зрізі A не оголошені й ігноруються.
    return service.list_issues(request.app.state.db_path)


@router.get("/issues/{issue_id}", response_model=IssueOut)
def get_issue(issue_id: str, request: Request):
    # issue_id оголошено як str: abc і 0 мають давати 404, а не 422 (D-10).
    try:
        return service.get_issue(request.app.state.db_path, issue_id)
    except service.NotFoundError as exc:
        return _error(404, "not_found", str(exc))


@router.patch("/issues/{issue_id}", response_model=IssueOut)
async def update_issue(issue_id: str, request: Request):
    # Сире тіло йде в сервіс: порядок перевірок 404 → 409 → 422 (architecture.md).
    data = await _read_json(request)
    return _respond(
        lambda: service.update_issue(request.app.state.db_path, issue_id, data)
    )


@router.patch("/issues/{issue_id}/status", response_model=IssueOut)
async def change_status(issue_id: str, request: Request):
    data = await _read_json(request)
    return _respond(
        lambda: service.change_status(request.app.state.db_path, issue_id, data)
    )


@router.post(
    "/issues/{issue_id}/comments", status_code=201, response_model=CommentOut
)
async def create_comment(issue_id: str, request: Request):
    # Сире тіло йде в сервіс: 404 має пріоритет над некоректним тілом.
    data = await _read_json(request)
    return _respond(
        lambda: service.create_comment(request.app.state.db_path, issue_id, data)
    )


@router.get("/issues/{issue_id}/comments", response_model=list[CommentOut])
def list_comments(issue_id: str, request: Request):
    return _respond(
        lambda: service.list_comments(request.app.state.db_path, issue_id)
    )