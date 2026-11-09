# Зрізи Mini Issue Tracker

Контракт має одне джерело — docs/. Тут лише посилання на розділи, без копіювання правил.
Маршрути розміщуються в routes.py (якщо їх об'єднано з main.py — використовуй main.py).
Критерії AC — у docs/requirements.md, розділ «Користувацькі історії та критерії приймання».

## A. Створення й читання
- Код (app/): schemas.py, service.py, routes.py, database.py
- Тести (tests/): conftest.py, test_issues.py
- Читати: docs/api-contract.md — 3.3 POST /issues, 3.5 GET /issues/{id}, 3.4 GET /issues (без фільтрів);
  docs/requirements.md — «Модель даних», «Впорядкування списків»
- Критерії: US-01 (AC-01.1–01.3); US-02 (AC-02.2, AC-02.4); US-07 (AC-07.1, AC-07.2)
- Сценарії: T01, T02, T03, T13

## B. Зміни й стани
- Код (app/): schemas.py, service.py, routes.py
- Тести (tests/): test_issues.py
- Читати: docs/api-contract.md — 3.6 PATCH /issues/{id}, 3.7 PATCH /issues/{id}/status;
  docs/requirements.md — «Життєвий цикл заявки» (матриця переходів, операції для закритої заявки),
  «Правила часткового редагування (PATCH)», «Каталог результатів» (пріоритет перевірок)
- Критерії: US-03 (AC-03.1–03.7); US-04 (AC-04.1–04.5); US-05 (AC-05.1–05.4); US-07 (AC-07.3)
- Сценарії: T07, T08, T09, T10, T14

## C. Коментарі
- Код (app/): schemas.py, service.py, routes.py
- Тести (tests/): test_comments.py
- Читати: docs/api-contract.md — 3.8 POST і 3.9 GET /issues/{id}/comments;
  docs/requirements.md — «Сутність Comment», «Зв'язки», «Впорядкування списків»
- Критерії: US-06 (AC-06.1–06.5)
- Сценарії: T11, T12

## D. Фільтри
- Код (app/): schemas.py, service.py, routes.py
- Тести (tests/): test_issues.py
- Читати: docs/api-contract.md — 3.4 GET /issues, параметри status і priority;
  docs/requirements.md — FR-02, «Впорядкування списків»
- Критерії: US-02 (AC-02.1, AC-02.3, AC-02.5)
- Сценарії: T04, T05, T06
