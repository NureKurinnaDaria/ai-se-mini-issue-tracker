# Матриця виявлення мутацій (ЛР3)

R0 = код `app/` з `lab02-implemented` (`4032564`); мутації відведено від `7128466` (код `app/` ідентичний R0).
T0 = 219 тестів ЛР2; T1 = T0 + 33 нових тести (32 від AI, 1 запропонований AI-консультацією; `56c961c`). Обидва набори проходять на R0 (219 і 252 passed).

| Версія                        | Код       | T0 виявив?      | T1 виявив?    | Доказ (тест, фактичний результат)                                                                                                                                                                                                                                             |
| ----------------------------- | --------- | --------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1. Повторне відкриття CLOSED | `33d580a` | Так (2 тести)   | Так (4 тести) | T0: `test_t10_..._forbidden_transition_is_conflict[closed-open]` (`assert 200 == 409`), `test_t10_..._conflict_message_names_both_statuses`. T1 додатково: `test_status_transition_matrix[CLOSED-OPEN-409]`, `test_error_responses_use_contract_format[forbidden-transition]` |
| M2. Частковий PATCH           | `adcb538` | Ні (219 passed) | Так (2 тести) | `test_patch_atomic_priority_with_unknown_assignee`: відповідь 422, але повторний GET `{'priority': 'high'} != {'priority': 'medium'}`; `test_patch_atomic_title_description_with_unknown_assignee`                                                                            |
| M3. Збереження назви          | `47d2a8f` | Ні (219 passed) | Так (2 тести) | `test_create_preserves_special_title[O'Brien]` і `[x'; DROP TABLE issues; --]`: `sqlite3.OperationalError: near "Brien": syntax error` і `near ";": syntax error`                                                                                                             |

**MS(T0) = 1/3 = 33,3 %. MS(T1) = 3/3 = 100 %.** Знаменник 3, мутацій не замінювали й не виключали.

Виправлення: M1 → `70bfd9c`, M3 → `f6dc320` (обидва збігаються з R0 за кодом `app/`). Для M2 виправлення не вимагалося.

Тест студентки `tests/test_lr3_student.py` додано після матриці (`b7f772b`), у T1 і MS не входить.
