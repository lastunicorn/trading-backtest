"""Tests for `domain.sample_size.SampleSize.__str__`."""

import pytest

from domain.sample_size import SampleSize, SampleUnit


def test_amount_then_unit_letter() -> None:
    assert str(SampleSize(5, SampleUnit.Minute)) == "5m"


@pytest.mark.parametrize("interval", ["1m", "15m", "4h", "7d", "2w", "3M"])
def test_round_trips_through_parse(interval: str) -> None:
    assert str(SampleSize.Parse(interval)) == interval
