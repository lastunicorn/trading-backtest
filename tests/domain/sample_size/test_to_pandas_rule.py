"""Tests for `domain.sample_size.SampleSize.to_pandas_rule`."""

import pytest

from domain.sample_size import SampleSize


@pytest.mark.parametrize(
    ("interval", "rule"),
    [
        ("5m", "5min"),
        ("4h", "4h"),
        ("1d", "1D"),
        ("2w", "2W"),
        ("3M", "3MS"),
    ],
)
def test_maps_each_unit_to_its_pandas_alias(interval: str, rule: str) -> None:
    assert SampleSize.Parse(interval).to_pandas_rule() == rule


def test_minutes_and_months_do_not_collide() -> None:
    assert SampleSize.Parse("1m").to_pandas_rule() != SampleSize.Parse("1M").to_pandas_rule()
