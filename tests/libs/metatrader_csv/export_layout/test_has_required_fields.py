"""Tests for `libs.metatrader_csv.export_layout.Layout.has_required_fields`."""

from libs.metatrader_csv import Layout


def test_true_with_date_time_and_four_prices() -> None:
    columns = {"date": 0, "time": 1, "open": 2, "high": 3, "low": 4, "close": 5}

    assert Layout(",", columns, has_header=False, field_count=6).has_required_fields


def test_false_without_a_price() -> None:
    columns = {"date": 0, "time": 1, "open": 2, "high": 3, "low": 4}

    assert not Layout(",", columns, has_header=True, field_count=5).has_required_fields
