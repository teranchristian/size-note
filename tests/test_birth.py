from datetime import date

import pytest

from size_note.birth import (
    approximate_age_years,
    effective_growth_stage,
    parse_birth,
    review_interval_days,
    youngest_possible_age,
)

SHOES = {"shoes"}


def test_partial_birth_keeps_only_known_precision():
    year = parse_birth("2024", today=date(2026, 8, 30))
    month = parse_birth("2024-05", today=date(2026, 8, 30))
    exact = parse_birth("2024-05-12", today=date(2026, 8, 30))

    assert year.display() == "2024"
    assert year.month is None and year.day is None
    assert month.display() == "2024-05"
    assert month.day is None
    assert exact.display() == "2024-05-12"


def test_partial_birth_never_fabricates_a_first_day():
    assert youngest_possible_age(2024, today=date(2026, 8, 30)) == 1
    assert youngest_possible_age(2024, 5, today=date(2026, 5, 10)) == 1
    assert youngest_possible_age(2024, 5, 1, today=date(2026, 5, 10)) == 2


def test_display_age_can_be_friendlier_than_conservative_review_age():
    assert approximate_age_years(2024, today=date(2026, 8, 30)) == 2
    assert youngest_possible_age(2024, today=date(2026, 8, 30)) == 1
    assert approximate_age_years(2024, 5, today=date(2026, 8, 30)) == 2


def test_partial_birth_becomes_adult_only_when_definitely_eighteen():
    assert (
        effective_growth_stage("adult", 2008, today=date(2026, 12, 31))
        == "child"
    )
    assert effective_growth_stage("child", 2008, today=date(2027, 1, 1)) == "adult"
    assert (
        effective_growth_stage("child", 2008, 5, today=date(2026, 5, 1))
        == "child"
    )
    assert (
        effective_growth_stage("child", 2008, 5, today=date(2026, 6, 1))
        == "adult"
    )


def test_age_aware_review_intervals_use_younger_possible_age():
    assert review_interval_days(
        "child",
        2024,
        None,
        None,
        item_key="t-shirt",
        shoe_keys=SHOES,
        today=date(2026, 8, 30),
    ) == 90
    assert review_interval_days(
        "child",
        2022,
        1,
        1,
        item_key="t-shirt",
        shoe_keys=SHOES,
        today=date(2026, 8, 30),
    ) == 120
    assert review_interval_days(
        "child",
        2017,
        1,
        1,
        item_key="t-shirt",
        shoe_keys=SHOES,
        today=date(2026, 8, 30),
    ) == 180
    assert review_interval_days(
        "child",
        2010,
        1,
        1,
        item_key="t-shirt",
        shoe_keys=SHOES,
        today=date(2026, 8, 30),
    ) == 270


def test_child_without_birth_uses_original_item_fallback():
    assert review_interval_days(
        "child",
        None,
        None,
        None,
        item_key="shoes",
        shoe_keys=SHOES,
        today=date(2026, 8, 30),
    ) == 90
    assert review_interval_days(
        "child",
        None,
        None,
        None,
        item_key="t-shirt",
        shoe_keys=SHOES,
        today=date(2026, 8, 30),
    ) == 180


def test_invalid_or_future_birth_is_rejected():
    with pytest.raises(ValueError):
        parse_birth("2024-02-30", today=date(2026, 8, 30))
    with pytest.raises(ValueError):
        parse_birth("2027", today=date(2026, 8, 30))
