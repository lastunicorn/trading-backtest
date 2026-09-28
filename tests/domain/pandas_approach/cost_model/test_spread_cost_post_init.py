"""Tests for `domain.pandas_approach.cost_model.SpreadCost.__post_init__`."""

import pytest

from domain.pandas_approach.cost_model import SpreadCost


def test_commission_defaults_to_zero() -> None:
    assert SpreadCost().commission_pips == 0.0


def test_negative_commission_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        SpreadCost(commission_pips=-0.2)
