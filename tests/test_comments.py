import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

CREATED_AT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def _make_issue(client, title="Помилка входу"):
    response = client.post("/issues", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


def _close_issue(client, issue_id):
    response = client.patch(f"/issues/{issue_id}/status", json={"status": "CLOSED"})
    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"


def _add_comment(client, issue_id, author_id=1, text="Відтворюється на версії 2.1"):
    return client.post(
        f"/issues/{issue_id}/comments",
        json={"author_id": author_id, "text": text},
    )


def _error_fields(response):
    return [d["field"] for d in response.json()["error"]["details"]]


# --- T11 / AC-06.1: валідний коментар ---


def test_create_comment_returns_201_and_appears_in_list(client):
    issue_id = _make_issue(client)

    response = _add_comment(client, issue_id, author_id=1, text="Відтворюється")

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["issue_id"] == issue_id
    assert body["author_id"] == 1
    assert body["text"] == "Відтворюється"
    assert CREATED_AT.fullmatch(body["created_at"])

    listed = client.get(f"/issues/{issue_id}/comments")
    assert listed.status_code == 200
    assert listed.json() == [body]


def test_comment_text_is_trimmed_before_saving(client):
    issue_id = _make_issue(client)

    response = _add_comment(client, issue_id, text="   Привіт   ")

    assert response.status_code == 201
    assert response.json()["text"] == "Привіт"
    assert client.get(f"/issues/{issue_id}/comments").json()[0]["text"] == "Привіт"


# --- T12 / AC-06.2: коментар до закритої заявки ---


def test_comment_to_closed_issue_is_allowed(client):
    issue_id = _make_issue(client)
    _close_issue(client, issue_id)

    response = _add_comment(client, issue_id, author_id=2, text="Після закриття")

    assert response.status_code == 201
    assert response.json()["author_id"] == 2
    listed = client.get(f"/issues/{issue_id}/comments").json()
    assert [c["text"] for c in listed] == ["Після закриття"]


# --- AC-06.3: межі довжини тексту ---


def test_comment_text_of_1000_chars_is_accepted(client):
    issue_id = _make_issue(client)

    response = _add_comment(client, issue_id, text="а" * 1000)

    assert response.status_code == 201
    assert len(response.json()["text"]) == 1000


@pytest.mark.parametrize(
    "text",
    ["", "   ", "\t\n", "а" * 1001],
    ids=["empty", "spaces", "whitespace", "1001-chars"],
)
def test_invalid_comment_text_gives_422_and_nothing_is_saved(client, text):
    issue_id = _make_issue(client)

    response = _add_comment(client, issue_id, text=text)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["type"] == "validation_error"
    assert "text" in _error_fields(response)
    assert all(d["reason"] for d in error["details"])
    assert client.get(f"/issues/{issue_id}/comments").json() == []


# --- AC-06.5: невідомий автор ---


@pytest.mark.parametrize("author_id", [3, 0, -1])
def test_unknown_author_gives_422_with_reason(client, author_id):
    issue_id = _make_issue(client)

    response = _add_comment(client, issue_id, author_id=author_id)

    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert {
        "field": "author_id",
        "reason": "допустимі значення: 1 або 2",
    } in details
    assert client.get(f"/issues/{issue_id}/comments").json() == []


# --- Контракт 3.8: форма тіла ---


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"text": "Привіт"}, "author_id"),
        ({"author_id": 1}, "text"),
        ({"author_id": 1, "text": "Привіт", "foo": 1}, "foo"),
        ({"author_id": 1, "text": "Привіт", "issue_id": 1}, "issue_id"),
        ({"author_id": "1", "text": "Привіт"}, "author_id"),
        ({"author_id": None, "text": "Привіт"}, "author_id"),
        ({"author_id": 1, "text": 123}, "text"),
        ({"author_id": 1, "text": None}, "text"),
    ],
    ids=[
        "missing-author",
        "missing-text",
        "unknown-field",
        "issue-id-in-body",
        "author-as-string",
        "author-null",
        "text-as-number",
        "text-null",
    ],
)
def test_malformed_comment_body_gives_422(client, body, field):
    issue_id = _make_issue(client)

    response = client.post(f"/issues/{issue_id}/comments", json=body)

    assert response.status_code == 422
    assert field in _error_fields(response)
    assert client.get(f"/issues/{issue_id}/comments").json() == []


