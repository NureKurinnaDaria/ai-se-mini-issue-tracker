# Mini Issue Tracker

Навчальний проєкт з курсу «Штучний інтелект у програмній інженерії»: система обліку заявок (issue tracker) з майбутнім AI-компонентом. Виконала Курінна Дар'я, група ПЗПІ-23-9.

## Стан

ЛР2: реалізовано сервіс (FastAPI, SQLite): 9 маршрутів, 219 автоматичних тестів. Версія здачі ЛР2: тег `lab02-implemented`; проміжні версії: `lab02-skill-v0` (Skill), `lab02-ai-draft` (перший AI-патч). ЛР1: вимоги та проєктування, версія здачі: тег `lab01-spec`.

GitHub repository: https://github.com/NureKurinnaDaria/ai-se-mini-issue-tracker

Відеозахист ЛР1:
https://drive.google.com/file/d/1RB_ghVUb4DY0W8fD-CxE4u5KGgz54iLX/view?usp=sharing

Відеозахист ЛР2: https://drive.google.com/file/d/1FjcNSw5ZuOOanSIb_yI7eVLDeKw0tWG2/view?usp=sharing

## Документація (папка `docs/`)

| Файл                                          | Зміст                                                                       |
| --------------------------------------------- | --------------------------------------------------------------------------- |
| [requirements.md](docs/requirements.md)       | вимоги, контракт даних, правила; **єдине джерело істини для бізнес-правил** |
| [architecture.md](docs/architecture.md)       | архітектура, модель сутностей, ADR-01 і ADR-02                              |
| [api-contract.md](docs/api-contract.md)       | API-контракт                                                                |
| [traceability.csv](docs/traceability.csv)     | матриця простежуваності                                                     |
| [ai-log.md](docs/ai-log.md)                   | журнал взаємодії з AI                                                       |
| [lab-01.md](docs/lab-01.md)                   | звіт з ЛР1                                                                  |
| [lab-02.md](docs/lab-02.md)                   | звіт з ЛР2: Skill, AI-draft і final, експеримент, обмеження                 |
| [experiment-lr2.csv](docs/experiment-lr2.csv) | протокол мікроексперименту (AI / без AI)                                    |

## Запуск і перевірка (ЛР2)

Протестовано з **Python 3.15.2** на Windows (PowerShell). Залежності зафіксовано в `requirements-lock.txt`.

### Чисте встановлення і запуск

```
git clone https://github.com/NureKurinnaDaria/ai-se-mini-issue-tracker.git
cd ai-se-mini-issue-tracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
python -m uvicorn app.main:app --host 127.0.0.1
```

Якщо активація середовища заблокована політикою скриптів, не змінюйте системні налаштування, а викликайте Python напряму: `.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt` і `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1`.

Сервіс слухає `http://127.0.0.1:8000`; перевірка: `GET /health`. База даних SQLite створюється автоматично в `data/app.db` (файл не комітиться). Інший шлях до бази задається змінною середовища `ISSUE_TRACKER_DB`.

### Тести та перевірки

```
python -m pytest -q
python -m ruff check app tests --select E4,E7,E9,F,I
python -m bandit -r app -q
```

Тести використовують окрему тимчасову базу (`tmp_path`) і не торкаються `data/app.db`.

### API

| Маршрут                      | Призначення                           | Успіх | Помилки       |
| ---------------------------- | ------------------------------------- | ----- | ------------- |
| `GET /health`                | Перевірка запуску                     | 200   | -             |
| `GET /users`                 | Два тестові користувачі               | 200   | -             |
| `POST /issues`               | Створити заявку                       | 201   | 422           |
| `GET /issues`                | Список (фільтри `status`, `priority`) | 200   | 422           |
| `GET /issues/{id}`           | Одна заявка                           | 200   | 404           |
| `PATCH /issues/{id}`         | Часткове редагування, виконавець      | 200   | 404, 409, 422 |
| `PATCH /issues/{id}/status`  | Зміна статусу                         | 200   | 404, 409, 422 |
| `POST /issues/{id}/comments` | Додати коментар                       | 201   | 404, 422      |
| `GET /issues/{id}/comments`  | Список коментарів                     | 200   | 404           |

Повний контракт: `docs/api-contract.md`. Формат помилки: `{"error": {"type": "...", "message": "...", "details": [{"field": "...", "reason": "..."}]}}`.

### Приклад

Swagger (`/docs`) показує маршрути, але не форми тіла для `POST` і `PATCH` (тіло читається сирим, щоб зберегти порядок перевірок «не знайдено → конфлікт → валідація»). Використовуйте `curl.exe`:

```
$t = $env:TEMP
Set-Content -Encoding ascii "$t\issue.json" '{"title":"Demo issue","priority":"high"}'
curl.exe -s -X POST http://127.0.0.1:8000/issues -H "Content-Type: application/json" --data "@$t\issue.json"
curl.exe -s "http://127.0.0.1:8000/issues?status=OPEN&priority=high"
```

На Linux або macOS: `curl -s -X POST http://127.0.0.1:8000/issues -H "Content-Type: application/json" -d '{"title":"Demo issue","priority":"high"}'`.

### Навчальні обмеження

- Лише локальний запуск із синтетичними даними; автентифікації немає, `author_id` задає клієнт.
- SQLite розрахована на одного чи кількох користувачів у локальному середовищі, не на високе навантаження.
- AI-асистент використовувався в режимі чату без підтримки Skills (`.agents/skills/tracker-slice/` вставлявся вручну; копія в `.claude/skills/` не потрібна, бо Claude Code не застосовувався).
- Відомі дефекти й обмеження: `docs/lab-02.md`, розділ 6. Журнал використання AI: `docs/ai-log.md`.
