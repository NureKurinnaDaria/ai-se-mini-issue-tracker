# tests/test_lr3_ai.py
import pytest


# --- допоміжні функції (скопійовано з tests/test_issues.py) ---------------

def create(client, **body):
    return client.post("/issues", json=body)


def patch(client, issue_id, **body):
    return client.patch(f"/issues/{issue_id}", json=body)


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


def assert_validation_error(response, field):
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["type"] == "validation_error"
    fields = [d["field"] for d in error["details"]]
    assert field in fields
    assert all(d["reason"] for d in error["details"])


# --- дані -----------------------------------------------------------------

SPECIAL_TITLES = ["Save button", "O'Brien", "x'; DROP TABLE issues; --"]

# (поточний, цільовий, очікуваний код): усі 9 пар
STATUS_PAIRS = [
    ("OPEN", "OPEN", 200),
    ("OPEN", "IN_PROGRESS", 200),
    ("OPEN", "CLOSED", 200),
    ("IN_PROGRESS", "OPEN", 409),
    ("IN_PROGRESS", "IN_PROGRESS", 200),
    ("IN_PROGRESS", "CLOSED", 200),
    ("CLOSED", "OPEN", 409),
    ("CLOSED", "IN_PROGRESS", 409),
    ("CLOSED", "CLOSED", 200),
]


# --- тести ----------------------------------------------------------------

@pytest.mark.parametrize("title", SPECIAL_TITLES)
def test_create_preserves_special_title(client, title):
    """
    AC: POST /issues з коректним title повертає 201, а title зберігається
    без змін (апострофи та SQL-подібний текст є звичайними даними).
    Після повторного GET: і GET /issues/{id}, і елемент у GET /issues
    мають title, точно рівний переданому.
    """
    response = create(client, title=title)
    assert response.status_code == 201
    issue_id = response.json()["id"]

    assert snapshot(client, issue_id)["title"] == title

    listing = client.get("/issues")
    assert listing.status_code == 200
    by_id = {i["id"]: i for i in listing.json()}
    assert by_id[issue_id]["title"] == title


@pytest.mark.parametrize("title", SPECIAL_TITLES)
def test_patch_preserves_special_title(client, title):
    """
    AC: PATCH /issues/{id} з коректним title повертає 200 і зберігає title
    без змін.
    Після повторного GET: GET /issues/{id} і GET /issues повертають title,
    точно рівний новому значенню.
    """
    issue = issue_in(client, "OPEN", title="Початкова назва")

    response = patch(client, issue["id"], title=title)
    assert response.status_code == 200

    assert snapshot(client, issue["id"])["title"] == title
    by_id = {i["id"]: i for i in client.get("/issues").json()}
    assert by_id[issue["id"]]["title"] == title


def test_patch_atomic_priority_with_unknown_assignee(client):
    """
    AC: якщо будь-яка передана зміна некоректна (assignee_id=999), PATCH дає
    422 і жодна зі змін не зберігається.
    Після повторного GET: priority == "medium", assignee_id == 1
    (початкові значення), а не "high".
    """
    issue = issue_in(client, "OPEN", priority="medium", assignee_id=1)
    assert issue["priority"] == "medium" and issue["assignee_id"] == 1

    response = patch(client, issue["id"], priority="high", assignee_id=999)
    assert_validation_error(response, "assignee_id")

    after = snapshot(client, issue["id"])
    assert after["priority"] == "medium"
    assert after["assignee_id"] == 1


def test_patch_atomic_title_description_with_unknown_assignee(client):
    """
    AC: атомарність PATCH для кількох полів: title і description не
    зберігаються, якщо assignee_id некоректний.
    Після повторного GET: title, description і assignee_id дорівнюють
    початковим значенням.
    """
    issue = issue_in(
        client, "OPEN",
        title="Початкова назва", description="Початковий опис", assignee_id=2,
    )

    response = patch(
        client, issue["id"],
        title="Нова назва", description="Новий опис", assignee_id=999,
    )
    assert_validation_error(response, "assignee_id")

    after = snapshot(client, issue["id"])
    assert after["title"] == "Початкова назва"
    assert after["description"] == "Початковий опис"
    assert after["assignee_id"] == 2