@pytest.mark.parametrize(
    "content",
    [b"not json", b"[1, 2]", b"42"],
    ids=["invalid-json", "array", "number"],
)
def test_non_object_body_gives_422(client, content):
    issue_id = _make_issue(client)

    response = client.post(
        f"/issues/{issue_id}/comments",
        content=content,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["type"] == "validation_error"
    assert client.get(f"/issues/{issue_id}/comments").json() == []


# --- T12 / AC-06.4: невідома заявка ---


def test_comment_to_unknown_issue_gives_404(client):
    response = _add_comment(client, 99)

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["type"] == "not_found"
    assert "99" in error["message"]


@pytest.mark.parametrize("raw_id", ["abc", "0", "-1", "99999999999999999999"])
def test_non_positive_or_non_numeric_issue_id_gives_404(client, raw_id):
    post = client.post(
        f"/issues/{raw_id}/comments", json={"author_id": 1, "text": "Привіт"}
    )
    get = client.get(f"/issues/{raw_id}/comments")

    assert post.status_code == 404
    assert post.json()["error"]["type"] == "not_found"
    assert get.status_code == 404
    assert get.json()["error"]["type"] == "not_found"


def test_unknown_issue_wins_over_invalid_body(client):
    invalid_body = client.post("/issues/99/comments", json={"author_id": 3, "text": ""})
    invalid_json = client.post(
        "/issues/99/comments",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )

    assert invalid_body.status_code == 404
    assert invalid_json.status_code == 404


def test_failed_comment_to_unknown_issue_is_not_saved(client):
    _add_comment(client, 99)
    issue_id = _make_issue(client)

    assert client.get(f"/issues/{issue_id}/comments").json() == []


# --- Контракт 3.9: GET ---


def test_list_comments_of_issue_without_comments_is_empty(client):
    issue_id = _make_issue(client)

    response = client.get(f"/issues/{issue_id}/comments")

    assert response.status_code == 200
    assert response.json() == []


def test_list_comments_of_unknown_issue_gives_404(client):
    response = client.get("/issues/99/comments")

    assert response.status_code == 404
    assert response.json()["error"]["type"] == "not_found"


def test_comments_are_ordered_by_creation_and_id(client):
    issue_id = _make_issue(client)
    texts = ["перший", "другий", "третій"]
    created_ids = [
        _add_comment(client, issue_id, author_id=1 + i % 2, text=text).json()["id"]
        for i, text in enumerate(texts)
    ]

    listed = client.get(f"/issues/{issue_id}/comments").json()

    assert [c["text"] for c in listed] == texts
    assert [c["id"] for c in listed] == created_ids
    assert created_ids == sorted(created_ids)


def test_comments_of_different_issues_are_not_mixed(client):
    first = _make_issue(client, "Перша заявка")
    second = _make_issue(client, "Друга заявка")
    _add_comment(client, first, text="до першої")
    _add_comment(client, second, text="до другої")
    _add_comment(client, first, text="ще до першої")

    first_list = client.get(f"/issues/{first}/comments").json()
    second_list = client.get(f"/issues/{second}/comments").json()

    assert [c["text"] for c in first_list] == ["до першої", "ще до першої"]
    assert all(c["issue_id"] == first for c in first_list)
    assert [c["text"] for c in second_list] == ["до другої"]
    assert second_list[0]["issue_id"] == second


# --- AC-07.1: збереження між запусками ---


def test_comment_persists_after_app_restart(db_path):
    with TestClient(create_app(db_path)) as first_run:
        issue_id = _make_issue(first_run)
        created = _add_comment(
            first_run, issue_id, author_id=2, text="Переживе перезапуск"
        )
        assert created.status_code == 201
        comment = created.json()

    with TestClient(create_app(db_path)) as second_run:
        response = second_run.get(f"/issues/{issue_id}/comments")

    assert response.status_code == 200
    assert response.json() == [comment]