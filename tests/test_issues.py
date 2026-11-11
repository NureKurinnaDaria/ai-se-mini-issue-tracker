import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def create(client, **body):
    return client.post("/issues", json=body)


def assert_validation_error(response, field):
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["type"] == "validation_error"
    fields = [d["field"] for d in error["details"]]
    assert field in fields
    assert all(d["reason"] for d in error["details"])


# ---------- T01: створення з мінімальним тілом (AC-01.1) ----------


def test_t01_ac_01_1_create_with_minimal_body(client):
    response = create(client, title="Помилка входу")

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["title"] == "Помилка входу"
    assert body["description"] == ""
    assert body["status"] == "OPEN"
    assert body["priority"] == "medium"
    assert body["assignee_id"] is None
    assert TIMESTAMP.match(body["created_at"])


def test_t01_ac_01_1_create_with_description_and_priority(client):
    response = create(
        client, title="Помилка входу", description="Деталі", priority="high"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["description"] == "Деталі"
    assert body["priority"] == "high"
    assert body["status"] == "OPEN"


# ---------- T02: межі title після trim (AC-01.2, AC-01.3, D-04) ----------


@pytest.mark.parametrize(
    ("title", "expected_status", "expected_title"),
    [
        pytest.param("ab", 422, None, id="len2"),
        pytest.param("abc", 201, "abc", id="len3"),
        pytest.param("a" * 120, 201, "a" * 120, id="len120"),
        pytest.param("a" * 121, 422, None, id="len121"),
        pytest.param("  ab  ", 422, None, id="len2-padded"),
        pytest.param("  abc  ", 201, "abc", id="len3-padded-trimmed"),
        pytest.param(" " + "a" * 120 + " ", 201, "a" * 120, id="len120-padded"),
        pytest.param(" " + "a" * 121 + " ", 422, None, id="len121-padded"),
        pytest.param("   ", 422, None, id="only-spaces"),
    ],
)
def test_t02_ac_01_2_ac_01_3_title_bounds_after_trim(
    client, title, expected_status, expected_title
):
    response = create(client, title=title)

    assert response.status_code == expected_status
    if expected_status == 201:
        assert response.json()["title"] == expected_title
        assert client.get("/issues").json() == [response.json()]
    else:
        assert_validation_error(response, "title")
        assert client.get("/issues").json() == []


def test_t02_ac_01_3_missing_title_is_validation_error(client):
    response = create(client)

    assert_validation_error(response, "title")
    assert client.get("/issues").json() == []


def test_t02_ac_01_3_non_string_title_is_validation_error(client):
    response = create(client, title=123)

    assert_validation_error(response, "title")
    assert client.get("/issues").json() == []


# ---------- T03: список і деталі, 404 (AC-02.2, AC-02.4, D-03, D-10) ----------


def test_t03_ac_02_2_get_issue_matches_created(client):
    created = create(client, title="Помилка входу", priority="low").json()

    response = client.get(f"/issues/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_t03_list_matches_created_in_creation_order(client):
    created = [create(client, title=f"Заявка {i}").json() for i in range(3)]

    response = client.get("/issues")

    assert response.status_code == 200
    assert response.json() == created
    ids = [issue["id"] for issue in response.json()]
    assert ids == sorted(ids)


def test_t03_list_is_empty_array_when_no_issues(client):
    response = client.get("/issues")

    assert response.status_code == 200
    assert response.json() == []


def test_t03_ac_02_4_unknown_id_is_not_found(client):
    response = client.get("/issues/99")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"type": "not_found", "message": "Заявку з id 99 не знайдено"}
    }


@pytest.mark.parametrize("bad_id", ["abc", "0", "-1", "1.5", "99999999999999999999"])
def test_t03_d_10_invalid_id_is_not_found(client, bad_id):
    create(client, title="Помилка входу")

    response = client.get(f"/issues/{bad_id}")

    assert response.status_code == 404
    assert response.json()["error"]["type"] == "not_found"


# ---------- T13: збереження між запусками (AC-07.1) ----------


def test_t13_ac_07_1_issue_survives_app_restart(db_path):
    with TestClient(create_app(db_path)) as first:
        created = create(first, title="Помилка входу", priority="high").json()

    with TestClient(create_app(db_path)) as second:
        response = second.get(f"/issues/{created['id']}")
        assert response.status_code == 200
        assert response.json() == created
        assert second.get("/issues").json() == [created]


# ---------- AC-07.2 та додаткові правила контракту 3.3 ----------


@pytest.mark.parametrize("priority", ["High", "urgent"])
def test_ac_07_2_invalid_priority_is_rejected(client, priority):
    response = create(client, title="Помилка входу", priority=priority)

    assert_validation_error(response, "priority")
    assert client.get("/issues").json() == []


@pytest.mark.parametrize(
    "extra",
    [{"assignee_id": 1}, {"status": "CLOSED"}, {"foo": "bar"}],
    ids=["assignee_id", "status", "unknown"],
)
def test_d_05_disallowed_fields_on_create_are_rejected(client, extra):
    response = create(client, title="Помилка входу", **extra)

    assert_validation_error(response, next(iter(extra)))
    assert client.get("/issues").json() == []


def test_contract_3_3_description_over_2000_is_rejected(client):
    response = create(client, title="Помилка входу", description="a" * 2001)

    assert_validation_error(response, "description")
    assert client.get("/issues").json() == []


def test_contract_3_3_non_object_body_is_validation_error(client):
    response = client.post("/issues", json=[])

    assert_validation_error(response, "body")


def test_contract_3_3_invalid_json_is_validation_error(client):
    response = client.post(
        "/issues",
        content="{не json",
        headers={"Content-Type": "application/json"},
    )

    assert_validation_error(response, "body")
    assert client.get("/issues").json() == []