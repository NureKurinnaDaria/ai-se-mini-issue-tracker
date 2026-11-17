"""Спільні перевірки для matches_status і matches_priority (крок 6).

Логіка однакова для обох полів. Предикати — чисті функції над заявкою (dict):
value=None означає «не фільтрувати», інше значення — точне порівняння.
"""

import copy

import pytest

from app import service

CASES = [
    pytest.param("matches_status", "status", ["OPEN", "IN_PROGRESS", "CLOSED"], id="status"),
    pytest.param("matches_priority", "priority", ["low", "medium", "high"], id="priority"),
]


def make_issue(field, value):
    issue = {
        "id": 1,
        "title": "Тест",
        "description": "",
        "status": "OPEN",
        "priority": "medium",
        "assignee_id": None,
        "created_at": "2026-11-12T10:00:00Z",
    }
    issue[field] = value
    return issue


@pytest.mark.parametrize(("name", "field", "values"), CASES)
def test_none_means_no_filter(name, field, values):
    predicate = getattr(service, name)
    for actual in values:
        assert predicate(make_issue(field, actual), None) is True


@pytest.mark.parametrize(("name", "field", "values"), CASES)
def test_equal_value_matches(name, field, values):
    predicate = getattr(service, name)
    for value in values:
        assert predicate(make_issue(field, value), value) is True


@pytest.mark.parametrize(("name", "field", "values"), CASES)
def test_other_value_does_not_match(name, field, values):
    predicate = getattr(service, name)
    for actual in values:
        for value in values:
            if value != actual:
                assert predicate(make_issue(field, actual), value) is False


@pytest.mark.parametrize(("name", "field", "values"), CASES)
@pytest.mark.parametrize("variant", ["swapcase", "leading_space", "trailing_space"])
def test_comparison_is_exact(name, field, values, variant):
    predicate = getattr(service, name)
    actual = values[0]
    changed = {
        "swapcase": actual.swapcase(),
        "leading_space": " " + actual,
        "trailing_space": actual + " ",
    }[variant]
    assert predicate(make_issue(field, actual), changed) is False


@pytest.mark.parametrize(("name", "field", "values"), CASES)
def test_unknown_value_does_not_match(name, field, values):
    predicate = getattr(service, name)
    assert predicate(make_issue(field, values[0]), "unknown") is False


@pytest.mark.parametrize(("name", "field", "values"), CASES)
def test_other_fields_are_ignored(name, field, values):
    predicate = getattr(service, name)
    other = "priority" if field == "status" else "status"
    issue = make_issue(field, values[0])
    issue[other] = "something-else"
    issue["title"] = values[1]
    assert predicate(issue, values[0]) is True
    assert predicate(issue, values[1]) is False


@pytest.mark.parametrize(("name", "field", "values"), CASES)
def test_input_is_not_mutated(name, field, values):
    predicate = getattr(service, name)
    issue = make_issue(field, values[0])
    before = copy.deepcopy(issue)
    predicate(issue, values[0])
    predicate(issue, None)
    predicate(issue, values[1])
    assert issue == before
