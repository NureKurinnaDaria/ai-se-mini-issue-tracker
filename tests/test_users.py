"""GET /users: довідник із двох користувачів (api-contract.md, 3.2)."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_users_returns_two_reference_users_in_id_order(client):
    response = client.get("/users")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "name": "Agent A"},
        {"id": 2, "name": "Agent B"},
    ]


@pytest.mark.parametrize("method", ["post", "patch", "delete"])
def test_users_are_read_only(client, method):
    response = client.request(method.upper(), "/users", json={"name": "Agent C"})

    assert response.status_code == 405
    assert len(client.get("/users").json()) == 2


def test_users_survive_app_restart(db_path):
    with TestClient(create_app(db_path)) as first:
        assert len(first.get("/users").json()) == 2

    with TestClient(create_app(db_path)) as second:
        assert second.get("/users").json() == [
            {"id": 1, "name": "Agent A"},
            {"id": 2, "name": "Agent B"},
        ]