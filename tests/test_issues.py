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


# ======================= Зріз B: зміни й стани =======================

INVALID_JSON_BODY = "{не json"


def patch(client, issue_id, **body):
    return client.patch(f"/issues/{issue_id}", json=body)


def patch_raw(client, path, content):
    return client.patch(
        path, content=content, headers={"Content-Type": "application/json"}
    )


def set_status(client, issue_id, status):
    return client.patch(f"/issues/{issue_id}/status", json={"status": status})


def issue_in(client, state, **body):
    """Створює заявку й переводить її у потрібний стан дозволеними переходами."""
    body.setdefault("title", "Помилка входу")
    issue = create(client, **body).json()
    if state != "OPEN":
        assert set_status(client, issue["id"], state).status_code == 200
    return client.get(f"/issues/{issue['id']}").json()


def snapshot(client, issue_id):
    return client.get(f"/issues/{issue_id}").json()


def assert_error(response, status_code, error_type):
    assert response.status_code == status_code
    assert response.json()["error"]["type"] == error_type


# ---------- T07: частковий PATCH (AC-03.1, AC-03.2, AC-03.3, AC-03.6) ----------


@pytest.mark.parametrize("state", ["OPEN", "IN_PROGRESS"])
def test_t07_ac_03_1_partial_patch_keeps_absent_fields(client, state):
    issue = issue_in(client, state, description="Опис", priority="low")
    assert patch(client, issue["id"], assignee_id=2).status_code == 200
    before = snapshot(client, issue["id"])

    response = patch(client, issue["id"], priority="high")

    assert response.status_code == 200
    assert response.json() == {**before, "priority": "high"}
    assert snapshot(client, issue["id"]) == response.json()


def test_t07_ac_03_1_patch_can_clear_description_with_empty_string(client):
    issue = issue_in(client, "OPEN", description="Опис")

    response = patch(client, issue["id"], description="")

    assert response.status_code == 200
    assert response.json()["description"] == ""


def test_t07_patch_trims_title_before_validation(client):
    issue = issue_in(client, "OPEN")

    response = patch(client, issue["id"], title="  Нова назва  ")

    assert response.status_code == 200
    assert response.json()["title"] == "Нова назва"


@pytest.mark.parametrize(
    ("length", "expected_status"),
    [pytest.param(2000, 200, id="len2000"), pytest.param(2001, 422, id="len2001")],
)
def test_t07_ac_03_2_description_bounds(client, length, expected_status):
    issue = issue_in(client, "OPEN", description="Старий")

    response = patch(client, issue["id"], description="a" * length)

    assert response.status_code == expected_status
    if expected_status == 200:
        assert snapshot(client, issue["id"])["description"] == "a" * length
    else:
        assert_validation_error(response, "description")
        assert snapshot(client, issue["id"])["description"] == "Старий"


def test_t07_ac_03_3_invalid_field_rejects_whole_request(client):
    issue = issue_in(client, "OPEN", priority="low")
    before = snapshot(client, issue["id"])

    response = patch(client, issue["id"], priority="high", title="ab")

    assert_validation_error(response, "title")
    assert snapshot(client, issue["id"]) == before
    assert before["priority"] == "low"


@pytest.mark.parametrize("field", ["title", "description", "priority"])
def test_t07_ac_03_6_null_is_rejected_for_non_nullable_fields(client, field):
    issue = issue_in(client, "OPEN", description="Опис")
    before = snapshot(client, issue["id"])

    response = patch(client, issue["id"], **{field: None})

    assert_validation_error(response, field)
    assert snapshot(client, issue["id"]) == before


def test_t07_patch_with_same_value_is_success_without_changes(client):
    issue = issue_in(client, "OPEN", priority="high")

    response = patch(client, issue["id"], priority="high")

    assert response.status_code == 200
    assert response.json() == issue


def test_t07_patch_wrong_type_is_validation_error(client):
    issue = issue_in(client, "OPEN")

    response = patch(client, issue["id"], title=123)

    assert_validation_error(response, "title")
    assert snapshot(client, issue["id"]) == issue


# ---------- T08: виконавець (AC-05.1–AC-05.4) ----------


@pytest.mark.parametrize("state", ["OPEN", "IN_PROGRESS"])
def test_t08_ac_05_1_assign_known_user(client, state):
    issue = issue_in(client, state)

    response = patch(client, issue["id"], assignee_id=2)

    assert response.status_code == 200
    assert response.json() == {**issue, "assignee_id": 2}
    assert snapshot(client, issue["id"]) == response.json()


