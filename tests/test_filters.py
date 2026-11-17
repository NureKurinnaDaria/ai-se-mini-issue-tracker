"""Фільтри GET /issues (зріз D): T04, T05, T06, AC-02.1, AC-02.3, AC-02.5, D-09."""

import pytest


def make_issue(client, title, priority=None, status=None):
    body = {"title": title}
    if priority is not None:
        body["priority"] = priority
    issue = client.post("/issues", json=body).json()
    if status is not None:
        response = client.patch(f"/issues/{issue['id']}/status", json={"status": status})
        assert response.status_code == 200
        issue = response.json()
    return issue


def ids(response):
    return [issue["id"] for issue in response.json()]


def error_fields(response):
    return [d["field"] for d in response.json()["error"]["details"]]


@pytest.fixture
def seeded(client):
    """Чотири заявки з різними статусами й пріоритетами (id за порядком створення)."""
    return {
        "open_high": make_issue(client, "Open high", priority="high"),
        "open_low": make_issue(client, "Open low", priority="low"),
        "closed_high": make_issue(client, "Closed high", priority="high", status="CLOSED"),
        "progress_high": make_issue(
            client, "Progress high", priority="high", status="IN_PROGRESS"
        ),
    }


def test_t04_status_filter_alone(client, seeded):
    response = client.get("/issues", params={"status": "OPEN"})

    assert response.status_code == 200
    assert ids(response) == [seeded["open_high"]["id"], seeded["open_low"]["id"]]
    assert all(issue["status"] == "OPEN" for issue in response.json())


@pytest.mark.parametrize("status", ["IN_PROGRESS", "CLOSED"])
def test_t04_zero_matches_gives_empty_list(client, status):
    make_issue(client, "Only open")

    response = client.get("/issues", params={"status": status})

    assert response.status_code == 200
    assert response.json() == []


def test_t05_priority_filter_alone(client, seeded):
    response = client.get("/issues", params={"priority": "low"})

    assert response.status_code == 200
    assert ids(response) == [seeded["open_low"]["id"]]


@pytest.mark.parametrize(
    ("param", "value"),
    [
        ("priority", "urgent"),
        ("priority", "High"),
        ("priority", ""),
        ("status", "DONE"),
        ("status", "open"),
        ("status", ""),
    ],
)
def test_t05_invalid_filter_value_gives_422(client, seeded, param, value):
    response = client.get("/issues", params={param: value})

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["type"] == "validation_error"
    assert error_fields(response) == [param]
    assert "допустимі значення" in body["details"][0]["reason"]


def test_invalid_filter_gives_422_even_without_issues(client):
    response = client.get("/issues", params={"status": "DONE"})

    assert response.status_code == 422


def test_both_invalid_filters_are_reported(client):
    response = client.get("/issues", params={"status": "DONE", "priority": "urgent"})

    assert response.status_code == 422
    assert sorted(error_fields(response)) == ["priority", "status"]


def test_t06_two_filters_return_intersection_not_union(client, seeded):
    response = client.get("/issues", params={"status": "OPEN", "priority": "high"})

    assert response.status_code == 200
    # Об'єднання дало б 4 заявки; перетин — лише одну.
    assert ids(response) == [seeded["open_high"]["id"]]


def test_ac_02_1_important_open_issues_in_creation_order(client):
    first = make_issue(client, "First", priority="high")
    make_issue(client, "Low one", priority="low")
    second = make_issue(client, "Second", priority="high")
    make_issue(client, "Closed high", priority="high", status="CLOSED")

    response = client.get("/issues?status=OPEN&priority=high")

    assert response.status_code == 200
    assert ids(response) == [first["id"], second["id"]]


def test_two_filters_without_overlap_give_empty_list(client, seeded):
    response = client.get("/issues", params={"status": "CLOSED", "priority": "low"})

    assert response.status_code == 200
    assert response.json() == []


def test_one_valid_one_invalid_filter_gives_422(client, seeded):
    response = client.get("/issues", params={"status": "OPEN", "priority": "urgent"})

    assert response.status_code == 422
    assert error_fields(response) == ["priority"]


def test_no_filters_returns_all_in_order(client, seeded):
    response = client.get("/issues")

    assert response.status_code == 200
    assert ids(response) == [issue["id"] for issue in seeded.values()]


def test_unknown_query_params_are_ignored(client, seeded):
    response = client.get("/issues", params={"foo": "bar", "status": "OPEN"})

    assert response.status_code == 200
    assert ids(response) == [seeded["open_high"]["id"], seeded["open_low"]["id"]]


def test_filtered_result_has_full_issue_fields(client, seeded):
    response = client.get("/issues", params={"priority": "low"})

    issue = response.json()[0]
    assert set(issue) == {
        "id",
        "title",
        "description",
        "status",
        "priority",
        "assignee_id",
        "created_at",
    }


def test_filter_does_not_change_stored_data(client, seeded):
    before = client.get("/issues").json()

    client.get("/issues", params={"status": "OPEN", "priority": "high"})
    client.get("/issues", params={"status": "DONE"})

    assert client.get("/issues").json() == before
