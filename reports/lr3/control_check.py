"""Контрольні запити для M1-M3 (тестова БД у тимчасовій теці)."""
import pathlib
import tempfile

from fastapi.testclient import TestClient

from app.main import create_app


def run():
    with tempfile.TemporaryDirectory() as d:
        app = create_app(pathlib.Path(d) / "control.db")
        with TestClient(app, raise_server_exceptions=False) as c:
            # M1: повторне відкриття CLOSED
            i = c.post("/issues", json={"title": "Control issue"}).json()["id"]
            c.patch(f"/issues/{i}/status", json={"status": "CLOSED"})
            r = c.patch(f"/issues/{i}/status", json={"status": "OPEN"})
            now = c.get(f"/issues/{i}").json()["status"]
            print("M1 CLOSED->OPEN:", r.status_code, "| GET status:", now)

            # M2: відхилений PATCH не має змінювати жодне поле
            j = c.post(
                "/issues", json={"title": "Control issue 2", "priority": "medium"}
            ).json()["id"]
            c.patch(f"/issues/{j}", json={"assignee_id": 1})
            before = c.get(f"/issues/{j}").json()
            r = c.patch(f"/issues/{j}", json={"priority": "high", "assignee_id": 999})
            after = c.get(f"/issues/{j}").json()
            print(
                "M2 PATCH:", r.status_code,
                "| priority", before["priority"], "->", after["priority"],
                "| assignee", before["assignee_id"], "->", after["assignee_id"],
            )

            # M3: збереження назви
            for title in ("Save button", "O'Brien"):
                r = c.post("/issues", json={"title": title})
                if r.status_code == 201:
                    got = c.get(f"/issues/{r.json()['id']}").json()["title"]
                    print("M3", repr(title), "->", r.status_code, "| GET:", repr(got),
                          "| exact:", got == title)
                else:
                    print("M3", repr(title), "->", r.status_code)


run()