def test_t08_ac_05_2_null_removes_assignee(client):
    issue = issue_in(client, "OPEN")
    assert patch(client, issue["id"], assignee_id=1).status_code == 200

    response = patch(client, issue["id"], assignee_id=None)

    assert response.status_code == 200
    assert response.json()["assignee_id"] is None
    assert snapshot(client, issue["id"])["assignee_id"] is None


@pytest.mark.parametrize("value", [3, 0, "1"], ids=["id3", "id0", "string"])
def test_t08_ac_05_3_unknown_assignee_is_validation_error(client, value):
    issue = issue_in(client, "OPEN")
    assert patch(client, issue["id"], assignee_id=1).status_code == 200
    before = snapshot(client, issue["id"])

    response = patch(client, issue["id"], assignee_id=value)

    assert_validation_error(response, "assignee_id")
    assert snapshot(client, issue["id"]) == before


def test_t08_ac_05_4_closed_issue_rejects_assignee_change(client):
    issue = issue_in(client, "OPEN")
    assert patch(client, issue["id"], assignee_id=1).status_code == 200
    assert set_status(client, issue["id"], "CLOSED").status_code == 200
    before = snapshot(client, issue["id"])

    response = patch(client, issue["id"], assignee_id=2)

    assert_error(response, 409, "conflict")
    assert snapshot(client, issue["id"]) == before


# ---------- T09: дозволені переходи й повтор статусу (AC-04.1, 04.2, 04.5) ----------


def test_t09_ac_04_1_open_to_in_progress_to_closed(client):
    issue = issue_in(client, "OPEN")

    first = set_status(client, issue["id"], "IN_PROGRESS")
    second = set_status(client, issue["id"], "CLOSED")

    assert first.status_code == 200
    assert first.json() == {**issue, "status": "IN_PROGRESS"}
    assert second.status_code == 200
    assert second.json() == {**issue, "status": "CLOSED"}
    assert snapshot(client, issue["id"])["status"] == "CLOSED"


def test_t09_ac_04_1_open_can_be_closed_directly(client):
    issue = issue_in(client, "OPEN")

    response = set_status(client, issue["id"], "CLOSED")

    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"


@pytest.mark.parametrize("state", ["OPEN", "IN_PROGRESS", "CLOSED"])
def test_t09_ac_04_2_ac_04_5_repeating_current_status_is_success(client, state):
    issue = issue_in(client, state)

    response = set_status(client, issue["id"], state)

    assert response.status_code == 200
    assert response.json() == issue
    assert snapshot(client, issue["id"]) == issue


# ---------- T10: заборонені переходи (AC-04.3, AC-04.4) ----------


@pytest.mark.parametrize(
    ("current", "target"),
    [
        pytest.param("IN_PROGRESS", "OPEN", id="in_progress-open"),
        pytest.param("CLOSED", "OPEN", id="closed-open"),
        pytest.param("CLOSED", "IN_PROGRESS", id="closed-in_progress"),
    ],
)
def test_t10_ac_04_3_ac_04_4_forbidden_transition_is_conflict(
    client, current, target
):
    issue = issue_in(client, current)

    response = set_status(client, issue["id"], target)

    assert_error(response, 409, "conflict")
    assert snapshot(client, issue["id"]) == issue
    assert snapshot(client, issue["id"])["status"] == current


def test_t10_ac_04_3_conflict_message_names_both_statuses(client):
    issue = issue_in(client, "CLOSED")

    response = set_status(client, issue["id"], "OPEN")

    assert response.json() == {
        "error": {
            "type": "conflict",
            "message": "Перехід зі статусу CLOSED у статус OPEN заборонений",
        }
    }


# ---------- T14: некоректний PATCH (AC-03.5, AC-03.7) ----------


def test_t14_ac_03_5_empty_patch_is_validation_error(client):
    issue = issue_in(client, "OPEN")

    response = client.patch(f"/issues/{issue['id']}", json={})

    assert_validation_error(response, "body")
    assert snapshot(client, issue["id"]) == issue


@pytest.mark.parametrize(
    "field",
    ["status", "id", "created_at", "foo"],
)
def test_t14_ac_03_7_disallowed_or_unknown_field_is_validation_error(client, field):
    issue = issue_in(client, "OPEN")

    response = patch(client, issue["id"], **{field: "OPEN"})

    assert_validation_error(response, field)
    assert snapshot(client, issue["id"]) == issue


