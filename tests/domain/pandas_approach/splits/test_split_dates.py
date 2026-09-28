"""Tests for `domain.pandas_approach.splits.split_dates`."""

from datetime import date, timedelta

import pytest

from domain.pandas_approach.splits import Split, split_dates


def _days(n: int) -> list[date]:
    return [date(2026, 1, 1) + timedelta(days=i) for i in range(n)]


def _counts(by_date: dict) -> list[int]:
    values = list(by_date.values())
    return [values.count(split) for split in Split]


def test_ten_days_split_six_two_two() -> None:
    assert _counts(split_dates(_days(10))) == [6, 2, 2]


@pytest.mark.parametrize("n", [1, 7, 11, 1599, 2001])
def test_boundaries_match_v28_int_truncation(n: int) -> None:
    discovery, validation, test = _counts(split_dates(_days(n)))

    assert discovery == int(n * 0.60)
    assert discovery + validation == int(n * 0.80)
    assert discovery + validation + test == n


def test_splits_are_chronological_not_input_order() -> None:
    days = _days(10)

    result = split_dates(reversed(days))

    assert [result[d] for d in days[:6]] == [Split.DISCOVERY] * 6
    assert [result[d] for d in days[6:8]] == [Split.VALIDATION] * 2
    assert [result[d] for d in days[8:]] == [Split.TEST] * 2


def test_duplicate_dates_count_once() -> None:
    days = _days(10)

    assert _counts(split_dates(days + days)) == [6, 2, 2]


def test_custom_fractions() -> None:
    assert _counts(split_dates(_days(10), discovery=0.5, validation=0.3)) == [5, 3, 2]


@pytest.mark.parametrize(("discovery", "validation"), [(0, 0.2), (0.6, 0), (0.8, 0.2), (0.9, 0.3)])
def test_fractions_leaving_no_room_are_rejected(discovery: float, validation: float) -> None:
    with pytest.raises(ValueError, match="room left for test"):
        split_dates(_days(10), discovery=discovery, validation=validation)


def test_no_dates_gives_an_empty_mapping() -> None:
    assert split_dates([]) == {}
