# Додано студенткою ПІСЛЯ матриці мутацій (T1 = 56c961c не змінювався).
# Цей файл не входить до T1 і не впливає на MS.

# --- допоміжні функції (скопійовано з tests/test_issues.py) ---


def create(client, **body):
    return client.post("/issues", json=body)


def snapshot(client, issue_id):
    return client.get(f"/issues/{issue_id}").json()


# --- сценарій ---


def test_patch_description_and_assignee_together_preserves_other_fields(client):
    """
    AC-03.1, AC-05.1. Одним PATCH змінюються description та assignee_id.
    Інші поля заявки, включно зі службовими, повинні залишитися без змін.
    """
    # 1. Створення заявки (лише дозволені поля)
    response = create(
        client,
        title="Initial title",
        description="Initial description",
        priority="medium",
    )
    assert response.status_code == 201

    issue_id = response.json()["id"]

    # 2. Призначення початкового виконавця окремим PATCH
    assign_response = client.patch(
        f"/issues/{issue_id}",
        json={"assignee_id": 1},
    )
    assert assign_response.status_code == 200

    # 3. Збереження початкового стану
    before = snapshot(client, issue_id)

    # Переконуємося, що початкові умови виконані
    assert before["assignee_id"] == 1
    assert before["status"] == "OPEN"

    # 4. Одночасне оновлення description та assignee_id
    patch_response = client.patch(
        f"/issues/{issue_id}",
        json={
            "description": "Updated description",
            "assignee_id": 2,
        },
    )
    assert patch_response.status_code == 200

    patch_body = patch_response.json()

    # 5. Повторне отримання заявки
    after = snapshot(client, issue_id)

    # 6. Перевірка змінених полів
    assert after["description"] == "Updated description"
    assert after["assignee_id"] == 2

    # Перевірка тіла відповіді PATCH
    assert patch_body["description"] == "Updated description"
    assert patch_body["assignee_id"] == 2

    # 7. Перевірка незмінених основних полів
    assert after["title"] == before["title"]
    assert after["priority"] == before["priority"]
    assert after["status"] == before["status"]

    # 8. Перевірка незмінених службових полів
    assert after["created_at"] == before["created_at"]
    assert after["id"] == before["id"]