from app.database import connect, init_db


def count(db_path, table):
    conn = connect(db_path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
    finally:
        conn.close()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_init_creates_two_users(client, db_path):
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT id, name FROM users ORDER BY id").fetchall()
    finally:
        conn.close()
    assert [(r["id"], r["name"]) for r in rows] == [(1, "Agent A"), (2, "Agent B")]


def test_reinit_keeps_users_and_issues(db_path):
    init_db(db_path)
    conn = connect(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO issues (title, created_at) VALUES (?, ?)",
                ("Тест", "2026-11-09T10:00:00Z"),
            )
    finally:
        conn.close()
    init_db(db_path)
    assert count(db_path, "users") == 2
    assert count(db_path, "issues") == 1