@pytest.mark.parametrize("current,target,expected", STATUS_PAIRS)
def test_status_transition_matrix(client, current, target, expected):
    """
    AC: дозволені переходи та повторне встановлення поточного статусу дають
    200; заборонені (IN_PROGRESS->OPEN, CLOSED->OPEN, CLOSED->IN_PROGRESS)
    дають 409 conflict.
    Після повторного GET: status == target при 200 (для повторення заявка
    повністю не змінена); status == current і заявка не змінена при 409.
    """
    before = issue_in(client, current)
    assert before["status"] == current

    response = set_status(client, before["id"], target)
    after = snapshot(client, before["id"])

    if expected == 200:
        assert response.status_code == 200
        assert after["status"] == target
        if current == target:
            assert after == before
    else:
        assert_error(response, 409, "conflict")
        assert after == before


@pytest.mark.parametrize(
    "old,new", [("OPEN", "IN_PROGRESS"), ("OPEN", "CLOSED"),
                ("IN_PROGRESS", "CLOSED")]
)
def test_status_change_moves_issue_between_filters(client, old, new):
    """
    AC: фільтр GET /issues?status= відображає актуальний статус заявки.
    Після повторного GET: заявка є у ?status=<новий> і відсутня
    у ?status=<старий>.
    """
    issue = issue_in(client, old)
    assert set_status(client, issue["id"], new).status_code == 200

    in_new = client.get("/issues", params={"status": new})
    in_old = client.get("/issues", params={"status": old})
    assert in_new.status_code == 200 and in_old.status_code == 200
    assert issue["id"] in [i["id"] for i in in_new.json()]
    assert issue["id"] not in [i["id"] for i in in_old.json()]


@pytest.mark.parametrize(
    "old,new", [("low", "high"), ("high", "medium"), ("medium", "low")]
)
def test_priority_change_moves_issue_between_filters(client, old, new):
    """
    AC: PATCH priority повертає 200, а фільтр GET /issues?priority=
    відображає актуальний пріоритет.
    Після повторного GET: заявка має priority == new, є у ?priority=<новий>
    і відсутня у ?priority=<старий>.
    """
    issue = issue_in(client, "OPEN", priority=old)
    assert issue["priority"] == old

    assert patch(client, issue["id"], priority=new).status_code == 200
    assert snapshot(client, issue["id"])["priority"] == new

    in_new = client.get("/issues", params={"priority": new})
    in_old = client.get("/issues", params={"priority": old})
    assert issue["id"] in [i["id"] for i in in_new.json()]
    assert issue["id"] not in [i["id"] for i in in_old.json()]


ERROR_CASES = [
    pytest.param(lambda c: c.get("/issues/9999"), 404, "not_found",
                 id="get-missing"),
    pytest.param(lambda c: patch(c, 9999, title="Нова назва"), 404,
                 "not_found", id="patch-missing"),
    pytest.param(lambda c: set_status(c, 9999, "CLOSED"), 404, "not_found",
                 id="status-missing"),
    pytest.param(
        lambda c: patch(c, issue_in(c, "CLOSED")["id"], title="Нова назва"),
        409, "conflict", id="patch-closed"),
    pytest.param(
        lambda c: set_status(c, issue_in(c, "CLOSED")["id"], "OPEN"),
        409, "conflict", id="forbidden-transition"),
    pytest.param(lambda c: create(c, title="ab"), 422, "validation_error",
                 id="create-short-title"),
    pytest.param(lambda c: create(c, description="без назви"), 422,
                 "validation_error", id="create-no-title"),
    pytest.param(
        lambda c: set_status(c, issue_in(c, "OPEN")["id"], "DONE"),
        422, "validation_error", id="unknown-status"),
    pytest.param(
        lambda c: patch(c, issue_in(c, "OPEN")["id"], assignee_id=999),
        422, "validation_error", id="unknown-assignee"),
]


@pytest.mark.parametrize("make_request,status_code,error_type", ERROR_CASES)
def test_error_responses_use_contract_format(
    client, make_request, status_code, error_type
):
    """
    AC: відповіді 404/409/422 мають формат {"error": {"type", "message"}},
    а не FastAPI-формат {"detail": ...}; без стектрейсу; код не 500;
    details є лише для validation_error.
    Після повторного GET: не застосовується (запити не змінюють даних);
    перевіряється лише тіло й код самої відповіді.
    """
    response = make_request(client)

    assert response.status_code != 500
    assert response.status_code == status_code
    assert "Traceback" not in response.text

    body = response.json()
    assert "detail" not in body
    assert set(body) == {"error"}
    assert body["error"]["type"] == error_type
    assert body["error"]["message"]
    if error_type == "validation_error":
        assert body["error"]["details"]
    else:
        assert not body["error"].get("details")