"""HTTP-шар зрізу A: маршрути перетворюють результати сервісу на відповіді."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import service
from app.schemas import ApiValidationError, IssueOut

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