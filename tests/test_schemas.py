import pytest

from app.schemas import (
    ApiValidationError,
    CommentCreate,
    IssueCreate,
    StatusChange,
    validate_body,
    validate_patch,
)


def fields(exc):
    return [d["field"] for d in exc.value.details]


def test_issue_create_defaults_and_trim():
    issue = validate_body(IssueCreate, {"title": "  Помилка входу  "})
    assert issue.title == "Помилка входу"
    assert issue.description == ""
    assert issue.priority == "medium"


@pytest.mark.parametrize(
    ("title", "ok"),
    [("ab", False), ("  ab  ", False), ("abc", True), ("x" * 120, True), ("x" * 121, False)],
)
def test_issue_create_title_bounds(title, ok):
    if ok:
        assert validate_body(IssueCreate, {"title": title}).title == title.strip()
    else:
        with pytest.raises(ApiValidationError) as exc:
            validate_body(IssueCreate, {"title": title})
        assert fields(exc) == ["title"]


@pytest.mark.parametrize(
    "body",
    [
        {"title": "abc", "status": "OPEN"},
        {"title": "abc", "assignee_id": 1},
        {"title": "abc", "id": 5},
        {"title": "abc", "created_at": "2026-01-01T00:00:00Z"},
        {"title": "abc", "priority": "High"},
        {"title": "abc", "priority": "urgent"},
        {"title": 123},
        {"title": "abc", "description": "x" * 2001},
        {},
    ],
)
def test_issue_create_rejects(body):
    with pytest.raises(ApiValidationError):
        validate_body(IssueCreate, body)


def test_description_allows_empty_and_2000():
    assert validate_body(IssueCreate, {"title": "abc", "description": ""})
    assert validate_body(IssueCreate, {"title": "abc", "description": "x" * 2000})


@pytest.mark.parametrize("body", [[], "text", 5, None])
def test_body_must_be_object(body):
    with pytest.raises(ApiValidationError) as exc:
        validate_body(IssueCreate, body)
    assert fields(exc) == ["body"]


def test_patch_absent_vs_null():
    only_priority = validate_patch({"priority": "high"})
    assert only_priority.model_fields_set == {"priority"}
    clear = validate_patch({"assignee_id": None})
    assert clear.model_fields_set == {"assignee_id"}
    assert clear.assignee_id is None


@pytest.mark.parametrize("field", ["title", "description", "priority"])
def test_patch_null_forbidden(field):
    with pytest.raises(ApiValidationError) as exc:
        validate_patch({field: None})
    assert fields(exc) == [field]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"status": "OPEN"},
        {"id": 1},
        {"created_at": "x"},
        {"foo": 1},
        {"assignee_id": 3},
        {"assignee_id": "1"},
        {"assignee_id": True},
        {"title": 5},
        {"title": "ab"},
        {"description": "x" * 2001},
    ],
)
def test_patch_rejects(body):
    with pytest.raises(ApiValidationError):
        validate_patch(body)


def test_patch_collects_all_errors():
    with pytest.raises(ApiValidationError) as exc:
        validate_patch({"priority": "high", "title": "ab"})
    assert fields(exc) == ["title"]


@pytest.mark.parametrize("body", [{"status": "DONE"}, {"status": None}, {}, {"status": "OPEN", "x": 1}])
def test_status_rejects(body):
    with pytest.raises(ApiValidationError):
        validate_body(StatusChange, body)


@pytest.mark.parametrize("status", ["OPEN", "IN_PROGRESS", "CLOSED"])
def test_status_accepts(status):
    assert validate_body(StatusChange, {"status": status}).status == status


@pytest.mark.parametrize(
    "body",
    [
        {"author_id": 3, "text": "hi"},
        {"author_id": "1", "text": "hi"},
        {"author_id": 1, "text": ""},
        {"author_id": 1, "text": "   "},
        {"author_id": 1, "text": "x" * 1001},
        {"author_id": 1},
        {"text": "hi"},
        {"author_id": 1, "text": "hi", "issue_id": 1},
    ],
)
def test_comment_rejects(body):
    with pytest.raises(ApiValidationError):
        validate_body(CommentCreate, body)


def test_comment_bounds_and_trim():
    assert validate_body(CommentCreate, {"author_id": 2, "text": " a "}).text == "a"
    assert validate_body(CommentCreate, {"author_id": 1, "text": "x" * 1000})