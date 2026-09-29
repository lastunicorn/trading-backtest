"""Tests for `domain.sample_size.SampleSize.can_be_resampled_from`."""

import pytest

from domain.sample_size import SampleSize


@pytest.mark.parametrize(("target", "source"), [
    ("1m", "1m"),
    ("5m", "1m"),
    ("15m", "5m"),
    ("1h", "15m"),
    ("4h", "1h"),
    ("1d", "5m"),
    ("1w", "1d"),
    ("1M", "1m"),
    ("1M", "4h"),
    ("3M", "1M"),
])
def test_accepts_a_whole_multiple_of_the_source(target: str, source: str) -> None:
    assert SampleSize.Parse(target).can_be_resampled_from(SampleSize.Parse(source))


@pytest.mark.parametrize(("target", "source"), [
    ("1m", "5m"),
    ("7m", "5m"),
    ("1h", "7m"),
    ("1M", "7h"),
    ("1M", "1w"),
    ("2M", "3M"),
    ("1w", "1M"),
])
def test_rejects_a_finer_or_misaligned_target(target: str, source: str) -> None:
    assert not SampleSize.Parse(target).can_be_resampled_from(SampleSize.Parse(source))