def test_t14_ac_03_7_status_with_valid_field_rejects_whole_request(client):
    issue = issue_in(client, "OPEN", priority="low")

    response = patch(client, issue["id"], priority="high", status="CLOSED")

    assert_validation_error(response, "status")
    assert snapshot(client, issue["id"]) == issue


def test_t14_patch_non_object_body_is_validation_error(client):
    issue = issue_in(client, "OPEN")

    response = client.patch(f"/issues/{issue['id']}", json=[])

    assert_validation_error(response, "body")
    assert snapshot(client, issue["id"]) == issue


def test_t14_patch_invalid_json_is_validation_error(client):
    issue = issue_in(client, "OPEN")

    response = patch_raw(client, f"/issues/{issue['id']}", INVALID_JSON_BODY)

    assert_validation_error(response, "body")
    assert snapshot(client, issue["id"]) == issue


# ---------- AC-03.4, AC-07.3 та порядок перевірок (404 → 409 → 422) ----------


@pytest.mark.parametrize(
    "body",
    [{"priority": "low"}, {"title": "Нова назва"}, {}, {"title": "ab"}, {"foo": 1}],
    ids=["priority", "title", "empty", "invalid-title", "unknown-field"],
)
def test_ac_03_4_closed_issue_rejects_any_patch_with_conflict(client, body):
    issue = issue_in(client, "CLOSED")

    response = client.patch(f"/issues/{issue['id']}", json=body)

    assert_error(response, 409, "conflict")
    assert snapshot(client, issue["id"]) == issue


def test_ac_03_4_closed_issue_with_invalid_json_is_conflict(client):
    issue = issue_in(client, "CLOSED")

    response = patch_raw(client, f"/issues/{issue['id']}", INVALID_JSON_BODY)

    assert_error(response, 409, "conflict")


@pytest.mark.parametrize("value", ["DONE", "done", "", None, 1])
def test_ac_07_3_unknown_status_is_validation_error(client, value):
    issue = issue_in(client, "OPEN")

    response = set_status(client, issue["id"], value)

    assert_validation_error(response, "status")
    assert snapshot(client, issue["id"]) == issue


def test_ac_07_3_closed_issue_with_unknown_status_is_validation_error(client):
    issue = issue_in(client, "CLOSED")

    response = set_status(client, issue["id"], "DONE")

    assert_validation_error(response, "status")
    assert snapshot(client, issue["id"]) == issue


def test_contract_3_7_missing_status_is_validation_error(client):
    issue = issue_in(client, "OPEN")

    response = client.patch(f"/issues/{issue['id']}/status", json={})

    assert_validation_error(response, "status")


def test_contract_3_7_unknown_field_is_validation_error(client):
    issue = issue_in(client, "OPEN")

    response = client.patch(
        f"/issues/{issue['id']}/status", json={"status": "CLOSED", "foo": 1}
    )

    assert_validation_error(response, "foo")
    assert snapshot(client, issue["id"]) == issue


def test_contract_3_7_non_object_and_invalid_json_are_validation_errors(client):
    issue = issue_in(client, "OPEN")
    path = f"/issues/{issue['id']}/status"

    assert_validation_error(client.patch(path, json=[]), "body")
    assert_validation_error(patch_raw(client, path, INVALID_JSON_BODY), "body")
    assert snapshot(client, issue["id"]) == issue


def test_order_patch_unknown_issue_wins_over_invalid_body(client):
    for response in (
        client.patch("/issues/99", json={}),
        client.patch("/issues/99", json={"title": "ab", "foo": 1}),
        patch_raw(client, "/issues/99", INVALID_JSON_BODY),
    ):
        assert_error(response, 404, "not_found")
        assert response.json()["error"]["message"] == "Заявку з id 99 не знайдено"


def test_order_status_unknown_issue_wins_over_invalid_body(client):
    for response in (
        client.patch("/issues/99/status", json={"status": "DONE"}),
        client.patch("/issues/99/status", json={}),
        patch_raw(client, "/issues/99/status", INVALID_JSON_BODY),
    ):
        assert_error(response, 404, "not_found")


@pytest.mark.parametrize("bad_id", ["abc", "0", "-1"])
def test_d_10_invalid_id_is_not_found_for_both_patch_routes(client, bad_id):
    create(client, title="Помилка входу")

    edit = client.patch(f"/issues/{bad_id}", json={"priority": "high"})
    status = client.patch(f"/issues/{bad_id}/status", json={"status": "CLOSED"})

    assert_error(edit, 404, "not_found")
    assert_error(status, 404, "not_found")