"""Tests for `domain.pandas_approach.splits.split_labels`."""

from datetime import date, timedelta

import pytest

from domain.pandas_approach.splits import SplitMode, split_dates, split_labels


def _days(n: int, first: date = date(2026, 1, 1)) -> list[date]:
    return [first + timedelta(days=i) for i in range(n)]


def test_dvt_is_the_60_20_20_cut() -> None:
    days = _days(10)

    assert split_labels(days, SplitMode.DVT) == {day: split.value for day, split in split_dates(days).items()}


def test_monthly_labels_each_day_with_its_month() -> None:
    labels = split_labels([date(2025, 12, 31), date(2026, 1, 1), date(2026, 2, 28)], SplitMode.MONTHLY)

    assert list(labels.values()) == ["2025-12", "2026-01", "2026-02"]


def test_yearly_labels_each_day_with_its_year() -> None:
    labels = split_labels([date(2025, 12, 31), date(2026, 1, 1)], SplitMode.YEARLY)

    assert list(labels.values()) == ["2025", "2026"]


@pytest.mark.parametrize("mode", [SplitMode.DVT, SplitMode.MONTHLY, SplitMode.YEARLY])
def test_labels_are_in_chronological_order_whatever_the_input_order(mode: SplitMode) -> None:
    days = _days(400, first=date(2025, 6, 1))

    assert list(split_labels(reversed(days + days), mode)) == days


def test_none_has_no_labels() -> None:
    with pytest.raises(ValueError):
        split_labels(_days(3), SplitMode.NONE)
